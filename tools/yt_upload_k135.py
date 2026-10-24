"""K135 雙視窗演練影片上傳 YouTube（Data API v3，本機執行）。

用法：
    PYTHONUTF8=1 python tools/yt_upload_k135.py [--manifest PATH] [--only KEY] [--dry-run]
    PYTHONUTF8=1 python tools/yt_upload_k135.py status [--manifest PATH]
    PYTHONUTF8=1 python tools/yt_upload_k135.py --self-test

安全設計：
- 啟動先用 channels.list(mine=True) 確認頻道 id，不是指定頻道立即停止，絕不傳到別的頻道。
- 狀態存在 manifest 同目錄的 yt_state.json；已上傳的一律跳過，避免重複上傳。
- 狀態檔遺失時，先比對頻道「上傳的影片」清單標題，同名就沿用，不重傳。
- 配額用完存檔後 exit 75，隔天執行同一指令會從中斷處繼續。
最後一行固定印 YT_UPLOAD_RESULT=OK|PARTIAL|QUOTA|ERROR，方便其他工具判讀。
"""
import argparse
import json
import os
import random
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

TOKEN_PATH = Path.home() / ".config" / "youtube-comment" / "token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
EXPECTED_CHANNEL_ID = "UCdq7Mig9UZNjtpj1KJRsJ6A"
DEFAULT_MANIFEST = Path.home() / "Videos" / "kindle-drill" / "k135" / "out" / "upload_manifest.json"

CHUNK_SIZE = 8 * 1024 * 1024
MAX_RETRIES = 5
RETRIABLE_STATUS = {500, 502, 503, 504}
QUOTA_REASONS = {"quotaExceeded", "uploadLimitExceeded", "dailyLimitExceeded"}
EXIT_QUOTA = 75

# 播放清單定義：manifest 的 playlist 欄位 → 要加入哪些清單
PLAYLISTS = {
    "drill": "K135 ROS 2 from Scratch｜雙視窗演練",
    "highlight": "K135 ROS 2 from Scratch｜精華版",
    "prompts": "K135 ROS 2 from Scratch｜提示詞與指令",
}
MEMBERSHIP = {
    "full": ["drill"],
    "highlight": ["drill", "highlight"],
    "prompts": ["prompts"],
}


class UploadError(Exception):
    """一般可預期錯誤（缺檔、API 錯誤）。"""


class QuotaError(Exception):
    """今日配額或上傳次數已用完。"""


# ================================================================ manifest／狀態

def load_manifest(path):
    path = Path(path)
    if not path.is_file():
        raise UploadError(f"找不到 manifest：{path}（先跑 make_videos.py manifest）")
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise UploadError(f"manifest JSON 解析失敗：{path}（{exc}）") from exc
    if not isinstance(entries, list) or not entries:
        raise UploadError(f"manifest 必須是非空陣列：{path}")
    seen = set()
    for idx, entry in enumerate(entries):
        missing = [k for k in ("key", "file", "title", "description", "playlist") if not entry.get(k)]
        if missing:
            raise UploadError(f"manifest 第 {idx + 1} 筆缺欄位：{missing}")
        if entry["playlist"] not in MEMBERSHIP:
            raise UploadError(f"manifest {entry['key']} 的 playlist 不合法：{entry['playlist']}")
        if entry["key"] in seen:
            raise UploadError(f"manifest key 重複：{entry['key']}")
        seen.add(entry["key"])
    return entries


def empty_state():
    return {"videos": {}, "playlists": {}, "playlist_items": {}}


def load_state(path):
    path = Path(path)
    if not path.is_file():
        return empty_state()
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise UploadError(f"狀態檔損毀，請手動檢查：{path}（{exc}）") from exc
    base = empty_state()
    base.update({k: v for k, v in state.items() if isinstance(v, dict)})
    return base


def save_state(path, state):
    """先寫暫存檔再取代，避免中途中斷留下半個 JSON。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def is_uploaded(state, key):
    info = state["videos"].get(key)
    return bool(info and info.get("video_id") and info.get("status") in ("uploaded", "adopted"))


def select_entries(entries, only):
    if only is None:
        return entries
    picked = [e for e in entries if e["key"] == only]
    if not picked:
        raise UploadError(f"--only {only} 不在 manifest 中（可用：{[e['key'] for e in entries]}）")
    return picked


def plan_actions(entries, state):
    """回傳待做事項清單（不連網），供 --dry-run 與 self-test 使用。"""
    actions = []
    needed = []
    for entry in entries:
        for pkey in MEMBERSHIP[entry["playlist"]]:
            if pkey not in needed:
                needed.append(pkey)
    for pkey in needed:
        if not state["playlists"].get(pkey, {}).get("playlist_id"):
            actions.append(("create_playlist", pkey, PLAYLISTS[pkey]))
    for entry in entries:
        key = entry["key"]
        if is_uploaded(state, key):
            actions.append(("skip_upload", key, state["videos"][key]["video_id"]))
        else:
            actions.append(("upload", key, entry["file"]))
        vid = state["videos"].get(key, {}).get("video_id")
        for pkey in MEMBERSHIP[entry["playlist"]]:
            if not vid or vid not in state["playlist_items"].get(pkey, []):
                actions.append(("add_to_playlist", key, pkey))
    return actions


# ================================================================ API

def http_error_reason(exc):
    """從 HttpError 取出 errors[0].reason。"""
    try:
        payload = json.loads(exc.content.decode("utf-8"))
        errors = payload.get("error", {}).get("errors") or []
        if errors:
            return errors[0].get("reason", "")
        return payload.get("error", {}).get("status", "")
    except (ValueError, AttributeError):
        return ""


def check_quota(exc):
    status = getattr(getattr(exc, "resp", None), "status", None)
    if int(status or 0) == 403 and http_error_reason(exc) in QUOTA_REASONS:
        raise QuotaError(http_error_reason(exc)) from exc


def build_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    if not TOKEN_PATH.is_file():
        raise UploadError(f"找不到 YouTube 憑證：{TOKEN_PATH}")
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise UploadError(f"憑證無效且無法 refresh：{TOKEN_PATH}")
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def execute(request, desc):
    """一般 API 呼叫：5xx 重試，配額錯誤轉成 QuotaError。"""
    from googleapiclient.errors import HttpError
    for attempt in range(MAX_RETRIES + 1):
        try:
            return request.execute()
        except HttpError as exc:
            check_quota(exc)
            if exc.resp.status in RETRIABLE_STATUS and attempt < MAX_RETRIES:
                time.sleep(2 ** attempt + random.random())
                continue
            raise UploadError(f"{desc} 失敗：HTTP {exc.resp.status} {http_error_reason(exc)}") from exc
        except (ConnectionError, TimeoutError, OSError) as exc:
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt + random.random())
                continue
            raise UploadError(f"{desc} 網路錯誤：{exc}") from exc
    raise UploadError(f"{desc} 重試用盡")


def verify_channel(youtube):
    """頻道不符立即停止，確保不會傳到別人的頻道。"""
    resp = execute(youtube.channels().list(part="id,snippet,contentDetails", mine=True), "查詢頻道")
    items = resp.get("items") or []
    if len(items) != 1 or items[0]["id"] != EXPECTED_CHANNEL_ID:
        got = [i.get("id") for i in items]
        raise UploadError(f"頻道不符！預期 {EXPECTED_CHANNEL_ID}，實際 {got}，立即停止")
    title = items[0]["snippet"].get("title", "")
    print(f"頻道確認：{title}（{EXPECTED_CHANNEL_ID}）")
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def list_uploaded_titles(youtube, uploads_playlist):
    """標題 → video_id；狀態檔遺失時用來避免重複上傳。"""
    titles, token = {}, None
    while True:
        resp = execute(youtube.playlistItems().list(
            part="snippet", playlistId=uploads_playlist, maxResults=50, pageToken=token),
            "列出已上傳影片")
        for item in resp.get("items", []):
            snip = item["snippet"]
            titles.setdefault(snip.get("title", ""), snip["resourceId"]["videoId"])
        token = resp.get("nextPageToken")
        if not token:
            return titles


def upload_video(youtube, entry):
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    path = Path(entry["file"])
    if not path.is_file():
        raise UploadError(f"影片檔不存在：{path}")
    body = {
        "snippet": {"title": entry["title"], "description": entry["description"],
                    "categoryId": "27", "defaultLanguage": "zh-TW",
                    "defaultAudioLanguage": "zh-TW"},
        "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(path), mimetype="video/mp4", chunksize=CHUNK_SIZE, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response, retries = None, 0
    size_mb = path.stat().st_size / 1024 / 1024
    print(f"上傳 {entry['key']}（{size_mb:.1f} MB）…")
    while response is None:
        try:
            progress, response = request.next_chunk()
            retries = 0
            if progress:
                print(f"  {progress.progress() * 100:5.1f}%", flush=True)
        except HttpError as exc:
            check_quota(exc)
            if exc.resp.status not in RETRIABLE_STATUS or retries >= MAX_RETRIES:
                raise UploadError(f"上傳 {entry['key']} 失敗：HTTP {exc.resp.status} "
                                  f"{http_error_reason(exc)}") from exc
            retries += 1
            time.sleep(2 ** retries + random.random())
        except (ConnectionError, TimeoutError, OSError) as exc:
            if retries >= MAX_RETRIES:
                raise UploadError(f"上傳 {entry['key']} 網路錯誤：{exc}") from exc
            retries += 1
            time.sleep(2 ** retries + random.random())
    return response["id"]


def ensure_playlist(youtube, state, state_path, pkey):
    pid = state["playlists"].get(pkey, {}).get("playlist_id")
    if pid:
        return pid
    title = PLAYLISTS[pkey]
    token = None
    while not pid:  # 先找同名清單，避免狀態檔遺失時重複建立
        resp = execute(youtube.playlists().list(part="snippet", mine=True, maxResults=50,
                                                pageToken=token), "列出播放清單")
        for item in resp.get("items", []):
            if item["snippet"]["title"] == title:
                pid = item["id"]
                break
        token = resp.get("nextPageToken")
        if not token:
            break
    if not pid:
        resp = execute(youtube.playlists().insert(part="snippet,status", body={
            "snippet": {"title": title, "defaultLanguage": "zh-TW"},
            "status": {"privacyStatus": "private"}}), f"建立播放清單 {title}")
        pid = resp["id"]
        print(f"建立播放清單：{title}")
    state["playlists"][pkey] = {"playlist_id": pid, "title": title}
    save_state(state_path, state)
    return pid


def add_to_playlist(youtube, state, state_path, pkey, video_id):
    items = state["playlist_items"].setdefault(pkey, [])
    if video_id in items:
        return
    pid = ensure_playlist(youtube, state, state_path, pkey)
    body = {"snippet": {"playlistId": pid, "position": len(items),
                        "resourceId": {"kind": "youtube#video", "videoId": video_id}}}
    try:
        execute(youtube.playlistItems().insert(part="snippet", body=body), "加入播放清單")
    except UploadError:
        # 清單被手動改過時 position 可能超出範圍，退回加到最後
        body["snippet"].pop("position")
        execute(youtube.playlistItems().insert(part="snippet", body=body), "加入播放清單")
    items.append(video_id)
    save_state(state_path, state)


# ================================================================ 指令

def process_entry(youtube, state, state_path, entry, uploaded_titles):
    key = entry["key"]
    if is_uploaded(state, key):
        print(f"略過 {key}（已上傳 {state['videos'][key]['video_id']}）")
    elif entry["title"] in uploaded_titles:
        vid = uploaded_titles[entry["title"]]
        state["videos"][key] = {"video_id": vid, "status": "adopted", "title": entry["title"],
                                "at": datetime.now().isoformat(timespec="seconds")}
        save_state(state_path, state)
        print(f"沿用 {key}：頻道已有同名影片 {vid}")
    else:
        vid = upload_video(youtube, entry)
        state["videos"][key] = {"video_id": vid, "status": "uploaded", "title": entry["title"],
                                "at": datetime.now().isoformat(timespec="seconds")}
        save_state(state_path, state)
        print(f"完成 {key}：https://youtu.be/{vid}")
    vid = state["videos"][key]["video_id"]
    for pkey in MEMBERSHIP[entry["playlist"]]:
        add_to_playlist(youtube, state, state_path, pkey, vid)


def run_upload(entries, state_path):
    state = load_state(state_path)
    youtube = build_service()
    uploads = verify_channel(youtube)
    uploaded_titles = list_uploaded_titles(youtube, uploads)
    failures = []
    for entry in entries:
        try:
            process_entry(youtube, state, state_path, entry, uploaded_titles)
        except UploadError as exc:
            print(f"錯誤：{exc}", file=sys.stderr)
            failures.append(entry["key"])
    save_state(state_path, state)
    if failures:
        print(f"未完成：{failures}", file=sys.stderr)
        return "PARTIAL"
    return "OK"


def print_dry_run(entries, state):
    actions = plan_actions(entries, state)
    labels = {"create_playlist": "建立清單", "upload": "上傳", "skip_upload": "略過（已上傳）",
              "add_to_playlist": "加入清單"}
    for kind, target, detail in actions:
        print(f"[dry-run] {labels[kind]}：{target} → {detail}")
    print(f"[dry-run] 共 {sum(1 for a in actions if a[0] == 'upload')} 支待上傳，未連網")


def print_status(entries, state):
    for entry in entries:
        info = state["videos"].get(entry["key"])
        if info and info.get("video_id"):
            print(f"{entry['key']:12s} {info['status']:9s} https://youtu.be/{info['video_id']}  {entry['title']}")
        else:
            exists = "檔案在" if Path(entry["file"]).is_file() else "檔案缺"
            print(f"{entry['key']:12s} 未上傳    （{exists}）  {entry['title']}")
    for pkey, info in state["playlists"].items():
        count = len(state["playlist_items"].get(pkey, []))
        print(f"清單 {info['title']}：{count} 支 https://www.youtube.com/playlist?list={info['playlist_id']}")


# ================================================================ self-test

def self_test():
    root = Path(tempfile.mkdtemp(prefix="k135yt_"))
    files = {}
    for key in ("full", "highlight", "prompt-01"):
        files[key] = root / f"{key}.mp4"
        files[key].write_bytes(b"\x00" * 16)
    manifest = [
        {"key": "full", "file": str(files["full"]), "title": "完整版", "description": "d", "playlist": "full"},
        {"key": "highlight", "file": str(files["highlight"]), "title": "精華版", "description": "d",
         "playlist": "highlight"},
        {"key": "prompt-01", "file": str(files["prompt-01"]), "title": "提示詞 01", "description": "d",
         "playlist": "prompts"},
    ]
    mpath = root / "upload_manifest.json"
    mpath.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    try:
        entries = load_manifest(mpath)
        assert [e["key"] for e in entries] == ["full", "highlight", "prompt-01"]
        spath = root / "yt_state.json"
        state = load_state(spath)
        assert state == empty_state()
        acts = plan_actions(entries, state)
        assert sum(1 for a in acts if a[0] == "upload") == 3
        assert sum(1 for a in acts if a[0] == "create_playlist") == 3
        assert sum(1 for a in acts if a[0] == "add_to_playlist") == 4  # full1 + highlight2 + prompt1
        state["videos"]["full"] = {"video_id": "VID_FULL", "status": "uploaded"}
        state["playlists"]["drill"] = {"playlist_id": "PL1", "title": PLAYLISTS["drill"]}
        state["playlist_items"]["drill"] = ["VID_FULL"]
        save_state(spath, state)
        state2 = load_state(spath)
        assert state2["videos"]["full"]["video_id"] == "VID_FULL"
        acts2 = plan_actions(entries, state2)
        assert ("skip_upload", "full", "VID_FULL") in acts2
        assert not any(a[0] == "upload" and a[1] == "full" for a in acts2)
        assert not any(a == ("add_to_playlist", "full", "drill") for a in acts2)
        assert select_entries(entries, "highlight")[0]["key"] == "highlight"
        try:
            select_entries(entries, "nope")
            raise AssertionError("--only 不存在的 key 應該報錯")
        except UploadError:
            pass
        bad = root / "bad.json"
        bad.write_text(json.dumps([{"key": "x"}]), encoding="utf-8")
        try:
            load_manifest(bad)
            raise AssertionError("缺欄位的 manifest 應該報錯")
        except UploadError:
            pass
        _test_quota_detection()
        print("SELF-TEST PASS")
        return 0
    except (AssertionError, UploadError) as exc:
        print(f"SELF-TEST FAIL：{exc!r}（暫存於 {root}）", file=sys.stderr)
        return 1


def _test_quota_detection():
    """用假的 HttpError 驗證配額判斷（不連網）。"""
    import httplib2
    from googleapiclient.errors import HttpError
    content = json.dumps({"error": {"errors": [{"reason": "quotaExceeded"}]}}).encode("utf-8")
    exc = HttpError(httplib2.Response({"status": 403}), content)
    assert http_error_reason(exc) == "quotaExceeded"
    try:
        check_quota(exc)
        raise AssertionError("quotaExceeded 應轉成 QuotaError")
    except QuotaError:
        pass
    other = HttpError(httplib2.Response({"status": 403}),
                      json.dumps({"error": {"errors": [{"reason": "forbidden"}]}}).encode("utf-8"))
    check_quota(other)  # 非配額錯誤不應拋 QuotaError


# ================================================================ main

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="K135 影片上傳 YouTube")
    parser.add_argument("command", nargs="?", choices=["status"], help="status：列出每支狀態")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="upload_manifest.json 路徑")
    parser.add_argument("--only", help="只處理這個 key")
    parser.add_argument("--dry-run", action="store_true", help="只列出會做什麼，不連網")
    parser.add_argument("--self-test", action="store_true", help="離線驗證 manifest／狀態邏輯")
    return parser.parse_args(argv)


def main():
    args = parse_args()
    if args.self_test:
        code = self_test()
        print(f"YT_UPLOAD_RESULT={'OK' if code == 0 else 'ERROR'}")
        sys.exit(code)
    manifest_path = Path(args.manifest).expanduser()
    state_path = manifest_path.parent / "yt_state.json"
    try:
        entries = select_entries(load_manifest(manifest_path), args.only)
        if args.command == "status":
            print_status(entries, load_state(state_path))
            result = "OK"
        elif args.dry_run:
            print_dry_run(entries, load_state(state_path))
            result = "OK"
        else:
            result = run_upload(entries, state_path)
    except QuotaError as exc:
        print(f"今日配額已用完（{exc}），明天再執行同一指令會從中斷處繼續", file=sys.stderr)
        print("YT_UPLOAD_RESULT=QUOTA")
        sys.exit(EXIT_QUOTA)
    except UploadError as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        print("YT_UPLOAD_RESULT=ERROR")
        sys.exit(1)
    except Exception as exc:  # 未預期錯誤也要印出結果行，讓呼叫端可判讀
        print(f"未預期錯誤：{type(exc).__name__}: {exc}", file=sys.stderr)
        print("YT_UPLOAD_RESULT=ERROR")
        sys.exit(1)
    print(f"YT_UPLOAD_RESULT={result}")
    sys.exit(0 if result == "OK" else 2)


if __name__ == "__main__":
    main()

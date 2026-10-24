"""K135 演練錄影：同時錄螢幕 2 與螢幕 3（絕對不錄螢幕 1）。

子指令：
  start  — 以 DETACHED 背景程序啟動自己的 run，印 PID 後立即返回
  run    — 常駐：開兩個 ffmpeg gdigrab，等停止旗標或時間上限，收尾並 remux 成 mp4
  stop   — 建立停止旗標，等 run 結束，印輸出檔
  status — 是否錄影中與檔案大小

為什麼 ffmpeg 用 stdin 寫 q 收尾：直接 kill 會讓 mkv 沒有正確結尾索引；
mkv 即使被中斷也比 mp4 救得回來，所以先錄 mkv、收尾後再 -c copy 轉 mp4。
為什麼記 time.time()：events.log 的 rec_start 是後製對齊 drill_ctl 事件的時間零點。
"""
import argparse
import ctypes
import glob
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path.home() / "Videos" / "kindle-drill" / "k135"
RAW_DIR = BASE_DIR / "raw"
EVENTS_LOG = BASE_DIR / "events.log"
SESSION_FILE = RAW_DIR / "session.json"
STOP_FLAG = Path(os.environ.get("TEMP") or os.environ.get("TMP") or str(Path.home())) / "k135-record.stop"

# 螢幕 2：x 1920~3840；螢幕 3：x -1280~0（螢幕 1 = x 0~1920，絕對不錄）
SCREENS = {
    "m2": {"offset_x": 1920, "offset_y": 0, "size": "1920x1080"},
    "m3": {"offset_x": -1280, "offset_y": 0, "size": "1280x720"},
}
FRAMERATE = 15
POLL_SEC = 2
QUIT_WAIT_SEC = 60
STOP_WAIT_SEC = 120

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000


def log_event(event: str, content: str, ts: float = None) -> None:
    try:
        EVENTS_LOG.parent.mkdir(parents=True, exist_ok=True)
        moment = datetime.fromtimestamp(ts) if ts is not None else datetime.now()
        stamp = moment.astimezone().isoformat(timespec="milliseconds")
        with EVENTS_LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"{stamp}\t{event}\t{content}\n")
    except OSError as exc:
        print(f"警告：無法寫入事件檔 {EVENTS_LOG}：{exc}", file=sys.stderr)


def find_ffmpeg() -> str:
    """WinGet 裝的 ffmpeg 不在 PATH，先找 WinGet 套件目錄再退回 PATH。"""
    local = os.environ.get("LOCALAPPDATA")
    if local:
        pattern = os.path.join(local, "Microsoft", "WinGet", "Packages",
                               "Gyan.FFmpeg*", "ffmpeg-*", "bin", "ffmpeg.exe")
        hits = sorted(glob.glob(pattern))
        if hits:
            return hits[-1]
    on_path = shutil.which("ffmpeg")
    if on_path:
        return on_path
    raise FileNotFoundError("找不到 ffmpeg.exe（WinGet Gyan.FFmpeg 目錄與 PATH 都沒有）")


def is_pid_alive(pid: int) -> bool:
    """用 OpenProcess + GetExitCodeProcess 判斷，避免依賴 psutil。"""
    if not pid:
        return False
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        return code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def read_session():
    try:
        return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        print(f"警告：session.json 讀取失敗：{exc}", file=sys.stderr)
        return None


def write_session(data: dict) -> None:
    SESSION_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------- run ----------

def start_ffmpeg(ffmpeg: str, name: str, out_path: Path, log_fh):
    geo = SCREENS[name]
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "warning", "-y",
           "-f", "gdigrab", "-framerate", str(FRAMERATE),
           "-offset_x", str(geo["offset_x"]), "-offset_y", str(geo["offset_y"]),
           "-video_size", geo["size"], "-i", "desktop",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p",
           str(out_path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=log_fh, stderr=log_fh,
                            creationflags=CREATE_NO_WINDOW)
    return proc, time.time()


def quit_ffmpeg(proc, name: str) -> None:
    """寫 q 讓 ffmpeg 正常寫完檔尾；逾時才 kill。"""
    if proc.poll() is not None:
        return
    try:
        proc.stdin.write(b"q")
        proc.stdin.flush()
        proc.stdin.close()
    except (OSError, ValueError) as exc:
        log_event("rec_error", f"{name} 寫入 q 失敗：{exc}")
    try:
        proc.wait(timeout=QUIT_WAIT_SEC)
    except subprocess.TimeoutExpired:
        log_event("rec_error", f"{name} {QUIT_WAIT_SEC} 秒未結束，強制 kill")
        proc.kill()
        proc.wait(timeout=10)


def remux_to_mp4(ffmpeg: str, mkv: Path):
    if not mkv.is_file() or mkv.stat().st_size == 0:
        log_event("rec_error", f"{mkv.name} 不存在或為空，略過 remux")
        return None
    mp4 = mkv.with_suffix(".mp4")
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(mkv),
           "-c", "copy", str(mp4)]
    try:
        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace",
                                timeout=600, creationflags=CREATE_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired) as exc:
        log_event("rec_error", f"remux {mkv.name} 失敗：{exc}")
        return None
    if result.returncode != 0:
        log_event("rec_error", f"remux {mkv.name} 失敗：{result.stderr.strip()[:200]}")
        return None
    return mp4


def wait_for_stop(procs: dict, max_minutes: float) -> str:
    """回傳停止原因：flag / timeout / died:<name>。"""
    deadline = time.time() + max_minutes * 60
    while True:
        for name, proc in procs.items():
            if proc.poll() is not None:
                return f"died:{name}"
        if STOP_FLAG.exists():
            return "flag"
        if time.time() >= deadline:
            return "timeout"
        time.sleep(POLL_SEC)


def cmd_run(args) -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    try:
        STOP_FLAG.unlink()
    except FileNotFoundError:
        pass
    ffmpeg = find_ffmpeg()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    outputs = {name: RAW_DIR / f"{name}-{stamp}.mkv" for name in SCREENS}
    log_path = RAW_DIR / f"ffmpeg-{stamp}.log"

    procs, started = {}, {}
    with log_path.open("ab") as log_fh:
        try:
            for name, out in outputs.items():
                procs[name], started[name] = start_ffmpeg(ffmpeg, name, out, log_fh)
                log_event("rec_start", f"{name} {out.name}", ts=started[name])
        except OSError as exc:
            log_event("rec_error", f"啟動 ffmpeg 失敗：{exc}")
            for name, proc in procs.items():
                quit_ffmpeg(proc, name)
            raise

        write_session({
            "run_pid": os.getpid(),
            "stamp": stamp,
            "files": {n: str(p) for n, p in outputs.items()},
            "start_time": {n: round(t, 3) for n, t in started.items()},
            "ffmpeg_pid": {n: p.pid for n, p in procs.items()},
            "state": "recording",
        })

        reason = wait_for_stop(procs, args.max_minutes)
        if reason.startswith("died:"):
            dead = reason.split(":", 1)[1]
            log_event("rec_error", f"{dead} ffmpeg 提早結束（exit {procs[dead].returncode}），停止另一路；詳見 {log_path.name}")
        for name, proc in procs.items():
            quit_ffmpeg(proc, name)

    mp4s = {name: remux_to_mp4(ffmpeg, mkv) for name, mkv in outputs.items()}
    for name in SCREENS:
        final = mp4s[name] or outputs[name]
        log_event("rec_stop", f"{name} {final.name} 原因={reason}")
    session = read_session() or {}
    session.update({"state": "stopped", "reason": reason,
                    "mp4": {n: str(p) if p else None for n, p in mp4s.items()}})
    write_session(session)
    try:
        STOP_FLAG.unlink()
    except FileNotFoundError:
        pass
    return 0 if not reason.startswith("died:") else 1


# ---------- start / stop / status ----------

def cmd_start(args) -> int:
    session = read_session()
    if session and session.get("state") == "recording" and is_pid_alive(session.get("run_pid")):
        print(f"錯誤：已在錄影中（run PID {session['run_pid']}）", file=sys.stderr)
        return 1
    find_ffmpeg()  # 先確認 ffmpeg 存在，免得背景程序默默失敗
    cmd = [sys.executable, str(Path(__file__).resolve()), "run",
           "--max-minutes", str(args.max_minutes)]
    try:
        STOP_FLAG.unlink()
    except FileNotFoundError:
        pass
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, close_fds=True,
                            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP)
    print(f"錄影已在背景啟動，run PID {proc.pid}")
    return 0


def cmd_stop(_args) -> int:
    session = read_session()
    if not session:
        print("錯誤：找不到 session.json，沒有錄影中的工作", file=sys.stderr)
        return 1
    pid = session.get("run_pid")
    STOP_FLAG.parent.mkdir(parents=True, exist_ok=True)
    STOP_FLAG.write_text("stop", encoding="utf-8")
    deadline = time.time() + STOP_WAIT_SEC
    while is_pid_alive(pid) and time.time() < deadline:
        time.sleep(1)
    if is_pid_alive(pid):
        print(f"錯誤：等候 {STOP_WAIT_SEC} 秒 run PID {pid} 仍未結束", file=sys.stderr)
        return 1
    session = read_session() or session
    outputs = session.get("mp4") or {}
    for name, mkv in session.get("files", {}).items():
        print(f"{name}: {outputs.get(name) or mkv}")
    return 0


def human_size(num: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TB"


def cmd_status(_args) -> int:
    session = read_session()
    if not session:
        print("未錄影（沒有 session.json）")
        return 0
    alive = is_pid_alive(session.get("run_pid"))
    print(f"錄影中：{'是' if alive else '否'}（run PID {session.get('run_pid')}，狀態 {session.get('state')}）")
    for name, path in session.get("files", {}).items():
        target = Path(path)
        mp4 = (session.get("mp4") or {}).get(name)
        if not alive and mp4:
            target = Path(mp4)
        size = human_size(target.stat().st_size) if target.is_file() else "（檔案不存在）"
        print(f"  {name}: {target}  {size}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="K135 演練錄影（螢幕 2＋螢幕 3，不錄螢幕 1）")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, func, helptext in (("start", cmd_start, "背景啟動錄影"),
                                 ("run", cmd_run, "前景常駐錄影（通常由 start 呼叫）")):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("--max-minutes", type=float, default=180, help="錄影上限分鐘（預設 180）")
        p.set_defaults(func=func)
    sub.add_parser("stop", help="停止錄影並印輸出檔").set_defaults(func=cmd_stop)
    sub.add_parser("status", help="是否錄影中與檔案大小").set_defaults(func=cmd_status)
    return parser


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args()
    if getattr(args, "max_minutes", 1) <= 0:
        print("錯誤：--max-minutes 必須大於 0", file=sys.stderr)
        return 1
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        log_event("rec_error", str(exc))
        return 1
    except OSError as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        log_event("rec_error", str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())

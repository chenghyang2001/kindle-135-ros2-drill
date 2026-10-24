"""K135《ROS 2 from Scratch》雙視窗演練：把錄影產物剪成完整版、精華版、提示詞影片，並產生上傳清單。

用法：
    PYTHONUTF8=1 python tools/make_videos.py full|highlight|prompts|manifest|all [--out DIR]
    PYTHONUTF8=1 python tools/make_videos.py --self-test

輸入（格式由錄影工具決定）：
- ~/Videos/kindle-drill/k135/events.log：ISO8601<TAB>事件<TAB>內容
- ~/Videos/kindle-drill/k135/raw/：m2／m3 錄影（收尾後有同名 .mp4）
- teaching/drill.json、teaching/narration/highlight.json、teaching/narration/prompts/chNN.txt

設計重點：
- 工作目錄放系統暫存區（ASCII 路徑），中文檔名的成品最後才搬到輸出目錄，
  避開 ffmpeg 濾鏡字串裡的中文路徑跳脫問題。
- 所有文字用 Pillow 畫成 PNG 再疊上去，不用 drawtext（中文與冒號跳脫很容易出錯）。
- 濾鏡寫成腳本檔，用 ffmpeg 7+ 的 `-/filter_complex <檔>`（舊的 -filter_complex_script 在 9 已移除）。
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
VIDEO_ROOT = Path.home() / "Videos" / "kindle-drill" / "k135"
DEFAULT_OUT = VIDEO_ROOT / "out"

BOOK_LABEL = "K135《ROS 2 from Scratch》"
REPO_URL = "https://github.com/chenghyang2001/kindle-135-ros2-drill"
VOICE = "zh-TW-HsiaoChenNeural"
TTS_RETRIES = 3

W, H, FPS = 1920, 1080, 30
BG_COLOR = (0x16, 0x20, 0x2A)
ORANGE = (0xE8, 0x95, 0x6A)
WHITE = (0xFF, 0xFF, 0xFF)
FONT_REGULAR = "C:/Windows/Fonts/msjh.ttc"
FONT_BOLD = "C:/Windows/Fonts/msjhbd.ttc"

INTRO_CARD_SEC = 4.0
TRIM_MARGIN_SEC = 3.0
# 第 1 段沒有 enter 事件標記開始，open 後約 3 秒畫面才出現第一段內容
FIRST_SECTION_DELAY = 3.0
# 段落結束前 1 秒收尾：enter 那一刻畫面常已切到下一段，留 1 秒避免剪到切換瞬間
HIGHLIGHT_TAIL_SEC = 1.0
MIN_CHAPTER_SEC = 10.0
VOICE_PAD_SEC = 0.8

# 精華版「雙視窗並排」版面：不用任何子畫面，避免小框擋住練習視窗的字。
# 螢幕 2 實測視窗位置：左「教練」x≈10～948、右「練習」x≈972～1910，工作列 y≥1008，
# 所以各切 942x1004（左右各多留一點邊緣，底部排除工作列）。格式為 (寬, 高, x, y)。
COACH_CROP = (942, 1004, 8, 0)
PRACTICE_CROP = (942, 1004, 970, 0)
BANNER_H = 120
WIN_H = 940
# 等比縮放後的寬度，取偶數（libx264 yuv420p 需要）
WIN_W = int(round(COACH_CROP[0] * WIN_H / COACH_CROP[1] / 2)) * 2
WIN_BORDER, WIN_GAP = 2, 24
WIN_BORDER_COLOR = "0xD0D0D0"
BANNER_MARGIN = 40

FULL_NAME = "K135-雙視窗演練-完整版"
HIGHLIGHT_NAME = "K135-雙視窗演練-精華版"
SECTION_RE = re.compile(r"\((\d+)/(\d+)\)")


class VideoError(Exception):
    """可預期的流程錯誤（缺檔、ffmpeg 失敗等），由 main() 統一印出。"""


@dataclass
class Context:
    """一次執行用到的所有路徑；self-test 會換成暫存目錄。"""
    out_dir: Path
    events_log: Path = VIDEO_ROOT / "events.log"
    raw_dir: Path = VIDEO_ROOT / "raw"
    drill_json: Path = REPO_DIR / "teaching" / "drill.json"
    narration_json: Path = REPO_DIR / "teaching" / "narration" / "highlight.json"
    prompts_dir: Path = REPO_DIR / "teaching" / "narration" / "prompts"
    caption_tool: Path = REPO_DIR / "tools" / "make_caption_video.py"
    force: bool = False
    keep_workdir: bool = False
    # self-test 離線時改用靜音代替 TTS，讓流程仍可驗證
    tts_silent_fallback: bool = False
    _tools: dict = field(default_factory=dict)


# ================================================================ ffmpeg 工具

def find_ffmpeg_tools():
    """優先找 WinGet 安裝的 Gyan.FFmpeg，找不到再用 PATH。"""
    local = os.environ.get("LOCALAPPDATA")
    if local:
        pattern = os.path.join(local, "Microsoft", "WinGet", "Packages",
                               "Gyan.FFmpeg*", "ffmpeg-*", "bin", "ffmpeg.exe")
        hits = sorted(glob.glob(pattern))
        if hits:
            ffmpeg = hits[-1]
            ffprobe = os.path.join(os.path.dirname(ffmpeg), "ffprobe.exe")
            if os.path.isfile(ffprobe):
                return ffmpeg, ffprobe
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise VideoError("找不到 ffmpeg／ffprobe（WinGet Gyan.FFmpeg 或 PATH 都沒有）")
    return ffmpeg, ffprobe


def tools(ctx):
    if not ctx._tools:
        ctx._tools["ffmpeg"], ctx._tools["ffprobe"] = find_ffmpeg_tools()
    return ctx._tools["ffmpeg"], ctx._tools["ffprobe"]


def run_cmd(cmd, desc, cwd=None, timeout=7200):
    """執行子程序；失敗時把 stderr 最後 20 行放進錯誤訊息。"""
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
    except FileNotFoundError as exc:
        raise VideoError(f"{desc}：找不到執行檔 {cmd[0]}（{exc}）") from exc
    except subprocess.TimeoutExpired as exc:
        raise VideoError(f"{desc}：逾時 {timeout} 秒") from exc
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or proc.stdout or "").strip().splitlines()[-20:])
        raise VideoError(f"{desc} 失敗（exit {proc.returncode}）：\n{tail}")
    return proc


def run_ffmpeg(ctx, args, desc, cwd=None):
    ffmpeg, _ = tools(ctx)
    return run_cmd([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", *args], desc, cwd=cwd)


def probe_duration(ctx, path):
    _, ffprobe = tools(ctx)
    proc = run_cmd([ffprobe, "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=nw=1:nk=1", str(path)], f"ffprobe {Path(path).name}")
    try:
        return float(proc.stdout.strip())
    except ValueError as exc:
        raise VideoError(f"無法讀取長度：{path}（ffprobe 輸出：{proc.stdout!r}）") from exc


def write_filter(workdir, name, text):
    path = Path(workdir) / name
    path.write_text(text, encoding="utf-8")
    return name


# ================================================================ 讀取輸入

def require_file(path, hint=""):
    if not Path(path).is_file():
        raise VideoError(f"缺檔：{path}{('（' + hint + '）') if hint else ''}")


def load_json(path, hint=""):
    require_file(path, hint)
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VideoError(f"JSON 解析失敗：{path}（{exc}）") from exc


def parse_events(path):
    """回傳 [(epoch 秒, 事件, 內容)]；格式錯的行略過並警告。"""
    require_file(path, "錄影時由 drill_ctl／record_m23 產生")
    events = []
    for lineno, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split("\t", 2)
        try:
            stamp = datetime.fromisoformat(parts[0].strip().replace("Z", "+00:00"))
        except ValueError:
            print(f"警告：events.log 第 {lineno} 行時間格式不對，略過：{line!r}", file=sys.stderr)
            continue
        name = parts[1].strip() if len(parts) > 1 else ""
        content = parts[2].strip() if len(parts) > 2 else ""
        events.append((stamp.timestamp(), name, content))
    events.sort(key=lambda e: e[0])
    if not events:
        raise VideoError(f"events.log 沒有任何事件：{path}")
    return events


def load_chapters(ctx):
    data = load_json(ctx.drill_json, "演練章節設定")
    chapters = data.get("chapters")
    if not chapters:
        raise VideoError(f"drill.json 沒有 chapters：{ctx.drill_json}")
    return chapters


def chapter_title(ch):
    return f"第 {int(ch['ch'])} 章 {ch['name']}"


def resolve_recording(raw_dir, filename):
    """收尾後同名 .mp4 優先；沒有就退回原始檔（通常是 .mkv）。"""
    name = Path(filename).name
    for cand in (raw_dir / (Path(name).stem + ".mp4"), raw_dir / name):
        if cand.is_file():
            return cand
    raise VideoError(f"找不到錄影檔：{raw_dir / (Path(name).stem + '.mp4')}（也沒有 {name}）")


def recording_from_session(raw_dir, key):
    """events.log 沒寫檔名時，從 session.json 找 m2／m3 的檔名。"""
    session = raw_dir / "session.json"
    if not session.is_file():
        return None
    try:
        data = json.loads(session.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    node = data.get(key)
    values = node.values() if isinstance(node, dict) else [node]
    for value in values:
        if isinstance(value, str) and value.lower().endswith((".mkv", ".mp4")):
            return value
    return None


def find_recordings(ctx, events):
    """回傳 {'m2': (路徑, 啟動 epoch), 'm3': (...)}，以 rec_start 事件為準。

    影片只用 m2；m3 可缺，有的話只把啟動時間寫進 composite_offset.json 備查。
    """
    found = {}
    for stamp, name, content in events:
        if name != "rec_start":
            continue
        # 內容以空格分隔：「m2 檔名 [其他欄位=值…]」，只取前兩個欄位
        parts = content.split()
        if parts and parts[0] in ("m2", "m3"):
            filename = parts[1] if len(parts) > 1 else recording_from_session(ctx.raw_dir, parts[0])
            if not filename:
                raise VideoError(f"rec_start {parts[0]} 沒有檔名，session.json 也查不到")
            found[parts[0]] = (resolve_recording(ctx.raw_dir, filename), stamp)
    if "m2" not in found:
        raise VideoError("events.log 缺少 rec_start m2")
    return found


def chapter_code(content):
    """open／close 內容可能是「ch01」或「01」，統一成兩位數字字串。"""
    code = content.strip()
    if code.lower().startswith("ch"):
        code = code[2:]
    return code.zfill(2) if code.isdigit() else code


def build_timeline(events):
    """每章取最後一次 open（重跑時以最後一次為準）到對應 close，收集期間的 enter。"""
    chapters, current = {}, None
    end_of_log = events[-1][0]
    for stamp, name, content in events:
        if name == "open":
            if current is not None and current["close"] is None:
                current["close"] = stamp
            current = {"open": stamp, "close": None, "enters": []}
            chapters[chapter_code(content)] = current
        elif name == "enter" and current is not None:
            current["enters"].append((stamp, content))
        elif name == "close" and current is not None:
            current["close"] = stamp
            current = None
        elif name == "rec_stop" and current is not None and current["close"] is None:
            current["close"] = stamp
    for record in chapters.values():
        if record["close"] is None:
            record["close"] = end_of_log
    return chapters


def section_bounds(record, k):
    """第 k 段的 (開始, 結束) 絕對時間；enter 內容含 (k-1/ 代表第 k 段開始。"""
    marks = {}
    for stamp, content in record["enters"]:
        match = SECTION_RE.search(content)
        if match:
            marks[int(match.group(1)) + 1] = stamp
    if k <= 1:
        start = record["open"] + FIRST_SECTION_DELAY
    elif k in marks:
        start = marks[k]
    else:
        raise VideoError(f"找不到第 {k} 段開始的 enter 事件（需要內容含「({k - 1}/」）")
    later = [t for idx, t in marks.items() if idx > k and t > start]
    end = min(later) if later else record["close"]
    return start, max(end, start)


def section_end_mark(record, k):
    """第 k 段結束時間：內容含「(k/」的 enter；重送造成多筆時取最後一筆，找不到用 close。"""
    hits = [stamp for stamp, content in record["enters"]
            if (m := SECTION_RE.search(content)) and int(m.group(1)) == k]
    return max(hits) if hits else record["close"]


# ================================================================ Pillow 畫面

def load_font(path, size):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(path, size)
    except OSError as exc:
        raise VideoError(f"載入字型失敗：{path}（{exc}）") from exc


def new_canvas():
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), BG_COLOR)
    return img, ImageDraw.Draw(img)


def draw_centered(draw, text, font, y, color):
    width = draw.textlength(text, font=font)
    draw.text(((W - width) / 2, y), text, font=font, fill=color)


def make_title_card(path, subtitle):
    """片頭／片尾卡：置中橘字書名、白字副標，中間一條橘色細線。"""
    img, draw = new_canvas()
    draw_centered(draw, BOOK_LABEL, load_font(FONT_BOLD, 88), 400, ORANGE)
    draw.rectangle([(W / 2 - 160, 530), (W / 2 + 160, 534)], fill=ORANGE)
    draw_centered(draw, subtitle, load_font(FONT_REGULAR, 56), 580, WHITE)
    img.save(path)


def fit_text(draw, text, font, max_width):
    """超出寬度就從尾端截掉並補「…」，確保章名不會壓到右側的「精華」。"""
    if draw.textlength(text, font=font) <= max_width:
        return text
    while text and draw.textlength(text + "…", font=font) > max_width:
        text = text[:-1]
    return text + "…"


def make_chapter_banner(path, ch):
    """精華版每章底圖：上方 120px 橫幅（左白字章名、右橘字「精華」），下方留給雙視窗。"""
    img, draw = new_canvas()
    font = load_font(FONT_BOLD, 56)
    mid_y = BANNER_H / 2
    tag = "精華"
    tag_w = draw.textlength(tag, font=font)
    draw.text((W - BANNER_MARGIN, mid_y), tag, font=font, fill=ORANGE, anchor="rm")
    title = f"K135　第 {int(ch['ch'])} 章　{ch['name']}"
    max_w = W - BANNER_MARGIN * 3 - tag_w
    draw.text((BANNER_MARGIN, mid_y), fit_text(draw, title, font, max_w), font=font,
              fill=WHITE, anchor="lm")
    img.save(path)


# ================================================================ full

def compute_trim(events, m2_start, m2_dur):
    opens = [t for t, n, _ in events if n == "open"]
    closes = [t for t, n, _ in events if n == "close"]
    if not opens or not closes:
        raise VideoError("events.log 至少要有一個 open 與一個 close 才能裁切")
    cut_start = max(opens[0] - TRIM_MARGIN_SEC, m2_start)
    cut_end = min(closes[-1] + TRIM_MARGIN_SEC, m2_start + m2_dur)
    if cut_end - cut_start < 1:
        raise VideoError(f"裁切範圍太短（{cut_end - cut_start:.2f} 秒），請檢查 events.log 與錄影時間")
    return cut_start, cut_end


def composite_filter():
    """螢幕 2 本身就是教練＋練習左右並排，直接輸出，不疊任何子畫面。"""
    return f"[0:v]fps={FPS},scale={W}:{H},setsar=1,format=yuv420p[v]\n"


def build_composite(ctx, workdir, recs, cut_start, cut_end):
    m2_path, m2_start = recs["m2"]
    dur = cut_end - cut_start
    args = ["-ss", f"{cut_start - m2_start:.3f}", "-t", f"{dur:.3f}", "-i", str(m2_path)]
    script = write_filter(workdir, "composite.txt", composite_filter())
    args += ["-/filter_complex", script, "-map", "[v]", "-an", "-t", f"{dur:.3f}",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(FPS),
             "-movflags", "+faststart", "composite.mp4"]
    print(f"裁切螢幕 2 雙視窗畫面（{dur:.1f} 秒）…")
    run_ffmpeg(ctx, args, "合成 composite.mp4", cwd=workdir)
    return Path(workdir) / "composite.mp4"


def build_full_video(ctx, workdir):
    card = Path(workdir) / "full_card.png"
    make_title_card(card, "雙視窗演練・完整版")
    script = write_filter(workdir, "full.txt", (
        f"[0:v]scale={W}:{H},setsar=1,fps={FPS},format=yuv420p[a];"
        f"[1:v]setsar=1,fps={FPS},format=yuv420p[b];"
        "[a][b]concat=n=2:v=1:a=0[v]\n"))
    args = ["-loop", "1", "-framerate", str(FPS), "-t", f"{INTRO_CARD_SEC}", "-i", card.name,
            "-i", "composite.mp4", "-/filter_complex", script, "-map", "[v]", "-an",
            "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-movflags", "+faststart",
            "full.mp4"]
    print("加片頭、輸出完整版…")
    run_ffmpeg(ctx, args, "輸出完整版", cwd=workdir)
    return Path(workdir) / "full.mp4"


def fmt_ts(seconds):
    total = int(max(seconds, 0))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def write_chapters_file(path, entries):
    """entries：[(秒, 標題)]；YouTube 規定第一行必須是 0:00。"""
    lines = ["0:00 開場"] + [f"{fmt_ts(t)} {title}" for t, title in sorted(entries)]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return lines


def cmd_full(ctx):
    events = parse_events(ctx.events_log)
    chapters = load_chapters(ctx)
    recs = find_recordings(ctx, events)
    m2_dur = probe_duration(ctx, recs["m2"][0])
    cut_start, cut_end = compute_trim(events, recs["m2"][1], m2_dur)
    ctx.out_dir.mkdir(parents=True, exist_ok=True)
    with work_dir(ctx) as workdir:
        build_composite(ctx, workdir, recs, cut_start, cut_end)
        build_full_video(ctx, workdir)
        shutil.move(str(Path(workdir) / "composite.mp4"), str(ctx.out_dir / "composite.mp4"))
        final = ctx.out_dir / f"{FULL_NAME}.mp4"
        shutil.move(str(Path(workdir) / "full.mp4"), str(final))
    offset = {
        "offset_epoch": cut_start,
        "offset_iso": datetime.fromtimestamp(cut_start).astimezone().isoformat(timespec="milliseconds"),
        "duration": cut_end - cut_start,
        "m2_start_epoch": recs["m2"][1],
        "m3_start_epoch": recs["m3"][1] if "m3" in recs else None,
    }
    (ctx.out_dir / "composite_offset.json").write_text(
        json.dumps(offset, ensure_ascii=False, indent=2), encoding="utf-8")
    timeline = build_timeline(events)
    entries = [(INTRO_CARD_SEC + timeline[c["ch"]]["open"] - cut_start, chapter_title(c))
               for c in chapters if c["ch"] in timeline]
    write_chapters_file(ctx.out_dir / f"{FULL_NAME}-chapters.txt", entries)
    print(f"完整版完成：{final}")
    return final


# ================================================================ highlight

def synthesize(ctx, text, out_mp3, workdir):
    """edge-tts 產生旁白，失敗重試 3 次；self-test 可退回靜音。"""
    cmd = [sys.executable, "-m", "edge_tts", "--voice", VOICE, "--text", text,
           "--write-media", out_mp3]
    last_err = None
    for attempt in range(1, TTS_RETRIES + 1):
        try:
            run_cmd(cmd, f"edge-tts（第 {attempt} 次）", cwd=workdir, timeout=180)
            if (Path(workdir) / out_mp3).stat().st_size > 0:
                return
            last_err = VideoError("edge-tts 產生空檔")
        except VideoError as exc:
            last_err = exc
        time.sleep(2 * attempt)
    if ctx.tts_silent_fallback:
        print(f"警告：TTS 失敗，self-test 改用 2 秒靜音（{last_err}）", file=sys.stderr)
        run_ffmpeg(ctx, ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "2",
                         "-c:a", "libmp3lame", out_mp3], "產生靜音", cwd=workdir)
        return
    raise VideoError(f"旁白合成失敗（已重試 {TTS_RETRIES} 次）：{last_err}")


ENCODE_ARGS = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
               "-r", str(FPS), "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2"]


def render_card_segment(ctx, workdir, png, mp3, seconds, out_name):
    script = write_filter(workdir, out_name + ".txt", (
        f"[0:v]scale={W}:{H},setsar=1,fps={FPS},format=yuv420p[v];"
        "[1:a]aresample=48000,aformat=channel_layouts=stereo,apad[a]\n"))
    run_ffmpeg(ctx, ["-loop", "1", "-framerate", str(FPS), "-i", png, "-i", mp3,
                     "-/filter_complex", script, "-map", "[v]", "-map", "[a]",
                     "-t", f"{seconds:.3f}", *ENCODE_ARGS, out_name],
               f"產生片段 {out_name}", cwd=workdir)


def plan_clip(record, k, seconds):
    """回傳片段的絕對 (開始 epoch, 結束 epoch)。

    取第 k 段的「最後」seconds 秒：段落結束前 1 秒收尾，往前推片長；
    若推到段落開始之前，就從段落開始起剪，不足處之後由 tpad 凍結補齊。
    （舊做法從段落開頭剪，常剪到圖形視窗還沒畫出來的黑畫面）
    """
    sec_start, _ = section_bounds(record, k)
    clip_end = section_end_mark(record, k) - HIGHLIGHT_TAIL_SEC
    if clip_end <= sec_start:
        clip_end = sec_start + 0.5
    clip_start = max(clip_end - seconds, sec_start)
    return clip_start, clip_end


def source_window(abs_start, abs_end, src_start, src_dur):
    """把絕對時間換成來源檔內的 (開始秒, 取用秒)，夾在檔案長度內，至少 0.5 秒。"""
    rel_start = min(max(abs_start - src_start, 0.0), max(src_dur - 0.5, 0.0))
    available = min(abs_end - src_start, src_dur) - rel_start
    return rel_start, max(available, 0.5)


def freeze_tpad(seconds, take):
    return f"tpad=stop_mode=clone:stop_duration={max(seconds - take, 0.0) + 0.5:.3f}"


def window_chain(label, crop, seconds, take, out_label):
    """切出一個視窗 → 等比縮到高 WIN_H → 加淺灰細框 → 不足長度時凍結補齊。"""
    crop_w, crop_h, crop_x, crop_y = crop
    return (f"[{label}]crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale={WIN_W}:{WIN_H},setsar=1,"
            f"pad={WIN_W + 2 * WIN_BORDER}:{WIN_H + 2 * WIN_BORDER}:{WIN_BORDER}:{WIN_BORDER}:"
            f"color={WIN_BORDER_COLOR},{freeze_tpad(seconds, take)}[{out_label}];")


def dual_window_positions():
    """回傳 (教練 x, 練習 x, y)：整組水平置中，垂直置中於橫幅下方的剩餘空間。"""
    box_w = WIN_W + 2 * WIN_BORDER
    box_h = WIN_H + 2 * WIN_BORDER
    left_x = (W - (box_w * 2 + WIN_GAP)) // 2
    top_y = BANNER_H + (H - BANNER_H - box_h) // 2
    return left_x, left_x + box_w + WIN_GAP, top_y


def dual_window_layout(seconds, take):
    """從 composite（=螢幕 2）切出教練、練習兩個視窗，左右並排一樣大，無子畫面。"""
    coach_x, practice_x, top_y = dual_window_positions()
    return (f"[1:v]fps={FPS},scale={W}:{H},setsar=1,split=2[src_coach][src_practice];"
            + window_chain("src_coach", COACH_CROP, seconds, take, "coach")
            + window_chain("src_practice", PRACTICE_CROP, seconds, take, "practice")
            + f"[bg][coach]overlay={coach_x}:{top_y}[tmp];"
            f"[tmp][practice]overlay={practice_x}:{top_y},format=yuv420p[v];")


def render_chapter_segment(ctx, workdir, ch, mp3, seconds, source, out_name):
    """source=(composite 路徑, 開始秒, 取用秒)；所有章節（含 gui）一律雙視窗並排。"""
    banner = f"banner_{ch['ch']}.png"
    make_chapter_banner(Path(workdir) / banner, ch)
    path, rel_start, take = source
    script = write_filter(workdir, out_name + ".txt", (
        f"[0:v]scale={W}:{H},setsar=1,fps={FPS}[bg];" + dual_window_layout(seconds, take) +
        "[2:a]aresample=48000,aformat=channel_layouts=stereo,apad[a]\n"))
    run_ffmpeg(ctx, ["-loop", "1", "-framerate", str(FPS), "-i", banner,
                     "-ss", f"{rel_start:.3f}", "-t", f"{take:.3f}", "-i", str(path),
                     "-i", mp3, "-/filter_complex", script,
                     "-map", "[v]", "-map", "[a]",
                     "-t", f"{seconds:.3f}", *ENCODE_ARGS, out_name],
               f"產生第 {ch['ch']} 章片段", cwd=workdir)


def concat_segments(ctx, workdir, names, out_name):
    """各片段編碼參數一致，可直接用 concat demuxer 串接不重編碼。"""
    listing = "".join(f"file '{n}'\n" for n in names)
    (Path(workdir) / "concat.txt").write_text(listing, encoding="utf-8")
    run_ffmpeg(ctx, ["-f", "concat", "-safe", "0", "-i", "concat.txt", "-c", "copy",
                     "-movflags", "+faststart", out_name], "串接精華版", cwd=workdir)


def load_highlight_inputs(ctx):
    narration = load_json(ctx.narration_json, "精華版旁白")
    for key in ("intro", "outro", "chapters"):
        if key not in narration:
            raise VideoError(f"highlight.json 缺少欄位 {key}：{ctx.narration_json}")
    offset_path = ctx.out_dir / "composite_offset.json"
    composite = ctx.out_dir / "composite.mp4"
    require_file(composite, "請先執行 full 子指令")
    offset = load_json(offset_path, "請先執行 full 子指令")
    return narration, composite, offset


def chapter_source(clip, composite, composite_dur, offset_epoch):
    """把片段的絕對時間換成 composite.mp4 內的位置：回傳 (source, 說明文字)。"""
    abs_start, abs_end = clip
    rel, take = source_window(abs_start, abs_end, offset_epoch, composite_dur)
    return (composite, rel, take), f"composite.mp4 {rel:.1f}s 起 {take:.1f}s"


def build_chapter_segments(ctx, workdir, narration, composite, offset, timeline):
    """回傳 [(片段檔名, 章標題或 None)]，片頭片尾以 None 表示。"""
    composite_dur = probe_duration(ctx, composite)
    segments = []
    for ch in load_chapters(ctx):
        code = ch["ch"]
        if code not in timeline:
            print(f"警告：第 {code} 章沒有 open 事件，精華版略過", file=sys.stderr)
            continue
        text = narration["chapters"].get(code)
        if not text:
            raise VideoError(f"highlight.json 缺少第 {code} 章旁白")
        mp3 = f"ch{code}.mp3"
        synthesize(ctx, text, mp3, workdir)
        seconds = max(probe_duration(ctx, Path(workdir) / mp3) + VOICE_PAD_SEC, MIN_CHAPTER_SEC)
        clip = plan_clip(timeline[code], int(ch.get("highlight", 1)), seconds)
        source, desc = chapter_source(clip, composite, composite_dur, offset["offset_epoch"])
        out_name = f"seg_{code}.mp4"
        print(f"第 {code} 章：{seconds:.1f} 秒，取 {desc}")
        render_chapter_segment(ctx, workdir, ch, mp3, seconds, source, out_name)
        segments.append((out_name, chapter_title(ch)))
    return segments


def build_card_segment(ctx, workdir, key, text, subtitle, min_sec):
    mp3 = f"{key}.mp3"
    synthesize(ctx, text, mp3, workdir)
    seconds = max(probe_duration(ctx, Path(workdir) / mp3) + VOICE_PAD_SEC, min_sec)
    png = f"{key}.png"
    make_title_card(Path(workdir) / png, subtitle)
    render_card_segment(ctx, workdir, png, mp3, seconds, f"seg_{key}.mp4")
    return f"seg_{key}.mp4"


def cmd_highlight(ctx):
    narration, composite, offset = load_highlight_inputs(ctx)
    events = parse_events(ctx.events_log)
    timeline = build_timeline(events)
    with work_dir(ctx) as workdir:
        intro = build_card_segment(ctx, workdir, "intro", narration["intro"],
                                   "雙視窗演練・精華版", INTRO_CARD_SEC)
        chapter_segs = build_chapter_segments(ctx, workdir, narration, composite, offset,
                                              timeline)
        outro = build_card_segment(ctx, workdir, "outro", narration["outro"],
                                   "完整版與提示詞影片請見播放清單", INTRO_CARD_SEC)
        names = [intro] + [n for n, _ in chapter_segs] + [outro]
        entries, cursor = [], probe_duration(ctx, Path(workdir) / intro)
        for name, title in chapter_segs:
            entries.append((cursor, title))
            cursor += probe_duration(ctx, Path(workdir) / name)
        concat_segments(ctx, workdir, names, "highlight.mp4")
        final = ctx.out_dir / f"{HIGHLIGHT_NAME}.mp4"
        shutil.move(str(Path(workdir) / "highlight.mp4"), str(final))
    write_chapters_file(ctx.out_dir / f"{HIGHLIGHT_NAME}-chapters.txt", entries)
    print(f"精華版完成：{final}")
    return final


# ================================================================ prompts

def prompt_video_path(ctx, code):
    return ctx.out_dir / "prompts" / f"K135-提示詞-ch{code}.mp4"


def cmd_prompts(ctx):
    require_file(ctx.caption_tool, "請從 kindle-120 複製 make_caption_video.py")
    failures = []
    for ch in load_chapters(ctx):
        code = ch["ch"]
        txt = ctx.prompts_dir / f"ch{code}.txt"
        out = prompt_video_path(ctx, code)
        if not txt.is_file():
            failures.append(f"第 {code} 章缺提示詞稿：{txt}")
            continue
        if out.is_file() and out.stat().st_mtime > txt.stat().st_mtime and not ctx.force:
            print(f"略過第 {code} 章（影片比稿新，--force 可重做）")
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        title = f"K135 {chapter_title(ch)}｜提示詞與指令"
        print(f"產生第 {code} 章提示詞影片…")
        try:
            run_cmd([sys.executable, str(ctx.caption_tool), str(txt), "--out", str(out),
                     "--title", title], f"第 {code} 章提示詞影片")
        except VideoError as exc:
            failures.append(str(exc))
    if failures:
        raise VideoError("提示詞影片有 {} 章失敗：\n".format(len(failures)) + "\n".join(failures))
    print("提示詞影片全部完成")


# ================================================================ manifest

INTRO_TEXT = ("《ROS 2 from Scratch》（K135）讀書演練：在 Windows 11 的 WSL2 裝好 ROS 2 Jazzy，"
              "用雙視窗方式逐章實作——左邊是教練視窗、右邊是練習終端機。")


def read_chapters_text(path):
    return Path(path).read_text(encoding="utf-8").strip() if Path(path).is_file() else ""


def build_description(kind_line, chapters_text=""):
    parts = [INTRO_TEXT, kind_line]
    if chapters_text:
        parts.append("章節：\n" + chapters_text)
    parts.append(f"演練腳本與教材：{REPO_URL}")
    return "\n\n".join(parts)


def build_manifest_entries(ctx):
    out = ctx.out_dir
    entries = [
        {"key": "full", "file": str((out / f"{FULL_NAME}.mp4").resolve()),
         "title": "K135 ROS 2 from Scratch｜雙視窗演練 完整版",
         "description": build_description(
             "這是完整版，從第 1 章到第 13 章不剪接，畫面為教練與練習兩個視窗並排。",
             read_chapters_text(out / f"{FULL_NAME}-chapters.txt")),
         "playlist": "full"},
        {"key": "highlight", "file": str((out / f"{HIGHLIGHT_NAME}.mp4").resolve()),
         "title": "K135 ROS 2 from Scratch｜雙視窗演練 精華版",
         "description": build_description(
             "這是精華版，每章挑一段重點畫面配上旁白說明，教練與練習兩個視窗左右並排。",
             read_chapters_text(out / f"{HIGHLIGHT_NAME}-chapters.txt")),
         "playlist": "highlight"},
    ]
    for ch in load_chapters(ctx):
        entries.append({
            "key": f"prompt-{ch['ch']}",
            "file": str(prompt_video_path(ctx, ch["ch"]).resolve()),
            "title": f"K135 {chapter_title(ch)}｜提示詞與指令",
            "description": build_description(
                f"本片整理{chapter_title(ch)}演練時使用的提示詞與指令，搭配語音與字幕。"),
            "playlist": "prompts"})
    return entries


def cmd_manifest(ctx):
    entries = build_manifest_entries(ctx)
    for entry in entries:
        if not Path(entry["file"]).is_file():
            print(f"警告：影片尚未產生，上傳時會失敗：{entry['file']}", file=sys.stderr)
    ctx.out_dir.mkdir(parents=True, exist_ok=True)
    path = ctx.out_dir / "upload_manifest.json"
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"上傳清單完成：{path}（{len(entries)} 支）")
    return path


# ================================================================ 共用

class work_dir:
    """暫存工作目錄（ASCII 路徑）；--keep-workdir 時保留供除錯。"""

    def __init__(self, ctx):
        self.ctx = ctx
        self.path = None

    def __enter__(self):
        self.path = tempfile.mkdtemp(prefix="k135vid_")
        return self.path

    def __exit__(self, exc_type, exc, tb):
        if self.ctx.keep_workdir or exc_type is not None:
            print(f"工作目錄保留於：{self.path}", file=sys.stderr)
        else:
            shutil.rmtree(self.path, ignore_errors=True)
        return False


def cmd_all(ctx):
    cmd_full(ctx)
    cmd_highlight(ctx)
    cmd_prompts(ctx)
    cmd_manifest(ctx)


COMMANDS = {"full": cmd_full, "highlight": cmd_highlight, "prompts": cmd_prompts,
            "manifest": cmd_manifest, "all": cmd_all}


# ================================================================ self-test

def iso(base, offset):
    return datetime.fromtimestamp(base + offset).astimezone().isoformat(timespec="milliseconds")


def write_fake_events(path, base):
    rows = [(0.0, "rec_start", "m2 m2.mkv"), (1.5, "rec_start", "m3 m3.mkv"),
            (5.0, "open", "ch01"),
            (9.0, "enter", "第 1 章演練 (1/5) 觀念"), (12.0, "enter", "第 1 章演練 (2/5) 環境變數"),
            (15.0, "enter", "第 1 章演練 (3/5) doctor"), (18.0, "enter", "第 1 章演練 (4/5) talker"),
            (19.0, "enter", "第 1 章演練 (4/5) talker"),  # 模擬按鍵重送
            (25.0, "close", "ch01"),
            (28.0, "open", "03"), (40.0, "enter", "第 3 章演練 (1/7) Topic：節點之間單向傳資料"),
            (55.0, "close", "03"), (58.0, "rec_stop", "m2 m2.mp4 原因=flag")]
    lines = [f"{iso(base, t)}\t{name}\t{content}" for t, name, content in rows]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_fake_inputs(ctx, root):
    raw = root / "raw"
    raw.mkdir(parents=True)
    run_ffmpeg(ctx, ["-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=30", "-t", "60",
                     "-c:v", "libx264", "-preset", "ultrafast", str(raw / "m2.mp4")], "假 m2")
    run_ffmpeg(ctx, ["-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30", "-t", "60",
                     "-c:v", "libx264", "-preset", "ultrafast", str(raw / "m3.mp4")], "假 m3")
    (raw / "session.json").write_text(json.dumps({"m2": {"file": "m2.mkv"}, "m3": {"file": "m3.mkv"}}),
                                      encoding="utf-8")
    write_fake_events(root / "events.log", time.time() - 3600)
    drill = {"chapters": [
        {"ch": "01", "name": "ROS 2 是什麼", "sections": 5, "gui": False, "highlight": 4, "keys": []},
        {"ch": "03", "name": "核心概念：turtlesim 很長很長的章名測試換行效果", "sections": 7,
         "gui": True, "highlight": 2, "keys": []}]}
    (root / "drill.json").write_text(json.dumps(drill, ensure_ascii=False), encoding="utf-8")
    narration = {"intro": "自我測試片頭。", "outro": "自我測試片尾。",
                 "chapters": {"01": "第一章測試。", "03": "第三章測試。"}}
    (root / "highlight.json").write_text(json.dumps(narration, ensure_ascii=False), encoding="utf-8")


def self_test():
    root = Path(tempfile.mkdtemp(prefix="k135selftest_"))
    ctx = Context(out_dir=root / "out", events_log=root / "events.log", raw_dir=root / "raw",
                  drill_json=root / "drill.json", narration_json=root / "highlight.json",
                  tts_silent_fallback=True)
    try:
        assert fmt_ts(0) == "0:00" and fmt_ts(65.9) == "1:05" and fmt_ts(3725) == "1:02:05"
        # 雙視窗版面：寬 882、整組水平置中、兩框不重疊且都在橫幅下方與畫面內
        assert WIN_W == 882, WIN_W
        coach_x, practice_x, top_y = dual_window_positions()
        box_w, box_h = WIN_W + 2 * WIN_BORDER, WIN_H + 2 * WIN_BORDER
        assert coach_x + box_w + WIN_GAP == practice_x, (coach_x, practice_x)
        assert abs(coach_x - (W - practice_x - box_w)) <= 1, (coach_x, practice_x)
        assert top_y >= BANNER_H and top_y + box_h <= H, top_y
        layout = dual_window_layout(12.0, 10.0)
        assert "crop=942:1004:8:0" in layout and "crop=942:1004:970:0" in layout, layout
        make_fake_inputs(ctx, root)
        # 片段取段落最後 N 秒：重送的 enter 取最後一筆（19s），不足時從段落開始（15s）起剪
        timeline = build_timeline(parse_events(ctx.events_log))
        base = timeline["01"]["open"] - 5.0
        c1 = plan_clip(timeline["01"], 4, 10.0)
        assert abs(c1[0] - (base + 15)) < 0.01 and abs(c1[1] - (base + 18)) < 0.01, c1
        c3 = plan_clip(timeline["03"], 2, 10.0)  # 最後一段找不到 (2/ → 用 close 55s
        assert abs(c3[0] - (base + 44)) < 0.01 and abs(c3[1] - (base + 54)) < 0.01, c3
        full = cmd_full(ctx)
        full_lines = (ctx.out_dir / f"{FULL_NAME}-chapters.txt").read_text(encoding="utf-8").splitlines()
        assert full_lines[0] == "0:00 開場", full_lines
        # 片頭 4 秒 + (open 01 在 5s − 裁切起點 2s) = 7 秒
        assert full_lines[1].startswith("0:07 第 1 章"), full_lines
        full_dur = probe_duration(ctx, full)
        assert 58 <= full_dur <= 62, full_dur  # 4 + (58 − 2)
        high = cmd_highlight(ctx)
        high_lines = (ctx.out_dir / f"{HIGHLIGHT_NAME}-chapters.txt").read_text(encoding="utf-8").splitlines()
        assert high_lines[0] == "0:00 開場" and len(high_lines) == 3, high_lines
        assert probe_duration(ctx, high) >= INTRO_CARD_SEC * 2 + MIN_CHAPTER_SEC * 2 - 1
        print("SELF-TEST PASS")
        print(f"（產物在 {root}）")
        return 0
    except (AssertionError, VideoError) as exc:
        print(f"SELF-TEST FAIL：{exc!r}", file=sys.stderr)
        print(f"（暫存目錄保留於 {root}）", file=sys.stderr)
        return 1


# ================================================================ main

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="K135 雙視窗演練影片製作")
    parser.add_argument("command", nargs="?", choices=sorted(COMMANDS), help="子指令")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="輸出目錄")
    parser.add_argument("--force", action="store_true", help="prompts：已存在也重做")
    parser.add_argument("--keep-workdir", action="store_true", help="保留暫存工作目錄")
    parser.add_argument("--self-test", action="store_true", help="用假資料驗證 full／highlight 流程")
    args = parser.parse_args(argv)
    if not args.self_test and not args.command:
        parser.error("請指定子指令或 --self-test")
    return args


def main():
    args = parse_args()
    if args.self_test:
        sys.exit(self_test())
    ctx = Context(out_dir=Path(args.out).expanduser(), force=args.force,
                  keep_workdir=args.keep_workdir)
    try:
        COMMANDS[args.command](ctx)
    except VideoError as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("已中斷", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()

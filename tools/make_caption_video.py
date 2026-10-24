"""把教學旁白稿（.txt/.md）轉成「語音＋同步字幕」的 MP4，可選擇直接用 VLC 播放。

用法：
    python make_caption_video.py <narration.txt> --out <out.mp4> [--title 標題]
        [--voice zh-TW-HsiaoChenNeural] [--play] [--keep-workdir]
        [--font PATH] [--font-bold PATH]
    python make_caption_video.py --self-test

設計重點：
- 逐句用 edge-tts 合成，再用 ffprobe 量每句時長，字幕時間軸因此與語音精準對齊。
- ffmpeg 濾鏡寫成腳本檔＋textfile 相對檔名，避開命令列跳脫與中文路徑問題。
- 工作目錄放系統暫存區的 ASCII 路徑，最後才把成品搬到使用者指定（可能含中文）的路徑。
"""
import argparse
import glob
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

DEFAULT_VOICE = "zh-TW-HsiaoChenNeural"
MAX_CHUNK_CHARS = 40
MAX_LINE_WIDTH = 22.0
WRAP_LOOKBACK = 10
TTS_RETRIES = 3
TTS_RETRY_DELAY_SEC = 2
PUNCT = "，。、：；！？」』"
SENTENCE_RE = re.compile(r"[^。！？]+[。！？]?")
CLAUSE_RE = re.compile(r"[^，、：]+[，、：]?")


class CaptionVideoError(Exception):
    """可預期的流程錯誤（相依缺失、子程序失敗等），由 main() 統一印出。"""


# ---------------------------------------------------------------- 切句

def split_long_sentence(sentence):
    """超過 40 字的句子依逗號類標點再切，累積到不超過 40 字為一段。"""
    chunks, cur = [], ""
    for part in CLAUSE_RE.findall(sentence):
        if cur and len(cur) + len(part) > MAX_CHUNK_CHARS:
            chunks.append(cur.strip())
            cur = part
        else:
            cur += part
    if cur.strip():
        chunks.append(cur.strip())
    return chunks


def split_paragraph(paragraph):
    """把一段文字切成字幕 chunk 清單。"""
    chunks = []
    for sentence in SENTENCE_RE.findall(paragraph):
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) > MAX_CHUNK_CHARS:
            chunks.extend(split_long_sentence(sentence))
        else:
            chunks.append(sentence)
    return chunks


def load_chunks(narration_path):
    """讀旁白稿（以行為段落、忽略空行），回傳全部字幕 chunk。"""
    text = Path(narration_path).read_text(encoding="utf-8")
    chunks = []
    for line in text.splitlines():
        if line.strip():
            chunks.extend(split_paragraph(line.strip()))
    return chunks


# ---------------------------------------------------------------- 斷行

def char_width(ch):
    """英數半形字只佔約半個中文字寬，用 0.55 估算才不會過早斷行。"""
    return 0.55 if ord(ch) < 128 else 1.0


def line_width(text):
    return sum(char_width(ch) for ch in text)


def is_word_char(ch):
    """英文單字/指令/路徑（ros2、cmd_vel、/turtle1/cmd_vel、--help）不可從中切開。"""
    return ch.isascii() and (ch.isalnum() or ch in "_./-")


def find_word_safe_break(cur, next_ch):
    """由行尾往前找第一個不落在英文單字中間的斷點；整行都是同一個單字時回傳 None。"""
    for idx in range(len(cur), 0, -1):
        right = cur[idx] if idx < len(cur) else next_ch
        if not (is_word_char(cur[idx - 1]) and is_word_char(right)):
            return idx
    return None


def break_current_line(cur, next_ch=""):
    """先在最後 10 字內找標點斷開；找不到再退回單字邊界；單字本身超過一行才硬切。"""
    start = max(0, len(cur) - WRAP_LOOKBACK)
    for idx in range(len(cur) - 1, start - 1, -1):
        if cur[idx] in PUNCT:
            return cur[:idx + 1], cur[idx + 1:]
    idx = find_word_safe_break(cur, next_ch)
    if idx is None:
        return cur, ""
    return cur[:idx], cur[idx:]


def fix_leading_punct(lines):
    """行首標點挪回上一行，並去頭尾空白、移除空行。"""
    fixed = []
    for line in (ln.strip() for ln in lines):
        while fixed and line and line[0] in PUNCT:
            fixed[-1] += line[0]
            line = line[1:].strip()
        if line:
            fixed.append(line)
    return fixed


def wrap_text(text, max_width=MAX_LINE_WIDTH):
    """依顯示寬度斷行；標點本身超寬也不斷，避免它跑到下一行行首。"""
    lines, cur = [], ""
    for ch in text:
        if line_width(cur) + char_width(ch) > max_width and ch not in PUNCT and cur:
            done, cur = break_current_line(cur, ch)
            lines.append(done)
        cur += ch
    if cur:
        lines.append(cur)
    return fix_leading_punct(lines)


# ---------------------------------------------------------------- 環境

def check_dependencies():
    """開工前一次列出所有缺少的相依，避免跑到一半才失敗。"""
    missing = [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]
    try:
        proc = subprocess.run([sys.executable, "-m", "edge_tts", "--help"],
                              capture_output=True, encoding="utf-8", errors="replace",
                              timeout=60)
        if proc.returncode != 0:
            missing.append("edge-tts（請執行：python -m pip install edge-tts）")
    except (OSError, subprocess.TimeoutExpired):
        missing.append("edge-tts（請執行：python -m pip install edge-tts）")
    if missing:
        raise CaptionVideoError("缺少相依：\n  - " + "\n  - ".join(missing))


def default_fonts():
    """依作業系統回傳 (一般字型, 粗體字型)；找不到回傳 (None, None)。"""
    system = platform.system()
    if system == "Windows":
        windir = os.environ.get("WINDIR")
        if not windir:
            return None, None
        fonts_dir = Path(windir) / "Fonts"
        return fonts_dir / "msjh.ttc", fonts_dir / "msjhbd.ttc"
    if system == "Darwin":
        pingfang = Path("/System/Library/Fonts/PingFang.ttc")
        return pingfang, pingfang
    candidates = sorted(glob.glob("/usr/share/fonts/**/NotoSansCJK*.ttc", recursive=True))
    if not candidates:
        return None, None
    regular = next((c for c in candidates if "Regular" in c), candidates[0])
    bold = next((c for c in candidates if "Bold" in c), regular)
    return Path(regular), Path(bold)


def resolve_fonts(font_arg, font_bold_arg):
    """命令列參數優先，否則用系統預設；任何一個不存在就明確報錯。"""
    regular, bold = default_fonts()
    regular = Path(font_arg) if font_arg else regular
    bold = Path(font_bold_arg) if font_bold_arg else (bold or regular)
    for label, path in (("一般字型", regular), ("粗體字型", bold)):
        if path is None or not Path(path).is_file():
            raise CaptionVideoError(f"找不到{label}：{path}（可用 --font / --font-bold 指定）")
    return regular, bold


def ffmpeg_font_path(path):
    """ffmpeg 濾鏡語法裡冒號是分隔符，Windows 磁碟機冒號必須跳脫。"""
    return str(Path(path).resolve()).replace("\\", "/").replace(":", "\\:")


# ---------------------------------------------------------------- 子程序

def run_cmd(cmd, workdir, desc, timeout=600):
    """執行子程序，失敗時帶 stderr 末段拋出，讓使用者知道是哪一步壞掉。"""
    try:
        proc = subprocess.run(cmd, cwd=workdir, capture_output=True, encoding="utf-8",
                              errors="replace", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CaptionVideoError(f"{desc} 執行失敗：{exc}") from exc
    if proc.returncode != 0:
        raise CaptionVideoError(f"{desc} 失敗（exit {proc.returncode}）：{proc.stderr[-300:]}")
    return proc.stdout


def synthesize_chunk(index, chunk, voice, workdir):
    """edge-tts 偶發網路失敗，所以每句最多重試 3 次。"""
    mp3_name = f"s{index:03d}.mp3"
    cmd = [sys.executable, "-m", "edge_tts", "--voice", voice,
           "--text", chunk, "--write-media", mp3_name]
    last_error = ""
    for attempt in range(1, TTS_RETRIES + 1):
        try:
            run_cmd(cmd, workdir, "edge-tts", timeout=120)
            return mp3_name
        except CaptionVideoError as exc:
            last_error = str(exc)
            if attempt < TTS_RETRIES:
                time.sleep(TTS_RETRY_DELAY_SEC)
    raise CaptionVideoError(
        f"第 {index + 1} 句語音合成失敗（已重試 {TTS_RETRIES} 次）\n"
        f"  句子：{chunk}\n  錯誤：{last_error[-300:]}")


def probe_duration(mp3_name, workdir):
    out = run_cmd(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                   "-of", "csv=p=0", mp3_name], workdir, f"ffprobe {mp3_name}")
    try:
        return float(out.strip())
    except ValueError as exc:
        raise CaptionVideoError(f"無法解析 {mp3_name} 的時長：{out!r}") from exc


def synthesize_all(chunks, voice, workdir):
    """逐句合成並累加時長，回傳 [(mp3, start, end), ...]。"""
    timings, cursor = [], 0.0
    for index, chunk in enumerate(chunks):
        print(f"  合成 {index + 1}/{len(chunks)}：{chunk}", flush=True)
        mp3_name = synthesize_chunk(index, chunk, voice, workdir)
        duration = probe_duration(mp3_name, workdir)
        timings.append((mp3_name, cursor, cursor + duration))
        cursor += duration
    return timings


# ---------------------------------------------------------------- 產生影片

def write_text(path, content):
    Path(path).write_text(content, encoding="utf-8", newline="\n")


def build_filter_script(timings, fonts, total_sec):
    """組 filter_complex 腳本；進度條用 overlay+eval=frame，因 drawbox 不能隨 t 動畫。"""
    regular, bold = (ffmpeg_font_path(f) for f in fonts)
    filters = [f"drawtext=fontfile='{bold}':textfile=title.txt:fontsize=30:"
               "fontcolor=0x89b4fa:x=(w-text_w)/2:y=40"]
    for index, (_, start, end) in enumerate(timings):
        filters.append(
            f"drawtext=fontfile='{regular}':textfile=c{index:03d}.txt:fontsize=44:"
            "fontcolor=white:line_spacing=14:x=(w-text_w)/2:y=(h-text_h)/2:"
            f"enable='between(t,{start:.3f},{end:.3f})'")
    return ("[0:v]" + ",\n".join(filters) + "[bg];\n"
            f"[bg][2:v]overlay=x='-w+W*t/{total_sec:.3f}':y=H-12:eval=frame[v]\n")


def write_assets(chunks, timings, title, fonts, workdir):
    """寫字幕檔、標題檔、濾鏡腳本與 concat 清單。"""
    for index, chunk in enumerate(chunks):
        write_text(Path(workdir) / f"c{index:03d}.txt", "\n".join(wrap_text(chunk)))
    write_text(Path(workdir) / "title.txt", title)
    total_sec = timings[-1][2]
    write_text(Path(workdir) / "filters_complex.txt",
               build_filter_script(timings, fonts, total_sec))
    write_text(Path(workdir) / "concat.txt",
               "".join(f"file '{mp3}'\n" for mp3, _, _ in timings))
    return total_sec


def render_video(workdir):
    run_cmd(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", "concat.txt",
             "-c:a", "aac", "-b:a", "128k", "narration.m4a"], workdir, "ffmpeg 合併音訊")
    run_cmd(["ffmpeg", "-v", "error", "-y",
             "-f", "lavfi", "-i", "color=c=0x1e1e2e:s=1280x720:r=24",
             "-i", "narration.m4a",
             "-f", "lavfi", "-i", "color=c=0xa6e3a1:s=1280x12:r=24",
             "-/filter_complex", "filters_complex.txt",  # ffmpeg 9 已移除 -filter_complex_script，「-/」前綴是 7.0 起的讀檔寫法
             "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast",
             "-tune", "stillimage", "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest",
             "out.mp4"], workdir, "ffmpeg 產生影片", timeout=3600)


def move_output(workdir, out_path):
    """先在 ASCII 工作目錄產出再搬到目的地，避開 ffmpeg 處理中文路徑參數的問題。"""
    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()
    shutil.move(str(Path(workdir) / "out.mp4"), str(out_path))
    return out_path


# ---------------------------------------------------------------- 播放

def find_vlc():
    found = shutil.which("vlc")
    if found:
        return found
    candidates = [Path("/Applications/VLC.app/Contents/MacOS/VLC")]
    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(env_name)
        if base:
            candidates.append(Path(base) / "VideoLAN" / "VLC" / "vlc.exe")
    return next((str(c) for c in candidates if c.is_file()), None)


def play_video(mp4_path):
    """背景啟動不等待；沒有 VLC 時退回系統預設播放器而不是失敗。"""
    vlc = find_vlc()
    try:
        if vlc:
            subprocess.Popen([vlc, "--play-and-exit", "--no-video-title-show", str(mp4_path)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        print("提示：找不到 VLC，改用系統預設播放器開啟。")
        if platform.system() == "Windows":
            os.startfile(str(mp4_path))  # 只在 Windows 存在
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", str(mp4_path)])
        else:
            subprocess.Popen(["xdg-open", str(mp4_path)])
    except OSError as exc:
        print(f"警告：無法啟動播放器：{exc}", file=sys.stderr)


# ---------------------------------------------------------------- 主流程

def build_video(args, chunks, fonts, workdir):
    title = args.title or Path(args.narration).stem
    timings = synthesize_all(chunks, args.voice, workdir)
    total_sec = write_assets(chunks, timings, title, fonts, workdir)
    print("  產生影片中…", flush=True)
    render_video(workdir)
    out_path = move_output(workdir, args.out)
    print(f"完成：{len(chunks)} 句，總長 {total_sec:.1f} 秒")
    print(f"輸出：{out_path}")
    return out_path


def run_pipeline(args):
    if not args.narration or not args.out:
        raise CaptionVideoError("必須提供旁白稿路徑與 --out（或改用 --self-test）")
    if not Path(args.narration).is_file():
        raise CaptionVideoError(f"找不到旁白稿：{args.narration}")
    chunks = load_chunks(args.narration)
    if not chunks:
        raise CaptionVideoError(f"旁白稿沒有任何可用文字：{args.narration}")
    fonts = resolve_fonts(args.font, args.font_bold)
    check_dependencies()
    workdir = tempfile.mkdtemp(prefix="capvid_")
    try:
        out_path = build_video(args, chunks, fonts, workdir)
    finally:
        if args.keep_workdir:
            print(f"工作目錄保留於：{workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)
    if args.play:
        play_video(out_path)


def self_test():
    """純函式測試：切句、長句切分、斷行；不需網路與 ffmpeg。"""
    assert split_paragraph("第一句。第二句！第三句？") == ["第一句。", "第二句！", "第三句？"]
    assert split_paragraph("沒有結尾標點") == ["沒有結尾標點"]
    long_sentence = "這是一個非常長的句子用來測試切分，" * 4 + "最後結尾。"
    long_chunks = split_paragraph(long_sentence)
    assert len(long_chunks) > 1, long_chunks
    assert all(len(c) <= MAX_CHUNK_CHARS for c in long_chunks), long_chunks
    assert "".join(long_chunks) == long_sentence
    lines = wrap_text("輸入驚嘆號就會切換到 shell 模式，指令會直接執行")
    assert len(lines) == 2, lines
    assert lines[0].endswith("模式，"), lines
    assert all(ln[0] not in PUNCT for ln in lines), lines
    assert not any(ln.endswith("模") for ln in lines), lines
    for ln in wrap_text("一二三四五六七八九十一二三四五六七八九十一二」，然後繼續說明。"):
        assert ln[0] not in PUNCT, ln
    ros_text = "再用 ros2 topic pub 對 turtle1 的 cmd vel 發速度，小烏龜就會動。"
    ros_lines = wrap_text(ros_text)
    assert "".join(ros_lines).replace(" ", "") == ros_text.replace(" ", ""), ros_lines
    for word in re.findall(r"[A-Za-z0-9_./-]+", ros_text):
        assert any(word in ln for ln in ros_lines), (word, ros_lines)
    print("SELF_TEST_PASS")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="旁白稿 → 語音＋同步字幕 MP4")
    parser.add_argument("narration", nargs="?", help="旁白稿 .txt/.md（UTF-8）")
    parser.add_argument("--out", help="輸出 MP4 路徑")
    parser.add_argument("--title", help="畫面標題（預設為旁白稿檔名）")
    parser.add_argument("--voice", default=DEFAULT_VOICE, help="edge-tts 語音")
    parser.add_argument("--play", action="store_true", help="完成後用 VLC 播放")
    parser.add_argument("--keep-workdir", action="store_true", help="保留工作目錄供除錯")
    parser.add_argument("--font", help="字幕字型路徑")
    parser.add_argument("--font-bold", help="標題粗體字型路徑")
    parser.add_argument("--self-test", action="store_true", help="只跑純函式測試")
    return parser.parse_args(argv)


def main():
    try:
        args = parse_args()
        if args.self_test:
            self_test()
            return
        run_pipeline(args)
    except AssertionError as exc:
        print(f"SELF_TEST_FAIL：{exc}", file=sys.stderr)
        sys.exit(1)
    except (CaptionVideoError, OSError, UnicodeDecodeError) as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

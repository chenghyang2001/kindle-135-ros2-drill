"""開一個 K135 導覽終端機視窗跑指定章節，並放到版面位置（在 Windows 的 Python 執行）。

用法：
    PYTHONUTF8=1 python tools/open_chapter.py NN [--layout m2right|m3]

    NN：01、03～13（沒有 02），"1" 會自動補成 "01"。
    m2right（預設）：終端機放螢幕 2 左半 (1920,0,960,1008)，圖形視窗由
                     ~/ros2-demo 複製檔指定開在螢幕 2 右半。
    m3：終端機佔滿螢幕 2 工作區 (1920,0,1920,1008)，圖形視窗在螢幕 3。

為什麼要先關舊視窗：同標題視窗有兩個時，搬移與後續操作會抓錯；
    只關標題以「K135 演練-」開頭的 Windows Terminal，不碰教練視窗或使用者自己的終端機。
為什麼不改 drill/ 原檔：drill/ 是已測過的三螢幕版；版面差異由 tools/apply-layout.py
    只套在 WSL 的 ~/ros2-demo 複製檔，本工具只負責終端機視窗的位置。
螢幕 1 絕對不放演練視窗（錄影只錄螢幕 2）。

依賴：pywin32（python -m pip install pywin32）、Windows Terminal（wt.exe）、WSL Ubuntu-24.04
"""
import argparse
import ctypes
import shutil
import subprocess
import sys
import time

try:
    import win32con
    import win32gui
except ImportError as exc:
    print(f"錯誤：缺少套件（{exc}），請執行：python -m pip install pywin32", file=sys.stderr)
    sys.exit(1)

# 必須在任何視窗座標操作前設定，否則 MoveWindow 的座標會被 DPI 縮放
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except (AttributeError, OSError):
    pass

TERMINAL_CLASS = "CASCADIA_HOSTING_WINDOW_CLASS"
TITLE_PREFIX = "K135 演練-"
WSL_DISTRO = "Ubuntu-24.04"
VALID_CHAPTERS = {"01"} | {f"{n:02d}" for n in range(3, 14)}
OPEN_TIMEOUT_SEC = 20

# 螢幕 2 工作區是 x 1920~3840、高 1008（扣工作列）
LAYOUT_RECTS = {
    "m2right": (1920, 0, 960, 1008),
    "m3": (1920, 0, 1920, 1008),
}
GUI_HINT = {
    "m2right": "圖形視窗會開在螢幕 2 右半",
    "m3": "圖形視窗會開在螢幕 3",
}


class OpenError(Exception):
    """可預期的失敗（章號不合法、wt.exe 不存在等），main 印訊息並 exit 1。"""


def normalize_chapter(raw: str) -> str:
    text = raw.strip()
    if not text.isdigit():
        raise OpenError(f"章號 {raw!r} 不合法，只接受 01、03～13")
    chapter = f"{int(text):02d}"
    if chapter not in VALID_CHAPTERS:
        raise OpenError(f"章號 {raw!r} 不合法，只接受 01、03～13（沒有 02）")
    return chapter


def find_terminal_windows(title_filter) -> list:
    """回傳 [(hwnd, title)]，只含 WT 頂層可見視窗且 title_filter(title) 為真。"""
    found = []

    def _enum(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        if win32gui.GetClassName(hwnd) != TERMINAL_CLASS:
            return True
        title = win32gui.GetWindowText(hwnd)
        if title_filter(title):
            found.append((hwnd, title))
        return True

    win32gui.EnumWindows(_enum, None)
    return found


def close_drill_windows() -> int:
    windows = find_terminal_windows(lambda t: t.startswith(TITLE_PREFIX))
    for hwnd, title in windows:
        try:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        except win32gui.error as exc:
            print(f"警告：關閉視窗「{title}」失敗：{exc}", file=sys.stderr)
    return len(windows)


def move_window(hwnd: int, rect: tuple) -> None:
    x, y, w, h = rect
    # 最大化狀態下 MoveWindow 不生效，先還原
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.MoveWindow(hwnd, x, y, w, h, True)


def launch_terminal(chapter: str, title: str) -> None:
    wt_path = shutil.which("wt.exe") or shutil.which("wt")
    if wt_path is None:
        raise OpenError("找不到 wt.exe，請先安裝 Windows Terminal（winget install Microsoft.WindowsTerminal）")
    # 參數不可含分號：wt 會把分號當命令分隔符
    cmd = [wt_path, "-w", "new", "new-tab", "--title", title, "--suppressApplicationTitle",
           "wsl.exe", "-d", WSL_DISTRO, "--cd", "~", "--", f"./ros2-demo/ch{chapter}.sh"]
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        raise OpenError(f"啟動 Windows Terminal 失敗（{wt_path}）：{exc}")


def wait_for_window(title: str):
    deadline = time.time() + OPEN_TIMEOUT_SEC
    while time.time() < deadline:
        windows = find_terminal_windows(lambda t: t == title)
        if windows:
            return windows[0][0]
        time.sleep(0.5)
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="開 K135 導覽終端機並放到版面位置")
    parser.add_argument("chapter", help="章號：01、03～13（1 會自動補成 01）")
    parser.add_argument("--layout", choices=sorted(LAYOUT_RECTS), default="m2right",
                        help="版面（預設 m2right）")
    return parser


def main() -> int:
    # 終端機是 cp950 時中文輸出會炸，統一改 UTF-8
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args()
    try:
        chapter = normalize_chapter(args.chapter)
        title = f"{TITLE_PREFIX}ch{chapter}"
        closed = close_drill_windows()
        if closed:
            print(f"已關閉 {closed} 個舊演練視窗")
            time.sleep(1)  # 等舊視窗真的消失，避免等候時抓到同標題的舊視窗
        launch_terminal(chapter, title)
    except OpenError as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 1

    hwnd = wait_for_window(title)
    if hwnd is None:
        print(f"警告：等候 {OPEN_TIMEOUT_SEC} 秒仍未出現「{title}」視窗，未搬移位置", file=sys.stderr)
        return 2
    rect = LAYOUT_RECTS[args.layout]
    time.sleep(0.5)  # 剛建立的視窗馬上搬會被 WT 自己的初始定位蓋掉
    try:
        move_window(hwnd, rect)
    except win32gui.error as exc:
        print(f"警告：搬移視窗失敗：{exc}", file=sys.stderr)
        return 2
    print(f"已開啟第 {chapter} 章「{title}」，位置 x={rect[0]} y={rect[1]} "
          f"寬={rect[2]} 高={rect[3]}（版面 {args.layout}）")
    print(f"提醒：{GUI_HINT[args.layout]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

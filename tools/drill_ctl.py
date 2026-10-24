"""K135 雙視窗演練控制器（在 Windows 的 Python 執行）。

教練視窗（Claude Code）透過本工具開「K135 練習-chNN」視窗、讀畫面、送 Enter，
讓錄影時練習視窗逐段前進。所有動作寫入事件檔，後製剪輯時用來對齊時間軸。

子指令：open NN｜place-coach｜screen [--lines N]｜next｜status｜close

為什麼讀畫面用 UIA：WT 的 TermControl 有提供 TextPattern，不必截圖 OCR。
為什麼送 Enter 用 wt-send.ps1：搶焦點與「使用者輸入保護」已在那支腳本維護，不重寫一份。

依賴：pywin32、pywinauto（python -m pip install pywin32 pywinauto）
"""
import argparse
import ctypes
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import win32con
    import win32gui
except ImportError as exc:
    print(f"錯誤：缺少套件（{exc}），請執行：python -m pip install pywin32 pywinauto",
          file=sys.stderr)
    sys.exit(1)

# 必須在任何視窗座標操作前設定，否則 MoveWindow 的座標會被 DPI 縮放
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except (AttributeError, OSError):
    pass

TERMINAL_CLASS = "CASCADIA_HOSTING_WINDOW_CLASS"
PRACTICE_PREFIX = "K135 練習-"
COACH_TAG = "K135 教練"
WSL_DISTRO = "Ubuntu-24.04"
VALID_CHAPTERS = {"01"} | {f"{n:02d}" for n in range(3, 14)}

# 螢幕 2 的工作區是 x 1920~3840、高 1008；左半教練、右半練習（螢幕 1 絕對不放）
COACH_RECT = (1920, 0, 960, 1008)
PRACTICE_RECT = (2880, 0, 960, 1008)
OPEN_TIMEOUT_SEC = 20

EVENTS_LOG = Path.home() / "Videos" / "kindle-drill" / "k135" / "events.log"
WT_SEND = Path.home() / ".claude" / "scripts" / "wt-send.ps1"

WAIT_MARK = "按 Enter 繼續"
DONE_MARK = "完成 ✅"
SECTION_RE = re.compile(r"第 (\d+) 章演練 \((\d+)/(\d+)\)")

# [x] 寫法讓 pkill -f 的樣式不會比對到這條 bash -c 命令列本身
WSL_CLEANUP = (
    "pkill -INT -f '[r]os2 launch'; sleep 2; "
    "pkill -f '[t]urtlesim_node|[t]urtle_controller|[n]umber_|[c]ount_until_|"
    "[r]obot_state_publisher|[r]viz2|[p]arameter_bridge|[g]z sim'; "
    "pkill -9 -f '[j]sp_gui_m3|[r]qt_graph'; true"
)


class DrillError(Exception):
    """可預期的操作失敗（找不到視窗等），main 會印訊息並 exit 1。"""


# ---------- 事件檔 ----------

def log_event(event: str, content: str) -> None:
    """寫一行事件：ISO8601<TAB>事件<TAB>內容（毫秒精度，供剪輯對齊）。"""
    try:
        EVENTS_LOG.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().astimezone().isoformat(timespec="milliseconds")
        with EVENTS_LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"{stamp}\t{event}\t{content}\n")
    except OSError as exc:
        # 事件檔寫不進去不應中斷演練，只警告
        print(f"警告：無法寫入事件檔 {EVENTS_LOG}：{exc}", file=sys.stderr)


# ---------- 視窗尋找 ----------

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


def find_practice_window():
    windows = find_terminal_windows(lambda t: t.startswith(PRACTICE_PREFIX))
    if not windows:
        raise DrillError(f"找不到標題以「{PRACTICE_PREFIX}」開頭的練習視窗（請先 open NN）")
    return windows[0]


def chapter_from_title(title: str):
    match = re.search(r"ch(\d{2})", title)
    return match.group(1) if match else None


def move_window(hwnd: int, rect: tuple) -> None:
    x, y, w, h = rect
    # 最大化狀態下 MoveWindow 不生效，先還原
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.MoveWindow(hwnd, x, y, w, h, True)


def close_practice_windows() -> int:
    windows = find_terminal_windows(lambda t: t.startswith(PRACTICE_PREFIX))
    for hwnd, _title in windows:
        try:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        except win32gui.error as exc:
            print(f"警告：關閉視窗 {hwnd} 失敗：{exc}", file=sys.stderr)
    return len(windows)


# ---------- 畫面讀取 ----------

def read_screen_text(hwnd: int) -> str:
    """用 UIA TextPattern 取練習視窗 TermControl 的全文。"""
    try:
        from pywinauto import Desktop
    except ImportError as exc:
        raise DrillError(f"缺少 pywinauto（{exc}），請執行：python -m pip install pywinauto")
    try:
        for win in Desktop(backend="uia").windows():
            if win.handle != hwnd:
                continue
            for ctrl in win.descendants():
                if ctrl.element_info.class_name == "TermControl":
                    return ctrl.iface_text.DocumentRange.GetText(-1)
    except Exception as exc:  # noqa: BLE001 — COM／UIA 例外型別不固定
        raise DrillError(f"讀取練習視窗內容失敗：{exc}")
    raise DrillError("練習視窗中找不到 TermControl 元件（視窗可能尚未完成載入）")


def non_empty_lines(text: str) -> list:
    lines = (line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"))
    return [line for line in lines if line.strip()]


def current_section_title(lines: list):
    """回傳 (標題行, 'k/n' 或 None)；找最後一個段落標題或含「完成」的標題行。"""
    for line in reversed(lines):
        match = SECTION_RE.search(line)
        if match:
            return line.strip(), f"{match.group(2)}/{match.group(3)}"
        if "完成" in line and "章演練" in line:
            return line.strip(), None
    return None, None


# ---------- WSL ----------

def wsl_cleanup() -> None:
    cmd = ["wsl.exe", "-d", WSL_DISTRO, "--", "bash", "-c", WSL_CLEANUP]
    try:
        subprocess.run(cmd, check=False, timeout=30, capture_output=True,
                       encoding="utf-8", errors="replace")
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"警告：WSL 清理殘留 ROS 程序失敗：{exc}", file=sys.stderr)


# ---------- 子指令 ----------

def cmd_open(args) -> int:
    chapter = args.chapter
    if chapter not in VALID_CHAPTERS:
        raise DrillError(f"章號 {chapter!r} 不合法，只接受兩位數 01、03~13")
    closed = close_practice_windows()
    if closed:
        print(f"已關閉 {closed} 個舊練習視窗")
        time.sleep(1)
    wsl_cleanup()

    title = f"{PRACTICE_PREFIX}ch{chapter}"
    # wt 會把分號當命令分隔符，args 內不可出現分號
    wt_args = (f"-w k135practice --pos 2890,10 new-tab --suppressApplicationTitle "
               f"--title \"{title}\" wsl.exe -d {WSL_DISTRO} --cd ~ -- "
               f"env DEMO_RECORD=1 ./ros2-demo/ch{chapter}.sh")
    ps_cmd = f"Start-Process wt.exe -ArgumentList '{wt_args}'"
    try:
        subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps_cmd],
                       check=True, timeout=30, capture_output=True,
                       encoding="utf-8", errors="replace")
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise DrillError(f"啟動 Windows Terminal 失敗：{exc}")

    deadline = time.time() + OPEN_TIMEOUT_SEC
    while time.time() < deadline:
        windows = find_terminal_windows(lambda t: t == title)
        if windows:
            hwnd = windows[0][0]
            time.sleep(0.5)  # 剛建立的視窗馬上搬會被 WT 自己的初始定位蓋掉
            move_window(hwnd, PRACTICE_RECT)
            log_event("open", f"ch{chapter}")
            print(f"已開啟「{title}」並放到螢幕 2 右半（hwnd={hwnd}）")
            return 0
        time.sleep(0.5)
    raise DrillError(f"等候 {OPEN_TIMEOUT_SEC} 秒仍未出現「{title}」視窗")


def cmd_place_coach(_args) -> int:
    windows = find_terminal_windows(lambda t: COACH_TAG in t)
    if not windows:
        raise DrillError(f"找不到標題含「{COACH_TAG}」的 Windows Terminal 視窗")
    hwnd, title = windows[0]
    move_window(hwnd, COACH_RECT)
    print(f"已把「{title}」放到螢幕 2 左半")
    return 0


def cmd_screen(args) -> int:
    if args.lines <= 0:
        raise DrillError("--lines 必須是正整數")
    hwnd, _title = find_practice_window()
    lines = non_empty_lines(read_screen_text(hwnd))
    print("\n".join(lines[-args.lines:]))
    return 0


def cmd_next(_args) -> int:
    hwnd, title = find_practice_window()
    lines = non_empty_lines(read_screen_text(hwnd))
    if not lines or WAIT_MARK not in lines[-1]:
        print("目前不在等待 Enter（腳本仍在執行或已完成），未送出")
        return 2
    section_line, _ = current_section_title(lines)
    if not WT_SEND.is_file():
        raise DrillError(f"找不到送鍵腳本：{WT_SEND}")
    log_event("enter", section_line or f"{chapter_from_title(title) or '?'}（無標題行）")
    cmd = ["powershell.exe", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass",
           "-File", str(WT_SEND), "-Title", f"{PRACTICE_PREFIX}ch", "-Enter", "1"]
    try:
        result = subprocess.run(cmd, check=False, timeout=30, capture_output=True,
                                encoding="utf-8", errors="replace")
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DrillError(f"呼叫 wt-send.ps1 失敗：{exc}")
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise DrillError(f"wt-send.ps1 未送出（exit {result.returncode}）：{detail}")
    print(f"已送出 Enter（{section_line or '未知段落'}）")
    return 0


def cmd_status(_args) -> int:
    hwnd, title = find_practice_window()
    lines = non_empty_lines(read_screen_text(hwnd))
    _, section = current_section_title(lines)
    chapter = chapter_from_title(title)
    status = {
        "chapter": int(chapter) if chapter is not None else None,
        "section": section,
        "waiting_enter": bool(lines) and WAIT_MARK in lines[-1],
        "done": any(DONE_MARK in line for line in lines),
    }
    print(json.dumps(status, ensure_ascii=False))
    return 0


def cmd_close(_args) -> int:
    windows = find_terminal_windows(lambda t: t.startswith(PRACTICE_PREFIX))
    chapters = ",".join(chapter_from_title(t) or "?" for _, t in windows)
    closed = close_practice_windows()
    wsl_cleanup()
    log_event("close", f"ch{chapters}" if closed else "（無練習視窗）")
    print(f"已關閉 {closed} 個練習視窗並清理 WSL 殘留程序")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="K135 雙視窗演練控制器（教練操作練習視窗用）")
    sub = parser.add_subparsers(dest="command", required=True)

    p_open = sub.add_parser("open", help="開啟「K135 練習-chNN」並放到螢幕 2 右半")
    p_open.add_argument("chapter", help="兩位數章號：01、03~13")
    p_open.set_defaults(func=cmd_open)

    sub.add_parser("place-coach", help="把「K135 教練」視窗放到螢幕 2 左半").set_defaults(func=cmd_place_coach)

    p_screen = sub.add_parser("screen", help="印出練習視窗最後 N 個非空行")
    p_screen.add_argument("--lines", type=int, default=25, help="行數（預設 25）")
    p_screen.set_defaults(func=cmd_screen)

    sub.add_parser("next", help="畫面在等待 Enter 時送 Enter（否則 exit 2）").set_defaults(func=cmd_next)
    sub.add_parser("status", help="以 JSON 印出目前章節／段落／狀態").set_defaults(func=cmd_status)
    sub.add_parser("close", help="關閉練習視窗並清理 WSL 殘留 ROS 程序").set_defaults(func=cmd_close)
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
        return args.func(args)
    except DrillError as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

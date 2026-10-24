"""演練視窗守門員（在 Windows 的 Python 執行）。

為什麼需要：WSLg 偶爾會無視 X11 座標，把 RViz／Gazebo 等視窗開到主螢幕（螢幕 1）
或螢幕 2，而螢幕 1 是使用者自用、演練視窗絕對不能出現。本程式每 0.15 秒巡一次，
發現 WSLg 視窗（class RAIL_WINDOW）不完全在螢幕 3（右緣 R > 0）就把它趕回螢幕 3。

為什麼不用 MoveWindow：WSLg 會把位置拉回去，實測只有「聚焦 + Win+Shift+方向鍵」有效。
螢幕排列 3 | 1 | 2：從螢幕 2 按 Win+Shift+→ 會繞回最左的螢幕 3；從螢幕 1 按 ← 到螢幕 3。

依賴：pywin32、pywinauto（python -m pip install pywin32 pywinauto）
"""
import argparse
import ctypes
import sys
import time
from datetime import datetime

try:
    import win32gui
    from pywinauto.controls.hwndwrapper import HwndWrapper
    from pywinauto.keyboard import send_keys
except ImportError as exc:
    print(f"錯誤：缺少套件（{exc}），請執行：python -m pip install pywin32 pywinauto",
          file=sys.stderr)
    sys.exit(1)

WSLG_CLASS = "RAIL_WINDOW"
TERMINAL_CLASS = "CASCADIA_HOSTING_WINDOW_CLASS"
POLL_SECONDS = 0.15
SETTLE_SECONDS = 0.8  # Windows 搬移視窗有動畫，太早讀座標會讀到半路的位置
RETRY_COOLDOWN = 2.0  # 同一視窗搬完仍不對時先等一下，避免狂按快捷鍵
KEYS_TO_RIGHT = "{VK_LWIN down}{VK_SHIFT down}{RIGHT}{VK_SHIFT up}{VK_LWIN up}"
KEYS_TO_LEFT = "{VK_LWIN down}{VK_SHIFT down}{LEFT}{VK_SHIFT up}{VK_LWIN up}"


def parse_args():
    parser = argparse.ArgumentParser(description="把跑出螢幕 3 的 WSLg 視窗趕回螢幕 3")
    parser.add_argument("--minutes", type=float, default=60, help="執行分鐘數（預設 60）")
    parser.add_argument("--mon2-left", type=int, default=1920,
                        help="螢幕 2 左緣的 Windows x 座標（預設 1920）")
    parser.add_argument("--dry-run", action="store_true", help="只印出會做什麼，不實際搬移")
    return parser.parse_args()


def set_dpi_awareness():
    # 螢幕 1/2 是 150% 縮放，不設 per-monitor DPI 感知會拿到被縮放過的假座標
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError) as exc:
        print(f"警告：設定 DPI 感知失敗（{exc}），座標可能不準", file=sys.stderr)


def list_windows(class_name):
    """回傳 [(hwnd, 標題, (L, T, R, B))]：可見且有標題的指定 class 視窗。"""
    found = []

    def _collect(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        if win32gui.GetClassName(hwnd) != class_name:
            return True
        title = win32gui.GetWindowText(hwnd)
        if title:
            found.append((hwnd, title, win32gui.GetWindowRect(hwnd)))
        return True

    win32gui.EnumWindows(_collect, None)
    return found


def now_text():
    return datetime.now().strftime("%H:%M:%S")


def move_to_screen3(hwnd, title, rect, mon2_left, dry_run):
    left, _top, right, _bottom = rect
    center_x = (left + right) // 2
    keys, direction = (KEYS_TO_RIGHT, "→") if center_x >= mon2_left else (KEYS_TO_LEFT, "←")
    if dry_run:
        print(f"{now_text()} [dry-run] 會送 Win+Shift+{direction}：{title} {rect}")
        return
    HwndWrapper(hwnd).set_focus()
    send_keys(keys)
    time.sleep(SETTLE_SECONDS)
    new_rect = win32gui.GetWindowRect(hwnd)
    print(f"{now_text()} 移到螢幕3: {title} {rect} -> {new_rect}")


def restore_terminal_focus(mon2_left):
    """把焦點還給螢幕 2 上的導覽終端機，讓使用者能繼續按 Enter。"""
    for hwnd, _title, rect in list_windows(TERMINAL_CLASS):
        if rect[0] >= mon2_left - 20:
            HwndWrapper(hwnd).set_focus()
            return


def guard_once(args, last_moved):
    for hwnd, title, rect in list_windows(WSLG_CLASS):
        if rect[2] <= 0:
            continue  # 右緣 ≤ 0 表示完整在螢幕 3
        if time.time() - last_moved.get(hwnd, 0) < RETRY_COOLDOWN:
            continue
        last_moved[hwnd] = time.time()
        try:
            move_to_screen3(hwnd, title, rect, args.mon2_left, args.dry_run)
            if not args.dry_run:
                restore_terminal_focus(args.mon2_left)
        except Exception as exc:  # 視窗可能在處理途中被關掉，任何錯誤都不能讓守門員停下
            print(f"{now_text()} 搬移失敗：{title} {rect}：{exc}", file=sys.stderr)


def main():
    args = parse_args()
    set_dpi_awareness()
    deadline = time.time() + args.minutes * 60
    last_moved = {}
    mode = "（dry-run，只印不動）" if args.dry_run else ""
    print(f"守門員啟動{mode}：{args.minutes} 分鐘，螢幕 2 左緣 x={args.mon2_left}，Ctrl+C 結束")
    try:
        while time.time() < deadline:
            try:
                guard_once(args, last_moved)
            except Exception as exc:  # 列舉視窗偶發失敗（如桌面切換中），記錄後繼續巡邏
                print(f"{now_text()} 巡邏錯誤：{exc}", file=sys.stderr)
            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        pass
    print("守門員結束")


if __name__ == "__main__":
    main()

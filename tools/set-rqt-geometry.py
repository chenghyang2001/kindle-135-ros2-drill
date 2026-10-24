#!/usr/bin/env python3
"""把 rqt_graph 視窗位置寫進 ~/.config/ros.org/rqt_gui.ini，讓它開在螢幕 3。

為什麼需要這支：rqt_graph 不吃 -qwindowgeometry，只會從 rqt_gui.ini 還原上次的
視窗幾何；而那個值是 Qt saveGeometry() 產生的二進位 blob，手寫不出來，
只能用 python_qt_binding 建一個 QWidget 設好位置後存出來。

執行環境：WSL 內、已 source /opt/ros/jazzy/setup.bash、DISPLAY 可用。
"""
import argparse
import os
import shutil
import sys
from datetime import date
from pathlib import Path

INI_PATH = Path.home() / ".config" / "ros.org" / "rqt_gui.ini"
GEOM_KEY = "perspective/@rqt_graph__RosGraph/mainwindow/geometry"


def parse_args():
    parser = argparse.ArgumentParser(description="設定 rqt_graph 視窗位置（寫入 rqt_gui.ini）")
    # 預設值讓視窗完整落在螢幕 3：X + W = 1190 ≤ 1226（WSLg 外框會多約 76px）
    parser.add_argument("--x", type=int, default=40, help="X11 座標 x（預設 40）")
    parser.add_argument("--y", type=int, default=40, help="X11 座標 y（預設 40）")
    parser.add_argument("--w", type=int, default=1150, help="寬度（預設 1150）")
    parser.add_argument("--h", type=int, default=580, help="高度（預設 580）")
    args = parser.parse_args()
    if args.w <= 0 or args.h <= 0:
        parser.error("寬度與高度必須為正整數")
    if args.x + args.w > 1226:
        print(f"⚠️  警告：x + w = {args.x + args.w} > 1226，視窗可能超出螢幕 3 跑到主螢幕",
              file=sys.stderr)
    return args


def check_display():
    if not os.environ.get("DISPLAY"):
        print("錯誤：缺少 DISPLAY 環境變數，請在 WSLg 有圖形環境的終端機執行"
              "（例如 export DISPLAY=:0）", file=sys.stderr)
        sys.exit(1)
    # 一定要 xcb：Wayland 模式下 Qt 不採用指定座標，存出來的幾何會不對
    os.environ["QT_QPA_PLATFORM"] = "xcb"


def backup_ini_once():
    """第一次修改前備份；已有任何 .bak-* 就不再備份，避免把原始設定蓋掉。"""
    if not INI_PATH.exists():
        return
    existing = list(INI_PATH.parent.glob(INI_PATH.name + ".bak-*"))
    if existing:
        print(f"已有備份：{existing[0]}（不再重複備份）")
        return
    backup_path = INI_PATH.with_name(f"{INI_PATH.name}.bak-{date.today():%Y%m%d}")
    shutil.copy2(INI_PATH, backup_path)
    print(f"已備份：{backup_path}")


def build_geometry_blob(x, y, w, h):
    try:
        from python_qt_binding.QtWidgets import QApplication, QWidget
    except ImportError as exc:
        print(f"錯誤：無法載入 python_qt_binding（{exc}）。"
              "請先 source /opt/ros/jazzy/setup.bash，並確認已安裝 ros-jazzy-desktop",
              file=sys.stderr)
        sys.exit(1)
    app = QApplication.instance() or QApplication([sys.argv[0]])
    widget = QWidget()
    widget.setGeometry(x, y, w, h)
    blob = widget.saveGeometry()
    widget.deleteLater()
    return app, blob


def write_ini(blob):
    from python_qt_binding.QtCore import QSettings

    INI_PATH.parent.mkdir(parents=True, exist_ok=True)
    settings = QSettings(str(INI_PATH), QSettings.IniFormat)
    settings.setValue(GEOM_KEY, blob)
    settings.sync()
    if settings.status() != QSettings.NoError:
        print(f"錯誤：寫入 {INI_PATH} 失敗（QSettings status={settings.status()}）",
              file=sys.stderr)
        sys.exit(1)


def main():
    args = parse_args()
    check_display()
    try:
        backup_ini_once()
        _app, blob = build_geometry_blob(args.x, args.y, args.w, args.h)
        write_ini(blob)
    except OSError as exc:
        print(f"錯誤：檔案操作失敗（{INI_PATH}）：{exc}", file=sys.stderr)
        sys.exit(1)
    print(f"✅ 已寫入 {INI_PATH}")
    print(f"   {GEOM_KEY} = {args.w}x{args.h}+{args.x}+{args.y}")
    print("   下次開 rqt_graph（QT_QPA_PLATFORM=xcb）就會出現在這個位置")


if __name__ == "__main__":
    main()

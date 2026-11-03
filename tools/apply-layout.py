#!/usr/bin/env python3
"""把 repo 的 drill/ 演練腳本複製到 ~/ros2-demo，並依版面改寫圖形視窗座標（在 WSL 執行）。

用法：
    python3 tools/apply-layout.py [--layout m3|m2right] [--dest ~/ros2-demo] [--dry-run]

版面：
    m3       原版三螢幕「3|1|2」，圖形視窗開在最左螢幕 3（WSLg X 0～1280），只複製不改。
    m2right  兩螢幕 [主螢幕 1][螢幕 2]，導覽終端機在螢幕 2 左半，
             圖形視窗開在螢幕 2 右半（WSLg X 2880～3840）。（預設）

為什麼不直接改 drill/ 原檔：
    drill/ 是已實測過的三螢幕版本，直接改會讓 m3 版面失效、也難以比對差異。
    版面差異只套在 ~/ros2-demo 的複製檔上，原檔保持不動，換回三螢幕時重跑 --layout m3 即可。

為什麼「必要替換」命中 0 次就報錯：
    替換是字面字串比對；命中 0 次代表 drill/ 原檔的座標已被改過，
    替換表跟不上，若靜默略過，視窗會開到螢幕 1 或畫面外，錄影才發現就太晚。

座標換算（m2right）：WSLg X 座標 = Windows x；外框 Windows left ≈ X - 32、寬 ≈ W + 76，
    所以相對右半左緣 relX + W ≤ 906、relX ≥ 32，對應 X 介於 2912～3786。

依賴：python 3.8+，只用標準函式庫。
"""
import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DRILL_DIR = REPO_ROOT / "drill"
DEFAULT_DEST = Path.home() / "ros2-demo"
LAYOUT_MARKER = ".layout"

# 只有這些副檔名會做「選用替換」（純畫面說明文字）
TEXT_SUFFIXES = {".sh", ".py", ".rviz"}

_RVIZ_CH12_13 = [
    ("880x600+40+20", "860x560+2916+20"),
    # 內嵌 Python 字串裡是「反斜線 n」兩個字元，不是換行，所以用 raw string
    (r'"\n  Height: 600\n"', r'"\n  Height: 560\n"'),
    (r'"\n  Width: 880\n"', r'"\n  Width: 860\n"'),
    (r'"\n  X: 40\n"', r'"\n  X: 2916\n"'),
]

# 版面 → 檔名 → [(舊, 新), ...]；每一條至少要命中 1 次
REQUIRED_REPLACEMENTS = {
    "m3": {},
    "m2right": {
        "gui-env.sh": [("500x500+720+100", "500x500+3180+100")],
        "jsp_gui_m3.py": [("300x540+880+60", "500x320+2916+640")],
        "urdf_m3.rviz": [
            ("  Height: 600", "  Height: 560"),
            ("  Width: 880", "  Width: 860"),
            ("  X: 40", "  X: 2916"),
        ],
        # ch03／ch05 原版沒載 gui-env.sh，三螢幕時靠 window-guardian 把視窗趕到螢幕 3；兩螢幕要補上
        "ch03.sh": [
            ("export GALLIUM_DRIVER=d3d12\n", "export GALLIUM_DRIVER=d3d12\nsource ~/ros2-demo/gui-env.sh\n"),
            ("ros2 run turtlesim turtlesim_node >", "ros2 run turtlesim turtlesim_node $TURTLE_GEOM >"),
        ],
        "ch05.sh": [
            ("export GALLIUM_DRIVER=d3d12\n", "export GALLIUM_DRIVER=d3d12\nsource ~/ros2-demo/gui-env.sh\n"),
            ('bg "ros2 run turtlesim turtlesim_node"', 'bg "ros2 run turtlesim turtlesim_node $TURTLE_GEOM"'),
        ],
        "ch09.sh": [
            ("500x500+40+80", "420x420+2916+40"),
            ("500x500+680+80", "420x420+2916+530"),
        ],
        "ch10.sh": [("880x600+40+20", "860x560+2916+20")],
        "ch11.sh": [("880x600+40+20", "860x560+2916+20")],
        "ch12.sh": list(_RVIZ_CH12_13),
        "ch13.sh": list(_RVIZ_CH12_13),
    },
}

# 版面 → 套用到所有 TEXT_SUFFIXES 檔案的 [(舊, 新), ...]；命中 0 次不算錯
OPTIONAL_REPLACEMENTS = {
    "m3": [],
    "m2right": [
        ("（X 0～1280）", "（X 2880～3840）"),
        ("螢幕 3", "螢幕 2 右半"),
    ],
}

# 執行完要提示使用者的 rqt_graph 設定指令
RQT_HINT = {
    "m3": "python3 tools/set-rqt-geometry.py",
    "m2right": "python3 tools/set-rqt-geometry.py --x 2916 --y 40 --w 860 --h 600",
}


class LayoutError(Exception):
    """可預期的失敗（來源不存在、替換表過期等），main 印訊息並 exit 1。"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="複製 drill/ 到 ~/ros2-demo 並套用視窗版面")
    parser.add_argument("--layout", choices=sorted(REQUIRED_REPLACEMENTS), default="m2right",
                        help="版面名稱（預設 m2right）")
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST,
                        help=f"目的資料夾（預設 {DEFAULT_DEST}）")
    parser.add_argument("--dry-run", action="store_true", help="只列出會做什麼，不寫檔")
    return parser.parse_args()


def list_source_files() -> list:
    if not DRILL_DIR.is_dir():
        raise LayoutError(f"找不到來源資料夾：{DRILL_DIR}")
    files = sorted(p for p in DRILL_DIR.rglob("*") if p.is_file())
    if not files:
        raise LayoutError(f"來源資料夾是空的：{DRILL_DIR}")
    return files


def apply_replacements(text: str, rel_name: str, layout: str) -> tuple:
    """回傳 (新文字, 必要替換處數, 選用替換處數)；必要替換命中 0 次就丟 LayoutError。"""
    required_count = 0
    for old, new in REQUIRED_REPLACEMENTS[layout].get(rel_name, []):
        hits = text.count(old)
        if hits == 0:
            raise LayoutError(f"{rel_name}：必要替換「{old}」命中 0 次"
                              f"（drill/ 原檔可能已改過，請更新 apply-layout.py 的替換表）")
        text = text.replace(old, new)
        required_count += hits

    optional_count = 0
    if Path(rel_name).suffix in TEXT_SUFFIXES:
        for old, new in OPTIONAL_REPLACEMENTS[layout]:
            optional_count += text.count(old)
            text = text.replace(old, new)
    return text, required_count, optional_count


def check_table_targets_exist(rel_names: set, layout: str) -> None:
    """替換表列的檔案若不在 drill/ 裡，也算表過期。"""
    missing = sorted(set(REQUIRED_REPLACEMENTS[layout]) - rel_names)
    if missing:
        raise LayoutError(f"替換表列出但 drill/ 中找不到的檔案：{', '.join(missing)}")


def process_file(src: Path, dest_root: Path, layout: str, dry_run: bool) -> tuple:
    """複製（必要時改寫）單一檔案，回傳 (相對路徑, 必要處數, 選用處數)。"""
    rel = src.relative_to(DRILL_DIR)
    rel_name = rel.as_posix()
    target = dest_root / rel
    needs_edit = layout != "m3" and (
        rel_name in REQUIRED_REPLACEMENTS[layout] or src.suffix in TEXT_SUFFIXES)

    required_count = optional_count = 0
    if needs_edit:
        # newline="" 保留原本的 LF，避免改寫後變 CRLF 在 bash 跑不動
        with src.open("r", encoding="utf-8", newline="") as fh:
            original = fh.read()
        new_text, required_count, optional_count = apply_replacements(original, rel_name, layout)
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("w", encoding="utf-8", newline="") as fh:
                fh.write(new_text)
            shutil.copymode(src, target)
    elif not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)

    if not dry_run and target.suffix == ".sh":
        target.chmod(target.stat().st_mode | 0o755)
    return rel_name, required_count, optional_count


def write_layout_marker(dest_root: Path, layout: str) -> None:
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    (dest_root / LAYOUT_MARKER).write_text(f"layout={layout}\napplied_at={stamp}\n",
                                           encoding="utf-8")


def print_report(results: list, layout: str, dest_root: Path, dry_run: bool) -> None:
    prefix = "【乾跑】" if dry_run else ""
    print(f"{prefix}版面：{layout}　來源：{DRILL_DIR}　目的：{dest_root}")
    for rel_name, required_count, optional_count in results:
        if required_count or optional_count:
            print(f"  {rel_name}：必要替換 {required_count} 處、說明文字替換 {optional_count} 處")
        else:
            print(f"  {rel_name}：原樣複製")
    verb = "會複製" if dry_run else "已複製"
    print(f"{prefix}{verb} {len(results)} 個檔案。")
    print("下一步：")
    print(f"  1. rqt_graph 視窗位置（WSL 內）：{RQT_HINT[layout]}")
    print("  2. 導覽終端機請在 Windows 端開：PYTHONUTF8=1 python tools/open_chapter.py NN "
          f"--layout {layout}")


def main() -> None:
    args = parse_args()
    dest_root = args.dest.expanduser()
    try:
        sources = list_source_files()
        check_table_targets_exist({p.relative_to(DRILL_DIR).as_posix() for p in sources},
                                  args.layout)
        # 先在記憶體做完所有替換檢查，任何一條失敗都不會留下半套複製檔
        for src in sources:
            process_file(src, dest_root, args.layout, dry_run=True)
        results = [process_file(src, dest_root, args.layout, args.dry_run) for src in sources]
        if not args.dry_run:
            write_layout_marker(dest_root, args.layout)
    except LayoutError as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        sys.exit(1)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"錯誤：讀寫檔案失敗：{exc}", file=sys.stderr)
        sys.exit(1)
    print_report(results, args.layout, dest_root, args.dry_run)


if __name__ == "__main__":
    main()

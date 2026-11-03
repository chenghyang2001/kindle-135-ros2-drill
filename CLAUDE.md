# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 專案概述

Kindle 135《ROS 2 from Scratch》（Packt）逐章演練包：在 **Windows 11 + WSL2 Ubuntu 24.04 + ROS 2 Jazzy** 上跑第 1～13 章（沒有 ch02，那章是安裝）。
所有演練腳本 2026-10-24 已完整跑過並測過——**重跑時直接用現有檔案，不要重新產生或改寫 `drill/chNN.sh`**。
屬學習情境，採「快速 demo 模式」（見全域規則），未經 QA／審查。

使用者文件：`README.md`（總覽、問題與解法表）、`RERUN-SAME-PC.md`（同機重跑）、`NEW-PC-CHECKLIST.md`（換機與座標重算）、`TODO.md`。

## 兩個執行端（最重要的架構概念）

程式碼分成兩邊執行，不可混用：

| 位置 | 在哪跑 | 內容 |
| --- | --- | --- |
| `drill/` | **WSL Ubuntu**（複製到 `~/ros2-demo/` 執行） | 每章導覽 bash 腳本、GUI 座標設定、RViz 設定 |
| `tools/setup-ros2.sh`、`check-env.sh`、`set-rqt-geometry.py` | **WSL Ubuntu** | 安裝、環境檢查、rqt 視窗位置 |
| `tools/` 其餘 `.py` | **Windows Python**（需 `PYTHONUTF8=1`） | 視窗控制、錄影、剪片、YouTube 上傳、視窗守門員 |

- 書本官方範例假設 clone 在 WSL 的 `~/ROS-2-from-Scratch`；腳本把檔案複製進 `~/ros2_ws`（可用 `WS=` 覆寫）再 `colcon build`。
- `.gitattributes` 強制 `*.sh/*.py/*.rviz/*.config/*.md` 用 LF——在 Windows 端編輯後若變 CRLF，WSL 執行會壞。

## 導覽腳本結構（`drill/chNN.sh`）

每支腳本共用同一組小函式：`title "(k/N) ..."`（清畫面＋段落標題）、`run`（印出並執行指令）、`note`（說明）、`next`（`read` 等 Enter）、`bg`（背景跑節點並導出 log 到 `/tmp/chNN_*.log`）、`stopall`（`trap EXIT` 清掉該章節點）。

`tools/drill_ctl.py` 依賴這些輸出字串判斷狀態——改腳本輸出格式會破壞控制器：

- `第 N 章演練 (k/N)`（`SECTION_RE`）、`按 Enter 繼續`（等待中）、`完成 ✅`（章節結束）。

環境旗標：`DEMO_RECORD=1`（錄影模式，第 13 章鍵盤遙控改自動駕駛）、`DEMO_AUTO=1`（自動測試時略過鍵盤遙控）。

## 視窗座標（全部依「3 | 1 | 2」螢幕排列寫死）

- 圖形視窗（turtlesim、RViz、關節滑桿、rqt）一律開在**螢幕 3**＝WSLg X 座標 0～1280；必須走 X11 模式（`drill/gui-env.sh` 的 `QT_QPA_PLATFORM=xcb` ＋ `-qwindowgeometry WxH+X+Y`），WSLg 預設 Wayland 會開到主螢幕。
- 導覽／練習終端機在**螢幕 2**（Windows x 1920～3840）；錄影版面左半「教練」、右半「練習」（`drill_ctl.py` 的 `COACH_RECT`／`PRACTICE_RECT`）。
- **螢幕 1 是使用者自用，任何演練視窗都不能出現在上面。**
- 座標散在多個檔案，換排列時要一起改，清單見 `NEW-PC-CHECKLIST.md` 第 4 節。外框換算：Windows left ≈ -1280 + X - 32、寬 ≈ W + 76，螢幕 3 內需 X + W ≤ 1226。
- 改書本 launch／rviz 設定時只改**工作區複製檔**並標「本演練加」，書本 repo 原檔不動。

## 兩螢幕版（2026-11-03 起，目前這台的配置）

進度與操作見 `HANDOFF.md`。重點：

- `tools/apply-layout.py`（WSL）複製 `drill/` 到 `~/ros2-demo` 並以字面替換表套用座標（`m2right`：圖形視窗放螢幕 2 右半 X 2880～3840；`m3`：原版）。改 `drill/` 的座標字串時要同步更新替換表，否則它會報錯。
- 這台 WSLg 不理 `-qwindowgeometry` 位置，靠 `tools/x11-placer.sh`（由 `gui-env.sh` 背景啟動）用 xdotool 搬視窗。
- 自動啟動的 ros2 daemon 會卡死，`tools/open_chapter.py`（Windows）開章前先手動重啟 daemon。
- `drill_ctl.py` 的錄影雙視窗版面仍是三螢幕設計，兩螢幕下會與圖形視窗重疊。

## 錄影與影片管線（Windows 端）

產物都在 `~/Videos/kindle-drill/k135/`（`events.log`、`raw/`、`out/`），不在 repo 內。

1. 教練 Claude 以 `teaching/DRILL-PROMPT.md` 為開場提示詞，讀 `teaching/drill.json`（章名、段數、`gui`、`highlight` 段、重點指令）。
2. `tools/record_m23.py start|stop|status` —— ffmpeg gdigrab 分錄螢幕 2、3（先錄 mkv 再 remux mp4），寫 `rec_start` 到 `events.log`。
3. `tools/drill_ctl.py open NN|screen --lines N|status|next|close|place-coach` —— 用 UIA 讀 Windows Terminal 文字、透過 `~/.claude/scripts/wt-send.ps1` 送 Enter；每個動作記到 `events.log`，後製靠它對齊時間軸。`close` 會在 WSL 裡 pkill 殘留 ROS 程序。
4. `tools/make_videos.py full|highlight|prompts|manifest|all [--out DIR]` —— 依 `events.log` 剪完整版、精華版（`teaching/narration/highlight.json` 旁白＋edge-tts）、提示詞影片（`teaching/narration/prompts/chNN.txt`，呼叫 `make_caption_video.py`）。文字一律 Pillow 畫成 PNG 疊上，不用 drawtext；濾鏡寫成檔案用 `-/filter_complex`（ffmpeg 7+）。
5. `tools/yt_upload_k135.py [--only KEY] [--dry-run] | status | --replace KEY` —— 私人上傳，先驗證頻道 id（`EXPECTED_CHANNEL_ID`），狀態存 manifest 旁的 `yt_state.json` 避免重傳；配額用盡 exit 75。

## 常用指令

```bash
# WSL：環境檢查、部署腳本
bash tools/check-env.sh
bash tools/setup-ros2.sh --dry-run
mkdir -p ~/ros2-demo && cp drill/* ~/ros2-demo/ && chmod +x ~/ros2-demo/*.sh

# WSL：無畫面自動跑單章（測試用）
QT_QPA_PLATFORM=offscreen yes "" | ~/ros2-demo/ch05.sh
DEMO_AUTO=1 QT_QPA_PLATFORM=offscreen yes "" | ~/ros2-demo/ch13.sh
# 驗證視窗座標：Xvfb :99 -screen 0 5120x1080x24 & 後以 DISPLAY=:99 啟動，再 xdotool + xwininfo 讀位置

# Windows：開單章導覽終端機到螢幕 2
wt.exe -w ros2drill --pos 2000,40 --maximized new-tab --title 第1章演練 wsl.exe -d Ubuntu-24.04 --cd ~ -- ./ros2-demo/ch01.sh

# Windows：自我測試（純函式／離線，不需錄影檔）
PYTHONUTF8=1 python tools/make_videos.py --self-test
PYTHONUTF8=1 python tools/make_caption_video.py --self-test
PYTHONUTF8=1 python tools/yt_upload_k135.py --self-test

# Windows：背景視窗守門員（視窗跑出螢幕 3 就用 Win+Shift+方向鍵趕回）
PYTHONUTF8=1 python tools/window-guardian.py --minutes 90
```

沒有建置系統或測試框架；`.sh` 用 `bash -n` 做語法檢查，`.py` 用各自的 `--self-test`。

## 已知限制

- Gazebo GUI 位置設定無效 → 第 13 章用 `gz sim -s`（只跑物理），用 RViz 看車子。
- 關節滑桿不理 SIGTERM，一律 `pkill -9`；rqt_graph 不收位置參數，用 `set-rqt-geometry.py` 寫 `~/.config/ros.org/rqt_gui.ini`。
- Jazzy turtlesim 需 `ros2 topic pub -r 30` 高頻發送才會連續移動。
- 錄影時第 5 章 turtlesim 視窗全黑，精華版該章改用終端機畫面（TODO：重錄第 5 章）。

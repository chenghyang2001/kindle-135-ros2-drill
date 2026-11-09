# 🔴 最新進度（2026-11-09，HP1 三螢幕 tmux＋TTS 互動版）

- 已完成：第 1、3、4、5、6、7、8 章；**下次從第 9 章第 1 段開始**
- 接續提示詞：`~/workspace/console/prompts/k135-resume-ch09.md`
- 這台（HP1）是三螢幕「2｜1｜3」：圖形視窗放螢幕 2（左）、tmux 教練＋練習放螢幕 3（右）、螢幕 1 不放；`~/ros2-demo` 是原版 m3 座標，小烏龜 `+720+100` 正好落在螢幕 2
- 重跑會遇到的坑（舊編譯暫存、自訂型別 echo 要 10 秒、WSLg COPY MODE）見 `~/.claude/instructions/wslg-drill-preflight.md`
- 以下是 2026-11-03 另一台兩螢幕的舊交接，僅供參考

---

# 交接：K135 演練在這台電腦（兩螢幕）繼續跑

最後更新：2026-11-03 10:20（台北時間）
電腦：HP EliteBook 840 G8（DESKTOP-6LST1BR），Windows 帳號 `USER`，WSL 發行版 `Ubuntu-24.04`（Linux 帳號 `user`）

---

## 1. 現在停在哪裡

| 項目 | 狀態 |
| --- | --- |
| 環境安裝 | ✅ 完成，`tools/check-env.sh` 全部 PASS（23 項） |
| 書本範例 | ✅ 已 clone 到 WSL `~/ROS-2-from-Scratch` |
| 演練腳本 | ✅ 已複製到 `~/ros2-demo`，套用兩螢幕版面（`~/ros2-demo/.layout` = `m2right`） |
| rqt_graph 位置 | ✅ 已寫入 `~/.config/ros.org/rqt_gui.ini`（螢幕 2 右半） |
| 工作區 `~/ros2_ws` | 只建了空殼（第 4 章第 1 段），`src/` 裡還沒有套件；`~/.bashrc` 已加 `source ~/ros2_ws/install/setup.bash` |
| 演練進度 | 第 4 章跑到 **(1/6)** 就停止（視窗已關） |
| 已實測的章節 | 第 3 章（小烏龜、rqt_graph）、第 10 章（RViz、關節滑桿）視窗位置正確 |

**下次從第 4 章重新開始**（第 4 章會偵測到 `~/ros2_ws` 已存在而略過建立，從建套件接下去，沒問題）。

---

## 2. 下次怎麼繼續（照做即可）

### 步驟 A：確認螢幕還是兩螢幕

這套設定假設：`[ 主螢幕 1（1920x1080）][ 螢幕 2（1920x1080）]`，螢幕 2 在主螢幕右邊。

- 還是一樣 → 直接到步驟 B。
- 接回三螢幕「3 | 1 | 2」→ 見第 6 節「換回三螢幕」。
- 變成別的排列 → 見 `NEW-PC-CHECKLIST.md` 第 4 節重算座標。

### 步驟 B：開一章（在 Windows 的 Git Bash，repo 根目錄）

```bash
cd ~/workspace/kindle-135-ros2-drill
PYTHONUTF8=1 python tools/open_chapter.py 04
```

它會自動：關掉上一章的演練視窗 → 重啟 ros2 daemon → 開新的 Windows Terminal 視窗（標題「K135 演練-ch04」）放在螢幕 2 左半。

### 步驟 C：在演練視窗裡按 Enter 往下

- 點一下演練視窗，看完一段按 Enter。
- 畫面出現「完成 ✅」就是這章結束。
- 圖形視窗（小烏龜、RViz…）會自動出現在螢幕 2 右半。
- 開下一章：`PYTHONUTF8=1 python tools/open_chapter.py 05`（會自動關掉上一章）。

### 章節順序（**一定要從第 4 章依序跑**，後面的章節依賴前面建好的套件）

| 章 | 主題 | 圖形視窗 | 狀態 |
| --- | --- | --- | --- |
| 01 | ROS 2 是什麼 | — | 可隨時跑 |
| 03 | 核心概念 turtlesim | 小烏龜、rqt_graph | ✅ 已實測 |
| **04** | **第一個節點（建 ros2_ws、Python／C++ 套件）** | — | **⬅ 從這裡繼續** |
| 05 | Topic | 小烏龜 | 未跑 |
| 06 | Service | 小烏龜 | 未跑 |
| 07 | Action | — | 未跑 |
| 08 | Parameter | 小烏龜 | 未跑 |
| 09 | Launch | 兩隻小烏龜（上下排） | 未跑 |
| 10 | TF | RViz＋滑桿 | ✅ 視窗位置已實測（但前面章節沒跑過，需依序） |
| 11 | URDF／Xacro | RViz＋滑桿 | 未跑 |
| 12 | description 套件 | RViz＋滑桿 | 未跑 |
| 13 | Gazebo | RViz | 未跑；最後一段鍵盤遙控按 Ctrl+C 結束 |

---

## 3. 這台電腦的特殊狀況（已處理，但要知道）

| 現象 | 原因 | 已做的處理 | 若又發生 |
| --- | --- | --- | --- |
| 圖形視窗開在主螢幕左上角 | 這台的 WSLg 不理 `-qwindowgeometry` 的位置（大小有效） | 章節腳本 source `gui-env.sh` 時背景啟動 `~/ros2-demo/x11-placer.sh`，用 xdotool 把視窗搬到螢幕 2 右半；章節腳本結束就自己停 | 看 WSL 的 `/tmp/x11-placer.log`；手動搬：`DISPLAY=:0 xdotool search --name TurtleSim windowmove %@ 3180 100` |
| 腳本卡在 `ros2 node list` 不動 | 由 ros2 指令「自動啟動」的 daemon 會卡死（連 127.0.0.1:11511 timeout） | `open_chapter.py` 開章前先殺舊 daemon、再手動 `ros2 daemon start` | 另開 WSL 終端機執行 `source /opt/ros/jazzy/setup.bash; ros2 daemon stop; ros2 daemon start`，卡住的指令通常就會繼續 |
| 關節滑桿視窗下半被工作列擋住 | 滑桿視窗最小高度約 700 | 改放 (2916, 300)，疊在 RViz 左側面板上（3D 畫面不擋） | 可手動拖動，x11-placer 只搬「跑出螢幕 2 右半」的視窗，不會跟你搶 |
| 安裝腳本卡在 sudo | 這台 sudo 免密碼，但 `sudo -v` 仍要求密碼 | `setup-ros2.sh` 改成先試 `sudo -n true` | — |

WSL 網路是 `mirrored` 模式（`%USERPROFILE%\.wslconfig`），DDS 通訊本身正常（talker／listener 實測可收）。

---

## 4. 如果環境好像壞了

在 WSL（Windows Terminal 執行 `wsl -d Ubuntu-24.04`）：

```bash
cd /mnt/c/Users/USER/workspace/kindle-135-ros2-drill
bash tools/check-env.sh                 # 應全部 PASS（xrandr 那段的座標提醒是三螢幕的文字，可忽略）
python3 tools/apply-layout.py           # 重新複製腳本並套用兩螢幕座標（會覆蓋 ~/ros2-demo）
source /opt/ros/jazzy/setup.bash
python3 tools/set-rqt-geometry.py --x 2916 --y 40 --w 860 --h 600
```

`set-rqt-geometry.py` 會印「x + w > 1226」的警告，那是它寫死的三螢幕檢查，兩螢幕版可忽略。

殘留的 ROS 程序（例如視窗被強制關掉）：

```bash
pkill -f '[t]urtlesim_node|[r]viz2|[r]obot_state_publisher|[p]arameter_bridge|[g]z sim|[x]11-placer'
pkill -9 -f '[j]sp_gui|[r]qt_graph'
```

想從頭重建工作區：`mv ~/ros2_ws ~/ros2_ws.bak-$(date +%Y%m%d)`，再從第 4 章跑。

---

## 5. 這次新增／修改的檔案

| 檔案 | 在哪跑 | 用途 |
| --- | --- | --- |
| `tools/apply-layout.py` | WSL | 把 `drill/` 複製到 `~/ros2-demo` 並套用版面座標（`--layout m2right` 預設／`m3` 原版）；替換表對不上會報錯，不留半套檔案 |
| `tools/x11-placer.sh` | WSL（自動） | 背景搬圖形視窗到螢幕 2 右半；由 `gui-env.sh` 啟動 |
| `tools/open_chapter.py` | Windows | 開章：關舊視窗、重啟 daemon、終端機放螢幕 2 左半（`--no-daemon-restart` 可跳過重啟） |
| `tools/setup-ros2.sh` | WSL | 修 sudo 檢查（一行） |
| `RERUN-SAME-PC.md` | — | 開頭新增兩螢幕版用法 |

`drill/` 底下的原始腳本**完全沒改**，兩螢幕的差異只套在 `~/ros2-demo` 的複製檔。
這些工具是快速 demo 模式寫的，沒有經過 QA／審查。

---

## 6. 換回三螢幕「3 | 1 | 2」

```bash
# WSL
python3 tools/apply-layout.py --layout m3
source /opt/ros/jazzy/setup.bash && python3 tools/set-rqt-geometry.py
```

之後照 `RERUN-SAME-PC.md` 後半（三螢幕版）的 `wt.exe` 指令開章，並開 `tools/window-guardian.py` 當備援。
注意：三螢幕版不會啟動 x11-placer，若 WSLg 仍不理座標，要靠 window-guardian 搬視窗。

---

## 7. 還沒做的事

- [ ] 第 4～13 章依序跑完（第 5、6、8、9、11、12、13 章的視窗位置尚未實測，特別是第 9 章兩隻烏龜、第 13 章 Gazebo）
- [ ] 錄影的「教練＋練習」雙視窗模式（`tools/drill_ctl.py`、`teaching/DRILL-PROMPT.md`）是照三螢幕設計：練習視窗放螢幕 2 右半，會跟兩螢幕版的圖形視窗重疊，要重錄前需重新規劃版面
- [ ] `TODO.md` 原有項目：第 5 章 turtlesim 全黑重錄、Kindle 136 照同方式演練

---

## 8. 給 Claude 的接手提示

使用者說「繼續 K135 演練」時：先讀本檔與 `CLAUDE.md`，確認螢幕仍是兩螢幕（可用 DPI aware 的 `Screen.AllScreens` 檢查），然後執行 `PYTHONUTF8=1 python tools/open_chapter.py <下一章>`。
WSL 指令含 `$` 或引號時，先寫成腳本檔放 scratchpad 再 `wsl.exe -d Ubuntu-24.04 -- bash <路徑>` 執行，直接用 `bash -c` 常因 Git Bash 跳脫出錯。

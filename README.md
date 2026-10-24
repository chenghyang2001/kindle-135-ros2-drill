# Kindle 135《ROS 2 from Scratch》演練包

在 **Windows 11 + WSL2 Ubuntu 24.04 + ROS 2 Jazzy** 上，把《ROS 2 from Scratch》（Edouard Renard，Packt）第 1～13 章逐章演練的腳本與設定。
2026-10-24 第一次完整跑完，所有腳本都測過，**之後重跑直接用這裡的檔案，不需要重新產生**。

- 書本官方範例：<https://github.com/PacktPublishing/ROS-2-from-Scratch>（範例從 ch4 開始）
- 簡報：<https://github.com/chenghyang2001/kindle-135-slides>

## 快速開始

| 情況 | 看哪份文件 |
| --- | --- |
| 在同一台電腦重跑 | [RERUN-SAME-PC.md](RERUN-SAME-PC.md) |
| 換一台電腦跑 | [NEW-PC-CHECKLIST.md](NEW-PC-CHECKLIST.md) |
| 之後要做的事 | [TODO.md](TODO.md) |

## YouTube 影片（私人，需登入 ChengHsien Yang 帳號觀看）

2026-10-24 用「教練＋練習」雙視窗錄製第 1～13 章，共 14 支：

| 播放清單 | 內容 |
| --- | --- |
| [雙視窗演練](https://www.youtube.com/playlist?list=PLWSfrpTQNwPE) | 完整版 57 分鐘（[單支](https://youtu.be/3fuZbhznKhU)，含章節時間軸）＋精華版 |
| [精華版](https://www.youtube.com/playlist?list=PLSJQ4ncKDE2U) | 3 分 20 秒，每章約 15 秒＋中文語音解說（[單支](https://youtu.be/YUw1yf7X4Po)） |
| [提示詞與指令](https://www.youtube.com/playlist?list=PLR1CQ60VN9do) | 12 支，每章的教練提示與關鍵 ROS 2 指令，語音＋同步字幕 |

製作流程（可重跑）：`teaching/DRILL-PROMPT.md`（教練開場提示詞）→ `tools/drill_ctl.py`（教練操作練習視窗）＋ `tools/record_m23.py`（分錄螢幕 2、3）→ `tools/make_videos.py all`（完整版／精華版／提示詞）→ `tools/yt_upload_k135.py`（私人上傳＋播放清單）。旁白稿在 `teaching/narration/`。
已知瑕疵：第 5 章 turtlesim 視窗錄影時未繪出（全黑），精華版該章改用終端機畫面。

## 目錄結構

```text
drill/                 # 演練腳本（複製到 WSL 的 ~/ros2-demo/ 執行）
  ch01.sh ~ ch13.sh    # 每章導覽腳本，每段按 Enter 往下（ch02 是安裝，無腳本）
  gui-env.sh           # 圖形視窗統一設定（X11 模式＋螢幕 3 座標）
  jsp_gui_m3.py        # 關節滑桿包裝程式（補上視窗位置）
  urdf_m3.rviz         # 第 10、11 章用的 RViz 設定（視窗縮小、移到螢幕 3）
  gz_gui_m3.config     # Gazebo 介面設定（目前未使用，見下方「已知限制」）
tools/
  setup-ros2.sh        # 新電腦一鍵安裝 ROS 2 與演練用套件
  check-env.sh         # 檢查執行環境（PASS/WARN/FAIL）
  set-rqt-geometry.py  # 把 rqt_graph 的視窗位置寫進設定檔
  window-guardian.py   # Windows 端背景守門員：Linux 視窗跑出螢幕 3 就移回來
screenshots/           # Hello World 演練截圖（螢幕 2、螢幕 3）
```

## 全書演練總結

| 章 | 主題 | 演練內容 | 圖形視窗（螢幕 3） |
| --- | --- | --- | --- |
| 1 | ROS 2 是什麼 | ROS 2 不是作業系統、Jazzy LTS、三大組成、跨語言無中央主機、拆節點容錯 | — |
| 2 | 安裝 | WSL2 + Ubuntu 24.04 + ROS 2 Jazzy + Gazebo Harmonic（見 tools/setup-ros2.sh） | — |
| 3 | 核心概念 | turtlesim：node / topic / service / action / parameter / launch | 小烏龜、rqt_graph |
| 4 | 第一個節點 | 建 ros2_ws、Python 與 C++ 套件、colcon build、`__node:=` 改名 | — |
| 5 | Topic | publisher / subscriber、跨語言、remap、自訂 `.msg`、小烏龜閉迴路控制 | 小烏龜 |
| 6 | Service | `.srv`、server / client、拒絕不合法請求、小烏龜換筆色與啟停 | 小烏龜 |
| 7 | Action | `.action`、server 三個 callback、client、取消、底層 3 service + 2 topic | — |
| 8 | Parameter | 宣告、`-p` 啟動給值、`param set`、YAML 檔、`param dump` | 小烏龜 |
| 9 | Launch | bringup 套件、Python 與 XML launch、namespace、兩組小烏龜 | 兩個小烏龜 |
| 10 | TF | R2-D2 模型、robot_state_publisher、RViz、關節滑桿、view_frames、tf2_echo | RViz、滑桿 |
| 11 | URDF / Xacro | 兩 link 範例、兩輪底盤、Xacro property / macro、加長實驗 | RViz、滑桿 |
| 12 | description 套件 | my_robot_description、display.launch.py | RViz、滑桿 |
| 13 | Gazebo | collision / inertia、DiffDrive 外掛、ros_gz_bridge、自動繞圈、鍵盤遙控 | RViz |

演練模式：**快速 demo 模式**（只求看懂流程；每章腳本都先用無畫面模式自動跑過一次，沒有經過 QA／審查）。

## 這次遇到的問題與解法

| 問題 | 解法 |
| --- | --- |
| WSLg 新視窗預設開在**主螢幕（螢幕 1）**中央 | 圖形程式改用 X11 模式（`QT_QPA_PLATFORM=xcb`）並指定座標，WSLg 會採用；見 `drill/gui-env.sh` |
| turtlesim / RViz 指定位置 | 啟動參數 `-qwindowgeometry WxH+X+Y` |
| rqt_graph 不收位置參數 | 把位置寫進 `~/.config/ros.org/rqt_gui.ini`（`tools/set-rqt-geometry.py`） |
| 關節滑桿不收位置參數 | `drill/jsp_gui_m3.py` 在建立視窗時補上參數 |
| 關節滑桿收到 SIGTERM 不會結束，換模型會殘留 | 一律 `pkill -9` |
| 書本 RViz 設定記住 X=2197（＝螢幕 1） | 在工作區複製檔改成螢幕 3；第 13 章另把 Fixed Frame 改 `odom` |
| 書本 launch 檔沒指定視窗位置（第 9、12、13 章） | 腳本在**工作區複製檔**加上座標（標「本演練加」），repo 原檔不動 |
| Gazebo 視窗位置設定實測無效 | 第 13 章改用 `-s` 只跑物理模擬、不開畫面，用 RViz 看車子移動 |
| Jazzy turtlesim 每筆 cmd_vel 只動一下 | `ros2 topic pub -r 30` 高頻發送 |
| Python 範例被中斷時印 `ExternalShutdownException` | 無害，腳本只顯示 INFO 行 |
| 實際視窗外框比 Xvfb 量到的寬 | Windows 端 left ≈ -1280 + X - 32、width ≈ W + 76；螢幕 3 內需 X + W ≤ 1226 |

## 螢幕配置（本機）

```text
 Windows 排列：  [ 3 ]  [   1   ]  [   2   ]
 Windows x：   -1280~0   0~1920   1920~3840
 WSLg X 桌面：   0~1280  1280~3200 3200~5120
 用途：        圖形視窗  使用者自用  導覽終端機
                         （禁放）
```

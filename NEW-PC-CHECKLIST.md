# 情況二：換一台電腦跑演練 —— 環境檢查清單

照順序檢查，前一項沒過就先處理，不要往下。

## 1. Windows 端（PowerShell 或 Git Bash）

| 項目 | 指令 | 通過條件 |
| --- | --- | --- |
| Windows 版本 | `winver` | Windows 11（或 Windows 10 21H2 以上，WSLg 才能顯示 Linux 視窗） |
| WSL 版本 | `wsl --version` | WSL 2.x，列出 **WSLg 版本** |
| 虛擬化 | 工作管理員 → 效能 → CPU →「虛擬化：已啟用」 | 已啟用（或 `wsl -l -v` 能跑 VERSION 2 的發行版） |
| 記憶體 | 工作管理員 | 16 GB 以上建議（本機 32 GB） |
| 磁碟 | 檔案總管 | 安裝槽剩 20 GB 以上（ROS 2＋Gazebo 約 7 GB，加編譯產物） |
| 顯示卡 | 裝置管理員 → 顯示卡 | 有 GPU 驅動（Intel Iris Xe 以上即可跑 RViz；Gazebo 3D 會吃力） |
| Python（Windows 端） | `python -m pip install pywin32 pywinauto pillow` | 守門員 `tools/window-guardian.py` 需要 |

## 2. 安裝 Ubuntu 24.04（裝到非系統槽較好）

```powershell
wsl --install -d Ubuntu-24.04 --location D:\WSL\Ubuntu-24.04 --no-launch
```

之後建立一般使用者（範例是 `peter`），並在 `/etc/wsl.conf` 設定 `[user] default=<帳號>`、`[boot] systemd=true`。

## 3. 一鍵安裝 ROS 2 與演練套件

在 Ubuntu 內，把本 repo clone 下來後：

```bash
git clone https://github.com/chenghyang2001/kindle-135-ros2-drill.git ~/kindle-135-ros2-drill
cd ~/kindle-135-ros2-drill
bash tools/setup-ros2.sh --dry-run   # 先看會做什麼
bash tools/setup-ros2.sh             # 實際安裝（需 sudo，約 15～30 分鐘）
bash tools/check-env.sh              # 檢查結果
```

`check-env.sh` 會檢查：Ubuntu 版本、ROS 2 Jazzy、所有需要的套件、顯示卡加速（d3d12）、記憶體與磁碟、X 桌面與螢幕配置、書本範例與演練腳本是否就位。

## 4. 螢幕配置 —— 最重要，座標要重算

演練腳本的視窗座標是依本機「**3 | 1 | 2**」排列寫的：

- 圖形視窗（RViz、小烏龜、滑桿…）放 **WSLg X 座標 0～1280**（＝最左邊的螢幕 3）
- 導覽終端機放 Windows 座標 x=2000 起（螢幕 2）
- 主螢幕（螢幕 1）不放任何演練視窗

換電腦時：

1. 執行 `xrandr`（在 Ubuntu 內）看 X 桌面大小與各螢幕位置；X 桌面最左邊 = Windows 最左邊螢幕。
2. 決定「圖形視窗放哪個螢幕」，算出它在 X 桌面的範圍（起點 X0、寬 W0）。
3. 外框換算：Windows 端 left ≈ 螢幕左緣 + X - 32、寬 ≈ W + 76；要完整落在螢幕內需 **X + W ≤ W0 - 54**。
4. 修改以下位置的座標（全部是 `寬x高+X+Y`）：

| 檔案 | 內容 |
| --- | --- |
| `drill/gui-env.sh` | `TURTLE_GEOM`（小烏龜） |
| `drill/jsp_gui_m3.py` | `JSP_GEOM` 預設值（關節滑桿） |
| `drill/urdf_m3.rviz` | `Window Geometry` 的 Width / Height / X / Y |
| `drill/ch10.sh`、`ch11.sh` | `rviz2 ... -qwindowgeometry` |
| `drill/ch09.sh` | 兩個小烏龜的 `500x500+40+80`、`500x500+680+80` |
| `drill/ch12.sh`、`ch13.sh` | 內嵌 Python 改的 RViz 設定與 `-qwindowgeometry` |
| `tools/set-rqt-geometry.py` | 執行時用 `--x --y --w --h` 指定 |
| `tools/window-guardian.py` | 判斷「不在螢幕 3」的條件與 `--mon2-left` |
| 導覽終端機 | `wt.exe ... --pos 2000,40` 改成你要的螢幕 |

只有一個螢幕時：圖形視窗和終端機只能共用，最簡單是不要 `--maximized`、讓兩者左右並排。

## 5. 測試時不要讓視窗跑到錯的螢幕

- 先用**看不見的虛擬螢幕**驗證座標：`Xvfb :99 -screen 0 5120x1080x24 &`，`DISPLAY=:99` 啟動程式，再用 `xdotool search --name <標題>` + `xwininfo -id <id>` 讀位置。
- 腳本自動測試：`QT_QPA_PLATFORM=offscreen` 加 `yes "" | ./chNN.sh`（第 13 章另加 `DEMO_AUTO=1` 略過鍵盤遙控）。
- 正式演練時開 `tools/window-guardian.py` 當備援。

## 6. 已知差異

- WSLg 預設（Wayland 模式）新視窗開在主螢幕中央 → 一定要用 `drill/gui-env.sh` 的 X11 模式。
- Gazebo GUI 的位置設定無效 → 第 13 章用 `-s` 不開畫面；若新電腦只有一個螢幕、不在意位置，可把 `ch13.sh` 裡的 `empty.sdf -r -s` 改回 `empty.sdf -r` 看 Gazebo 畫面。
- rqt_tf_tree 在本機啟動失敗 → 第 10 章改用 `view_frames`。

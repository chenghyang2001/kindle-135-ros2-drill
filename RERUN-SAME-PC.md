# 情況一：在同一台電腦重跑演練

適用：HP EliteBook 840 G8（DESKTOP-6LST1BR），WSL 的 `Ubuntu-24.04` 已裝好 ROS 2 Jazzy（2026-10-24 完成）。
所有腳本都已產生並測過，**不需要再請 Claude 重新產生**，照下面做即可。

## 1. 確認環境還在

在 Windows Terminal：

```bash
wsl -d Ubuntu-24.04
```

進入 Ubuntu 後：

```bash
cd /mnt/c/Users/<你的 Windows 帳號>/workspace/kindle-135-ros2-drill
bash tools/check-env.sh
```

全部 PASS 或只有 WARN 就可以開始。

## 2. 把演練腳本放回 ~/ros2-demo

```bash
cd <repo 在 WSL 裡的路徑>      # 例：/mnt/c/Users/<你>/workspace/kindle-135-ros2-drill
mkdir -p ~/ros2-demo && cp drill/* ~/ros2-demo/ && chmod +x ~/ros2-demo/*.sh
python3 tools/set-rqt-geometry.py   # 讓 rqt_graph 開在螢幕 3（需在 WSLg 有畫面的終端機執行）
```

## 3. 決定要不要從頭重建工作區

腳本會在 `~/ros2_ws` 建立／覆寫套件。

- **想看完整建立過程**（建議）：先把舊的改名備份 `mv ~/ros2_ws ~/ros2_ws.bak-$(date +%Y%m%d)`，並從 `~/.bashrc` 刪掉 `source ~/ros2_ws/install/setup.bash` 那行。
- **只想複習**：保留現有 `~/ros2_ws`，第 4 章會顯示「已存在，略過建立」。

## 4. 逐章執行

在 **Windows（Git Bash 或 PowerShell）** 開導覽終端機到螢幕 2：

```powershell
wt.exe -w ros2drill --pos 2000,40 --maximized new-tab --title 第1章演練 wsl.exe -d Ubuntu-24.04 --cd ~ -- ./ros2-demo/ch01.sh
```

把 `ch01` 換成 `ch03`、`ch04`…`ch13` 逐章跑（沒有 ch02）。每段按 Enter 往下；第 13 章最後一段是鍵盤遙控，按 Ctrl+C 結束。

建議同時在 Windows 開背景守門員當備援（萬一有視窗跑出螢幕 3 會自動移回）：

```bash
PYTHONUTF8=1 python tools/window-guardian.py --minutes 90
```

## 5. 注意

- **螢幕排列必須是「3 | 1 | 2」**（螢幕 3 在最左、1280x720）。排列變了就要依 NEW-PC-CHECKLIST.md 第 4 節重算座標。
- 第 9、12、13 章會修改**工作區複製檔**的 launch／rviz 設定（標「本演練加」），書本 repo 原檔不動。
- 結束一章後，先關掉該章的終端機視窗再開下一章（腳本離開時會自動停止該章的 ROS 節點）。

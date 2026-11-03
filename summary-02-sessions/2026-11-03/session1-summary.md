# Session 1 摘要（2026-11-03，DESKTOP-6LST1BR／HP EliteBook 840 G8）

主題：K135 演練環境在兩螢幕電腦上重建 → ROS 2 成果整理成 LinkedIn／104 履歷 → 104 投遞 20 個機器人職缺 → 建立 `104-ros2-apply` skill。

## 完成事項

### A. K135 演練環境（kindle-135-ros2-drill）

- 新增 `CLAUDE.md`（雙執行端架構、導覽腳本輸出格式約束、視窗座標、錄影管線），commit `9b67c76`。
- 修 `tools/setup-ros2.sh` 卡在 `sudo -v`（免密碼 sudo 仍要求密碼）→ 先試 `sudo -n true`；安裝補齊 urdf-tutorial／xdotool／xvfb／x11-xserver-utils，clone 書附範例，`check-env.sh` 23 項全 PASS。
- 新增兩螢幕版面（`[主螢幕1][螢幕2]`，螢幕 2 左半終端機、右半圖形視窗）：
  - `tools/apply-layout.py`（m2right／m3 字面替換表，替換表對不上就報錯、不留半套檔）`0d8116d`、ch03／ch05 補 gui-env `2003cae`
  - `tools/x11-placer.sh`：這台 WSLg 不理 `-qwindowgeometry` 位置，背景用 xdotool 搬視窗 `097c2f4`
  - `tools/open_chapter.py`：開章前殺舊 daemon＋手動 `ros2 daemon start`（自動啟動的 daemon 會卡死在 127.0.0.1:11511）`bb220a9`
  - 實測第 3 章（小烏龜、rqt_graph）、第 10 章（RViz、關節滑桿改到 (2916,300)）位置正確
- `HANDOFF.md` 交接文件 `5017aa9`；README 精華版影片 ID 改為現行公開版 `H2eM8dY_mU4` `4c947ae`。
- 第二輪演練停在第 4 章 (1/6)，`~/ros2_ws` 只有空殼。

### B. ROS 2 履歷素材（新 private repo `chenghyang2001/ros2-career-profile`）

- 4 個 subagent 平行盤點 K135／K136／K901／書籍 → `inventory/*.md`；獨立事實查核 `FACT-CHECK.md`（4 必改＋33 建議，全數修正）`00d2f5d`。
- YouTube：從 VPS 複製 token 到本機 `~/.config/youtube-comment/token.json`（頻道 `UCdq7Mig9UZNjtpj1KJRsJ6A` 驗證），3 支作品集影片改公開：`W6IAOGiunRs`（K901 避障節點）、`H2eM8dY_mU4`（K135）、`GASd9vHkP-c`（K136）。
- 修正 K901 repo「麥克納姆輪」→「四輪滑移轉向」7 處 `beab761`（yahboom-microros-pi5）。

### C. LinkedIn（透過 Chrome 代填，皆回讀驗證）

- 技能 +12（ROS 2、ROS、micro-ROS、Robot Simulation〔Gazebo 只會對到涼亭〕、Raspberry Pi、LiDAR、OpenCV、URDF、Docker、Rviz、ros2_control、Linux）。
- 專案 3 筆（中文＋「EN |」英文摘要）、關於（中英各加 ROS 2 段；英文版依使用者選擇刪掉 Claude Max 段，2,591/2,600）、標題加 ROS 2（中英）。

### D. 104

- 中文履歷表：專案成就 3 筆（嵌入 YouTube）並拖到最前、專長「ROS 2 機器人開發（自學實作）」、自傳加【機器人與 ROS 2】段。
- 投遞 20 個職缺（全部「應徵成功」）：第一批 5、第二批 5、第三批 10（skill dry-run 清單經核准後投遞），紀錄 `ros2-career-profile/applications.md`（職缺明細與公司都在該檔）：第一批 `1e5b310`、第二批 `960e37f`、第三批 dry-run 清單 `ac446ee` → 投遞完成 `8735f00`。

### E. 新 skill `~/.claude/skills/104-ros2-apply/`（`3bbf3884`、`cefbcca2`）

- SKILL.md＋references（profile、fit-rubric、cover-letter、104-dom-notes）＋evals.json；排除仲介、主管職加權、每輪必經確認關卡、單輪上限 10。

## 關鍵技術筆記

- 這台 WSLg 忽略 X11 視窗位置但接受大小；`xdotool windowmove` 事後搬移有效且不會被拉回。
- 自動啟動的 ros2 daemon 會卡死；手動 `ros2 daemon start` 穩定。DDS（talker/listener）本身正常。
- Git Bash 呼叫 `wsl.exe -- bash -c` 遇 `$`、引號易出錯 → 寫腳本檔到 scratchpad 再執行。
- LinkedIn：關於／標題是 contenteditable → `execCommand('insertText')`；專案說明 textarea 用原生 setter；第二語言檔案不支援專案翻譯。
- 104：投遞表單直接開 `job/<id>?apply=form`；推薦信 textarea 用原生 setter＋input 事件並核對 `N/2000`；完整 JD 可用 `fetch('/job/ajax/content/<id>')`；搜尋結果前端渲染，`fetch` 搜尋頁拿不到；Quill 編輯器用 execCommand 逐段插入；月份是 vue-multiselect 需真實點擊；專案排序用拖曳，遇「異動資料失敗」需重整。
- Chrome 擴充斷線時分頁群組可能換回舊群組，須先讀頁面狀態避免重複送出。

## 關鍵決定

1. **兩螢幕版不改 `drill/` 原檔**：原檔是 2026-10-24 測過的三螢幕版，保留給原配置使用；兩螢幕差異只在複製到 `~/ros2-demo` 時由 `tools/apply-layout.py --layout m2right` 以字面替換表套用（`0d8116d`），切回三螢幕用 `--layout m3`。**之後改座標不要直接改 `drill/`**，改替換表。
2. **履歷定位為「自學專案」並主動揭露 AI 輔助**：不包裝成工作經歷；LinkedIn 專案說明與 104 專案成就結尾都寫明 Claude Code 的角色（K136 AI 代跑、K901 Claude 透過 SSH 下指令、使用者負責實體操作與驗證）；104 專長名稱標「（自學實作）」。只在模擬做過的 Nav2／MoveIt／PX4 不列為技能。
3. **英文 About 刪 Claude Max 段**（使用者選擇）：英文版已 2,589/2,600，ROS 2 段放不下；Claude Max 使用量對求職最不相關，中文版保留。
4. **104 求職規則**：排除人力仲介（履歷不經第三方轉手）、主管職在評分加權（24 年資歷＋現任組長）、單輪上限 10。
5. **投遞前必經使用者確認關卡**：投遞不可撤回（僅 5 分鐘內可取消），清單與推薦信由 Claude 產生，所以每輪都要使用者明確同意；已寫進 `104-ros2-apply` skill。
6. **YouTube 公開 3 支作品集影片**（使用者同意）；履歷素材 repo 設為 private。

## 產出檔案

| 檔案 | 說明 |
| --- | --- |
| `kindle-135-ros2-drill/CLAUDE.md`、`HANDOFF.md` | 架構指引、兩螢幕版交接 |
| `kindle-135-ros2-drill/tools/apply-layout.py`、`x11-placer.sh`、`open_chapter.py` | 兩螢幕版面工具 |
| `kindle-135-ros2-drill/tools/setup-ros2.sh`、`RERUN-SAME-PC.md`、`README.md`、`TODO.md` | 修正與文件 |
| `ros2-career-profile/`（README、linkedin.md、104.md、CHECKLIST.md、FACT-CHECK.md、applications.md、inventory/*） | 履歷素材與應徵紀錄 |
| `yahboom-microros-pi5/CLAUDE.md` 等 7 檔 | 車型描述修正 |
| `~/.claude/skills/104-ros2-apply/**` | 新 skill |
| `~/.config/youtube-comment/token.json`（本機，不進版控） | YouTube API 憑證 |

## HANDOFF（下次 session 優先處理）

### 立即行動

- [ ] 改掉 Yahboom 機器人車的出廠 SSH 密碼（公開 repo `yahboom-microros-pi5` 的 CLAUDE.md／POWER-ON-CHECK.md 仍寫著預設值），再把文件改成變數
- [ ] 查看 104「誰聯絡我」（session 中有該分頁被開啟，可能有企業留言）並追蹤 20 份應徵回覆
- [ ] K135 第二輪演練：`PYTHONUTF8=1 python tools/open_chapter.py 04` 從第 4 章依序跑（步驟見 HANDOFF.md）

### 進行中（需接續）

- K135 兩螢幕版：第 3、10 章視窗已實測；第 5、6、8、9、11～13 章未實測（尤其第 9 章兩隻烏龜、第 13 章 Gazebo）。
- `104-ros2-apply`：主管版推薦信尚未給使用者核准；fit-rubric 可依面試回饋調整。
- LinkedIn Featured（精選）與專案多媒體尚未加。

### 注意事項

- 投遞類動作不可逆：每輪必經使用者確認清單＋推薦信（skill 已內建）。
- 面試時要誠實：ROS 2 為 2026/10 起約兩週自學、AI 輔助程度高（K136 AI 代跑、K901 Claude 透過 SSH 下指令）。
- 這台 WSL `~/.wslconfig` 是 mirrored 網路；`drill_ctl.py` 錄影雙視窗版面仍是三螢幕設計。
- ROS 2 履歷素材 repo 是 private；3 支 YouTube 影片已公開。

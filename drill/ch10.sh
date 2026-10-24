#!/bin/bash
# 《ROS 2 from Scratch》第 10 章：認識 TF —— 用 RViz 看機器人模型與座標系（快速 demo 模式）
source /opt/ros/jazzy/setup.bash
source ~/ros2-demo/gui-env.sh
URDF=/opt/ros/jazzy/share/urdf_tutorial/urdf/08-macroed.urdf.xacro
C='\033[1;36m'; Y='\033[1;33m'; G='\033[1;32m'; N='\033[0m'
title() { clear; echo -e "${C}════════════════════════════════════════════${N}"; echo -e "${C} 第 10 章演練 $1${N}"; echo -e "${C}════════════════════════════════════════════${N}\n"; }
run()   { echo -e "${G}\$ $*${N}"; eval "$@"; echo; }
note()  { echo -e "${Y}💡 $*${N}"; }
next()  { echo; read -rp "👉 按 Enter 繼續…" _; }
bg()    { echo -e "${G}\$ $1 &${N}"; eval "$1" > "$2" 2>&1 & }
stopall() { pkill -f "[r]obot_state_publisher|[r]viz2" 2>/dev/null; pkill -9 -f "[j]sp_gui_m3|[j]oint_state_publisher" 2>/dev/null; sleep 1; }
trap stopall EXIT

title "(1/5) TF 是什麼？先看機器人模型"
note "TF（transform）＝各個座標系之間的相對位置與角度。機器人每個部件（link）都有自己的座標系，"
note "部件之間用關節（joint）連起來，TF 負責隨時算出「A 相對於 B 在哪裡」。"
note "本章用 urdf_tutorial 內建的 R2-D2 造型機器人："
run "xacro $URDF > /tmp/r2d2.urdf && echo \"link 數：\$(grep -c '<link ' /tmp/r2d2.urdf)　joint 數：\$(grep -c '<joint ' /tmp/r2d2.urdf)\""
run "grep -oE '<joint name=\"[^\"]+\" type=\"[^\"]+\"' /tmp/r2d2.urdf | sed 's/<joint name=//; s/ type=/ → /'"
note "fixed 固定｜continuous 無限轉（輪子）｜revolute 有角度限制（夾爪）｜prismatic 直線滑動（夾爪伸縮）"
next

title "(2/5) robot_state_publisher：把模型變成 TF"
note "robot_state_publisher 讀入模型，持續發布每個部件的座標系到 /tf 和 /tf_static"
bg "ros2 run robot_state_publisher robot_state_publisher --ros-args -p robot_description:=\"\$(xacro $URDF)\"" /tmp/ch10_rsp.log
sleep 3
run "ros2 topic list | grep -E 'tf|robot_description|joint'"
note "會動的關節需要知道「現在轉到幾度」——這由 /joint_states 提供，下一步用滑桿來發布。"
next

title "(3/5) RViz ＋ 關節滑桿（螢幕 3）"
note "RViz 開在螢幕 3 左邊、關節滑桿開在螢幕 3 右邊。"
note "（RViz 用本演練調整過視窗大小的設定檔 urdf_m3.rviz；滑桿用包裝程式 jsp_gui_m3.py 指定位置）"
bg "rviz2 -d ~/ros2-demo/urdf_m3.rviz -qwindowgeometry 880x600+40+20" /tmp/ch10_rviz.log
sleep 3
bg "python3 ~/ros2-demo/jsp_gui_m3.py" /tmp/ch10_jsp.log
sleep 6
note "👉 去螢幕 3 拖動滑桿：輪子轉、頭轉、夾爪開合伸縮，RViz 裡的模型和彩色座標軸（紅 X／綠 Y／藍 Z）會跟著動"
note "   滑鼠在 RViz 裡：左鍵拖曳旋轉視角、滾輪縮放"
run "timeout 3 ros2 topic echo /joint_states --once | sed -n '/^name:/,/^velocity:/p'"
next

title "(4/5) 資料流與 TF 樹"
note "資料流：關節滑桿 →（/joint_states）→ robot_state_publisher →（/tf、/tf_static）→ RViz"
run "ros2 topic info /joint_states; ros2 topic info /tf"
note "用 view_frames 匯出 TF 樹（產生 PDF），這裡列出父子關係："
run "cd /tmp && ros2 run tf2_tools view_frames > /dev/null 2>&1; grep -oE '\"[a-z_]+\" -> \"[a-z_]+\"' \$(ls -t /tmp/frames_*.gv | head -1) | tr -d '\"' | sort"
run "ls -t /tmp/frames_*.pdf | head -1"
note "查詢任兩個座標系的相對位置：夾爪尖端 left_tip 相對 base_link（拖動夾爪滑桿，數字會變）"
run "timeout 3 ros2 run tf2_ros tf2_echo base_link left_tip 2>/dev/null | grep -A2 -m1 Translation"
next
stopall

title "(5/5) 完成 ✅"
note "第 10 章重點：每個 link 一個座標系｜joint 決定怎麼動｜robot_state_publisher 把模型＋/joint_states 變成 /tf｜RViz 視覺化｜view_frames / tf2_echo 檢查 TF"
note "下一步第 11 章：自己用 URDF 寫一台機器人（repo 的 ch11 範例）。"
exec bash

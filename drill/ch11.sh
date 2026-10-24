#!/bin/bash
# 《ROS 2 from Scratch》第 11 章：用 URDF／Xacro 寫自己的機器人（快速 demo 模式）
source /opt/ros/jazzy/setup.bash
source ~/ros2-demo/gui-env.sh
REPO=~/ROS-2-from-Scratch/ch11
WS=${WS:-$HOME/ros2_ws}
D=$WS/urdf_practice
C='\033[1;36m'; Y='\033[1;33m'; G='\033[1;32m'; N='\033[0m'
title() { clear; echo -e "${C}════════════════════════════════════════════${N}"; echo -e "${C} 第 11 章演練 $1${N}"; echo -e "${C}════════════════════════════════════════════${N}\n"; }
run()   { echo -e "${G}\$ $*${N}"; eval "$@"; echo; }
note()  { echo -e "${Y}💡 $*${N}"; }
next()  { echo; read -rp "👉 按 Enter 繼續…" _; }
# 換模型：重啟 robot_state_publisher 與關節滑桿，RViz 保持開著（會自動讀新的 /robot_description）
show_model() {
  pkill -f "[r]obot_state_publisher" 2>/dev/null; pkill -9 -f "[j]sp_gui_m3" 2>/dev/null; sleep 1
  echo -e "${G}\$ ros2 run robot_state_publisher robot_state_publisher --ros-args -p robot_description:=\"\$(xacro $1)\" &${N}"
  ros2 run robot_state_publisher robot_state_publisher --ros-args -p robot_description:="$(xacro $1)" > /tmp/ch11_rsp.log 2>&1 &
  sleep 2
  python3 ~/ros2-demo/jsp_gui_m3.py > /tmp/ch11_jsp.log 2>&1 &
  if ! pgrep -f "[r]viz2" > /dev/null; then
    echo -e "${G}\$ rviz2 -d ~/ros2-demo/urdf_m3.rviz &${N}"
    rviz2 -d ~/ros2-demo/urdf_m3.rviz -qwindowgeometry 880x600+40+20 > /tmp/ch11_rviz.log 2>&1 &
  fi
  sleep 5
}
stopall() { pkill -f "[r]obot_state_publisher|[r]viz2" 2>/dev/null; pkill -9 -f "[j]sp_gui_m3" 2>/dev/null; sleep 1; }
trap stopall EXIT

title "(1/5) 最小的 URDF：兩個 link ＋ 一個 joint"
run "mkdir -p $D && cp $REPO/* $D/ && ls $D"
run "cat $D/example_with_two_links.urdf | sed -n '/<link name=\"base_link\"/,/<\/robot>/p'"
note "link＝部件（visual 裡放形狀、位置、顏色）｜joint＝連接 parent 和 child，origin 是相對位置，axis 是轉軸"
run "check_urdf $D/example_with_two_links.urdf"
note "RViz 開在螢幕 3 左邊、滑桿在右邊。拖動 base_shoulder_joint 滑桿，灰色圓柱會繞 Z 軸轉："
show_model $D/example_with_two_links.urdf
next

title "(2/5) my_robot.urdf：兩輪移動底盤"
run "grep -oE '<(link|joint) name=\"[^\"]+\"( type=\"[^\"]+\")?' $D/my_robot.urdf | sed 's/<//'"
note "base_footprint 是貼地的虛擬座標系（沒有形狀），base_link 是車身；左右輪 continuous 可無限轉，前面萬向球輪固定"
run "check_urdf $D/my_robot.urdf | tail -8"
show_model $D/my_robot.urdf
note "看螢幕 3：綠色車身＋兩個灰輪＋前方小球。拖動兩個輪子的滑桿，輪子會轉。"
next

title "(3/5) Xacro：把重複的地方變成變數和巨集"
note "my_robot.urdf.xacro 只負責 include 另外兩個檔："
run "cat $D/my_robot.urdf.xacro"
note "mobile_base.xacro 用 property 定義尺寸，用 macro 一次定義「輪子」再呼叫兩次："
run "grep -nE 'xacro:property|xacro:macro|xacro:wheel_link|\\$\{' $D/mobile_base.xacro | head -14"
note "改車身大小只要改一個數字，所有位置都會跟著算 —— 這就是 Xacro 的好處"
next

title "(4/5) Xacro 展開後和手寫的 URDF 一樣嗎？"
run "xacro $D/my_robot.urdf.xacro > /tmp/my_robot_from_xacro.urdf && check_urdf /tmp/my_robot_from_xacro.urdf | head -3"
note "比對兩者的 link／joint 清單："
run "diff <(grep -oE '<(link|joint) name=\"[^\"]+\"' $D/my_robot.urdf | sort) <(grep -oE '<(link|joint) name=\"[^\"]+\"' /tmp/my_robot_from_xacro.urdf | sort) && echo '✅ 完全相同'"
note "實驗：把車身長度改成 1.0（原本 0.6），重新載入 —— 車身變長，輪子位置自動跟著調整："
run "sed 's/name=\"base_length\" value=\"0.6\"/name=\"base_length\" value=\"1.0\"/' $D/mobile_base.xacro > $D/mobile_base_long.xacro && sed 's/mobile_base.xacro/mobile_base_long.xacro/' $D/my_robot.urdf.xacro > $D/my_robot_long.urdf.xacro && echo 已產生加長版"
show_model $D/my_robot_long.urdf.xacro
note "看螢幕 3：車身變長了。"
next
stopall

title "(5/5) 完成 ✅"
note "第 11 章重點：link（visual: geometry/origin/material）｜joint（parent/child/origin/axis/type）｜base_footprint 慣例｜check_urdf 檢查｜Xacro property／macro／include"
note "練習檔在 ~/ros2_ws/urdf_practice；下一步第 12 章：把模型做成 my_robot_description 套件，用 launch 檔顯示。"
exec bash

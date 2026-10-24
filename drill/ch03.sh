#!/bin/bash
# 《ROS 2 from Scratch》第 3 章：用 turtlesim 認識 ROS 2 核心概念（快速 demo 模式）
source /opt/ros/jazzy/setup.bash
export GALLIUM_DRIVER=d3d12
C='\033[1;36m'; Y='\033[1;33m'; G='\033[1;32m'; N='\033[0m'
title() { clear; echo -e "${C}════════════════════════════════════════════${N}"; echo -e "${C} 第 3 章演練 $1${N}"; echo -e "${C}════════════════════════════════════════════${N}\n"; }
run()   { echo -e "${G}\$ $*${N}"; eval "$@"; echo; }
note()  { echo -e "${Y}💡 $*${N}"; }
next()  { echo; read -rp "👉 按 Enter 繼續…" _; }
cleanup() { pkill -f "[t]urtlesim_node" 2>/dev/null; pkill -9 -f "[r]qt_graph" 2>/dev/null; }
trap cleanup EXIT

title "(1/7) 節點 Node"
note "節點＝一個獨立執行的程式，負責一件事。用 ros2 run <套件> <執行檔> 啟動。"
note "小烏龜視窗會出現在螢幕 3。"
echo -e "${G}\$ ros2 run turtlesim turtlesim_node &${N}"
ros2 run turtlesim turtlesim_node > /tmp/ch03_turtle.log 2>&1 &
sleep 4
run "ros2 node list"
note "ros2 node info 會列出這個節點發布／訂閱哪些 topic、提供哪些 service、action："
run "ros2 node info /turtlesim | head -30"
next

title "(2/7) Topic：節點之間單向傳資料"
run "ros2 topic list"
note "/turtle1/cmd_vel 是「速度指令」，誰發布到這裡，小烏龜就照著動。看它的資料格式："
run "ros2 topic info /turtle1/cmd_vel"
run "ros2 interface show geometry_msgs/msg/Twist | grep -v '^#' | grep -v '^\s*\$'"
note "小烏龜不斷發布自己的位置 /turtle1/pose，抓一筆來看："
run "ros2 topic echo /turtle1/pose --once"
run "timeout 4 ros2 topic hz /turtle1/pose 2>/dev/null | head -4"
note "現在從命令列發布速度指令，讓小烏龜畫一段弧線（看螢幕 3）："
run "ros2 topic pub -w 1 -t 90 -r 30 /turtle1/cmd_vel geometry_msgs/msg/Twist \"{linear: {x: 2.0}, angular: {z: 1.8}}\" > /dev/null"
run "ros2 topic echo /turtle1/pose --once | head -3"
next

title "(3/7) rqt_graph：把節點和 topic 畫成圖"
note "rqt_graph 視窗會出現在螢幕 3。按左上角重新整理鈕即可更新。"
echo -e "${G}\$ rqt_graph &${N}"
rqt_graph > /dev/null 2>&1 &
sleep 6
note "等一下在另一個 topic pub 持續發布時，圖上就會看到「命令列節點 → /turtle1/cmd_vel → /turtlesim」"
ros2 topic pub -r 1 /turtle1/cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.0}}" > /dev/null 2>&1 &
PUB=$!
note "（已在背景開一個持續發布的節點，在 rqt_graph 按重新整理就看得到）"
next
kill $PUB 2>/dev/null

title "(4/7) Service：一問一答"
note "topic 是單向廣播；service 是「送出請求 → 拿到回應」，例如叫小烏龜生出第二隻。"
run "ros2 service list"
run "ros2 service type /spawn"
run "ros2 interface show turtlesim/srv/Spawn"
run "ros2 service call /spawn turtlesim/srv/Spawn \"{x: 2.0, y: 2.0, theta: 0.0, name: 'turtle2'}\""
note "螢幕 3 多了一隻 turtle2。再呼叫 /clear 把剛才畫的線清掉："
run "ros2 service call /clear std_srvs/srv/Empty"
next

title "(5/7) Action：長時間任務＋過程回報"
note "action 適合要花時間的工作：送出目標、途中收到進度（feedback）、最後拿到結果。"
run "ros2 action list"
run "ros2 action info /turtle1/rotate_absolute -t"
note "叫 turtle1 轉到 180 度（3.14 弧度），並顯示過程回報："
run "ros2 action send_goal /turtle1/rotate_absolute turtlesim/action/RotateAbsolute \"{theta: 3.14}\" --feedback | grep -E 'remaining|Goal|status|delta' | sed -n '1,4p;\$p'"
next

title "(6/7) 參數 Parameter：節點的設定值"
run "ros2 param list /turtlesim"
run "ros2 param get /turtlesim background_r"
note "把背景的紅色值改成 180，再呼叫 /clear 重畫，背景就會變色（看螢幕 3）："
run "ros2 param set /turtlesim background_r 180"
run "ros2 service call /clear std_srvs/srv/Empty > /dev/null && echo 已重畫背景"
next

title "(7/7) Launch 檔：一次啟動多個節點"
note "實際專案常有十幾個節點，用 launch 檔一個指令全部帶起來。"
run "cat /opt/ros/jazzy/share/demo_nodes_cpp/launch/topics/talker_listener_launch.py | grep -vE '^#|^\s*\$'"
note "執行它 6 秒：talker 和 listener 同時啟動、互相傳訊息："
run "timeout 6 ros2 launch demo_nodes_cpp talker_listener_launch.py 2>&1 | grep -E 'Publishing|heard' | head -6"
next

title "完成 ✅"
note "第 3 章重點：Node 做事｜Topic 單向傳資料｜Service 一問一答｜Action 長任務＋回報｜Parameter 設定值｜Launch 一次啟動多節點"
note "下一步：第 4 章開始自己寫 Python／C++ 節點（會用到 ~/ROS-2-from-Scratch/ch4 的範例）。"
cleanup
exec bash

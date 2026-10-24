#!/bin/bash
# 《ROS 2 from Scratch》第 6 章：Service —— server／client、自訂 .srv、小烏龜換筆色與啟停（快速 demo 模式）
source /opt/ros/jazzy/setup.bash
source ~/ros2-demo/gui-env.sh
REPO=~/ROS-2-from-Scratch/ch6
WS=${WS:-$HOME/ros2_ws}
C='\033[1;36m'; Y='\033[1;33m'; G='\033[1;32m'; N='\033[0m'
title() { clear; echo -e "${C}════════════════════════════════════════════${N}"; echo -e "${C} 第 6 章演練 $1${N}"; echo -e "${C}════════════════════════════════════════════${N}\n"; }
run()   { echo -e "${G}\$ $*${N}"; eval "$@"; echo; }
note()  { echo -e "${Y}💡 $*${N}"; }
next()  { echo; read -rp "👉 按 Enter 繼續…" _; }
bg()    { echo -e "${G}\$ $1 &${N}"; eval "$1" > "$2" 2>&1 & }
stopall() { pkill -f "[n]umber_publisher|[n]umber_counter|[r]eset_counter_client|[t]urtle_controller|[t]urtlesim_node" 2>/dev/null; sleep 1; }
build() { cd $WS && colcon build --packages-select "$@" 2>&1 | grep -E "Finished|Failed|Summary|rror"; source $WS/install/setup.bash; }
trap stopall EXIT
source $WS/install/setup.bash 2>/dev/null

title "(1/5) 定義 Service 格式：.srv"
note ".srv 用 --- 分成兩半：上面是「請求」，下面是「回應」"
run "cp -r $REPO/my_robot_interfaces/srv $WS/src/my_robot_interfaces/ && cp $REPO/my_robot_interfaces/CMakeLists.txt $WS/src/my_robot_interfaces/"
run "cat $WS/src/my_robot_interfaces/srv/ResetCounter.srv; echo; echo; cat $WS/src/my_robot_interfaces/srv/ActivateTurtle.srv; echo"
run "grep -A4 rosidl_generate_interfaces $WS/src/my_robot_interfaces/CMakeLists.txt"
run "build my_robot_interfaces"
run "ros2 interface show my_robot_interfaces/srv/ResetCounter"
next

title "(2/5) Service server：number_counter 加上「重設計數器」"
run "cp $REPO/my_py_pkg/my_py_pkg/number_counter.py $REPO/my_py_pkg/my_py_pkg/reset_counter_client.py $WS/src/my_py_pkg/my_py_pkg/ && cp $REPO/my_py_pkg/setup.py $REPO/my_py_pkg/package.xml $WS/src/my_py_pkg/"
run "sed -n '/create_service/p; /def callback_reset_counter/,/return response/p' $WS/src/my_py_pkg/my_py_pkg/number_counter.py"
note "規則：不能設成負數、不能比目前值大，否則回傳 success=False"
run "build my_py_pkg"
bg "ros2 run my_py_pkg number_publisher" /tmp/ch06_pub.log
bg "ros2 run my_py_pkg number_counter" /tmp/ch06_cnt.log
sleep 5
run "ros2 service list | grep reset"
run "grep Counter /tmp/ch06_cnt.log | tail -1"
note "從命令列呼叫：重設成 0（合法）"
run "ros2 service call /reset_counter my_robot_interfaces/srv/ResetCounter \"{reset_value: 0}\" | grep Response"
note "重設成 -5（不合法，會被拒絕）"
run "ros2 service call /reset_counter my_robot_interfaces/srv/ResetCounter \"{reset_value: -5}\" | grep Response"
run "grep Reset /tmp/ch06_cnt.log | tail -1; grep Counter /tmp/ch06_cnt.log | tail -1"
next

title "(3/5) Service client：用程式呼叫服務"
run "sed -n '/create_client/p; /def call_reset_counter/,/add_done_callback/p' $WS/src/my_py_pkg/my_py_pkg/reset_counter_client.py"
note "流程：等服務上線 → 建立請求 → call_async 非同步送出 → 回應到了再呼叫 callback（不會卡住節點）"
note "等計數器超過 20，再讓 client 把它重設成 20："
sleep 8
run "grep Counter /tmp/ch06_cnt.log | tail -1"
run "timeout 5 ros2 run my_py_pkg reset_counter_client 2>&1 | grep INFO"
run "grep Reset /tmp/ch06_cnt.log | tail -2; grep Counter /tmp/ch06_cnt.log | tail -1"
stopall
next

title "(4/5) C++ 版 server ＋ client"
run "cp $REPO/my_cpp_pkg/src/*.cpp $WS/src/my_cpp_pkg/src/ && cp $REPO/my_cpp_pkg/CMakeLists.txt $REPO/my_cpp_pkg/package.xml $WS/src/my_cpp_pkg/"
run "grep -nE 'create_service|create_client|async_send_request' $WS/src/my_cpp_pkg/src/number_counter.cpp $WS/src/my_cpp_pkg/src/reset_counter_client.cpp | sed \"s|$WS/src/my_cpp_pkg/src/||\""
run "build my_cpp_pkg"
bg "ros2 run my_cpp_pkg number_publisher" /tmp/ch06_cpppub.log
bg "ros2 run my_cpp_pkg number_counter" /tmp/ch06_cppcnt.log
sleep 13
run "grep -i counter /tmp/ch06_cppcnt.log | tail -1"
run "timeout 5 ros2 run my_cpp_pkg reset_counter_client 2>&1 | grep INFO | grep -v signal_handler"
run "grep -i reset /tmp/ch06_cppcnt.log | tail -1; grep -i counter /tmp/ch06_cppcnt.log | tail -1"
stopall
next

title "(5/5) 小烏龜：換筆色（client）＋ 啟停開關（server）"
note "turtle_controller 現在是 client：越過中線就呼叫 /turtle1/set_pen —— 左邊綠色、右邊紅色"
note "同時也是 server：提供 /activate_turtle，讓別人叫它停或走"
run "rm -rf $WS/src/turtle_controller && cp -r $REPO/turtle_controller $WS/src/"
run "build turtle_controller"
note "小烏龜視窗直接開在螢幕 3："
bg "ros2 run turtlesim turtlesim_node $TURTLE_GEOM" /tmp/ch06_turtle.log
sleep 4
bg "ros2 run turtle_controller turtle_controller" /tmp/ch06_ctrl.log
sleep 8
run "grep -E 'color' /tmp/ch06_ctrl.log | tail -4"
note "看螢幕 3：軌跡左綠右紅。現在叫它停："
run "ros2 service call /activate_turtle my_robot_interfaces/srv/ActivateTurtle \"{activate: false}\" | grep Response"
sleep 3
run "ros2 topic echo /turtle1/pose --once | grep -E 'linear_velocity|angular_velocity'"
note "速度歸零，停了。再叫它繼續："
run "ros2 service call /activate_turtle my_robot_interfaces/srv/ActivateTurtle \"{activate: true}\" | grep Response"
note "看螢幕 3，小烏龜又開始畫圈。"
next
stopall

title "完成 ✅"
note "第 6 章重點：.srv 請求/回應｜create_service 寫 server｜create_client＋call_async 寫 client｜server 可拒絕不合法請求｜節點可同時是 client 和 server"
note "下一步第 7 章：Action —— 長時間任務＋進度回報。"
exec bash

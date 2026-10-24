#!/bin/bash
# 《ROS 2 from Scratch》第 5 章：Topic —— publisher／subscriber、自訂訊息、小烏龜閉迴路控制（快速 demo 模式）
source /opt/ros/jazzy/setup.bash
export GALLIUM_DRIVER=d3d12
REPO=~/ROS-2-from-Scratch/ch5
WS=${WS:-$HOME/ros2_ws}
C='\033[1;36m'; Y='\033[1;33m'; G='\033[1;32m'; N='\033[0m'
title() { clear; echo -e "${C}════════════════════════════════════════════${N}"; echo -e "${C} 第 5 章演練 $1${N}"; echo -e "${C}════════════════════════════════════════════${N}\n"; }
run()   { echo -e "${G}\$ $*${N}"; eval "$@"; echo; }
note()  { echo -e "${Y}💡 $*${N}"; }
next()  { echo; read -rp "👉 按 Enter 繼續…" _; }
bg()    { echo -e "${G}\$ $1 &${N}"; eval "$1" > "$2" 2>&1 & }
stopall() { pkill -f "[n]umber_publisher|[n]umber_counter|[t]urtle_controller|[t]urtlesim_node" 2>/dev/null; sleep 1; }
build() { cd $WS && colcon build --packages-select "$@" 2>&1 | grep -E "Finished|Failed|Summary|rror"; source $WS/install/setup.bash; }
trap stopall EXIT
source $WS/install/setup.bash 2>/dev/null

title "(1/6) Python publisher：每秒發布數字到 /number"
note "程式取自書本 repo ch5/my_py_pkg/number_publisher.py"
run "cp $REPO/my_py_pkg/my_py_pkg/number_publisher.py $REPO/my_py_pkg/my_py_pkg/number_counter.py $WS/src/my_py_pkg/my_py_pkg/"
run "cp $REPO/my_py_pkg/setup.py $REPO/my_py_pkg/package.xml $WS/src/my_py_pkg/"
run "grep -nE 'import|create_publisher|create_timer|publish\(' $WS/src/my_py_pkg/my_py_pkg/number_publisher.py"
note "create_publisher(訊息型別 Int64, topic 名稱 \"number\", 佇列長度 10)；timer 每秒呼叫 publish_number"
run "build my_py_pkg"
bg "ros2 run my_py_pkg number_publisher" /tmp/ch05_pub.log
sleep 3
run "ros2 topic list | grep number"
run "timeout 4 ros2 topic echo /number | head -6"
next

title "(2/6) Python subscriber：累加收到的數字"
run "grep -nE 'create_subscription|def callback|counter_ \+=' $WS/src/my_py_pkg/my_py_pkg/number_counter.py"
note "create_subscription(Int64, \"number\", 收到時呼叫的函式, 10) —— 每收到一筆就把數字加進 counter"
bg "ros2 run my_py_pkg number_counter" /tmp/ch05_cnt.log
sleep 5
run "grep Counter /tmp/ch05_cnt.log | tail -4"
run "ros2 topic info /number"
note "1 個 publisher、1 個 subscriber，兩者只靠 topic 名稱和訊息型別對上，彼此不認識對方"
stopall
next

title "(3/6) C++ 版 publisher ＋ Python subscriber 互通"
run "cp $REPO/my_cpp_pkg/src/number_publisher.cpp $REPO/my_cpp_pkg/src/number_counter.cpp $WS/src/my_cpp_pkg/src/"
run "cp $REPO/my_cpp_pkg/CMakeLists.txt $REPO/my_cpp_pkg/package.xml $WS/src/my_cpp_pkg/"
run "grep -nE 'create_publisher|create_wall_timer|publish\(' $WS/src/my_cpp_pkg/src/number_publisher.cpp"
run "build my_cpp_pkg"
bg "ros2 run my_cpp_pkg number_publisher" /tmp/ch05_cpppub.log
bg "ros2 run my_py_pkg number_counter" /tmp/ch05_cnt2.log
sleep 5
run "grep Counter /tmp/ch05_cnt2.log | tail -3"
note "C++ 發、Python 收，結果一樣 —— topic 不管對方用什麼語言寫"
stopall
next

title "(4/6) 執行時改 topic 名稱（remap）"
note "不改程式，啟動時用 -r 舊名:=新名，兩邊都要改才接得上："
bg "ros2 run my_py_pkg number_publisher --ros-args -r number:=my_number" /tmp/ch05_pub3.log
bg "ros2 run my_py_pkg number_counter --ros-args -r number:=my_number" /tmp/ch05_cnt3.log
sleep 5
run "ros2 topic list | grep number"
run "grep Counter /tmp/ch05_cnt3.log | tail -2"
stopall
next

title "(5/6) 自訂訊息格式：my_robot_interfaces"
note "內建的 Int64、String 不夠用時，自己定義 .msg。專門放介面的套件習慣叫 xxx_interfaces。"
run "rm -rf $WS/src/my_robot_interfaces && cp -r $REPO/my_robot_interfaces $WS/src/ && find $WS/src/my_robot_interfaces -type f | sed \"s|$WS/src/||\""
run "cat $WS/src/my_robot_interfaces/msg/HardwareStatus.msg"
run "grep -A2 rosidl_generate_interfaces $WS/src/my_robot_interfaces/CMakeLists.txt"
note "編譯時 ROS 2 會自動產生 Python 與 C++ 都能用的程式碼："
run "build my_robot_interfaces"
run "ros2 interface show my_robot_interfaces/msg/HardwareStatus"
bg "ros2 topic pub -r 1 /hardware_status my_robot_interfaces/msg/HardwareStatus \"{version: 1, temperature: 45.5, are_motors_ready: true, debug_message: 'all good'}\"" /tmp/ch05_hw.log
sleep 3
run "timeout 3 ros2 topic echo /hardware_status --once"
pkill -f "[h]ardware_status"
next

title "(6/6) 小烏龜閉迴路控制：turtle_controller"
note "一個節點同時「訂閱 /turtle1/pose」＋「發布 /turtle1/cmd_vel」：依位置決定速度 —— 左半邊慢慢轉、右半邊快快轉"
run "rm -rf $WS/src/turtle_controller && cp -r $REPO/turtle_controller $WS/src/"
run "sed -n '/def callback_pose/,/publish(cmd)/p' $WS/src/turtle_controller/turtle_controller/turtle_controller.py"
run "build turtle_controller"
note "小烏龜視窗會出現在螢幕 3："
bg "ros2 run turtlesim turtlesim_node" /tmp/ch05_turtle.log
sleep 4
bg "ros2 run turtle_controller turtle_controller" /tmp/ch05_ctrl.log
sleep 6
run "ros2 topic info /turtle1/cmd_vel"
run "ros2 topic echo /turtle1/pose --once | head -3"
note "看螢幕 3：小烏龜自己畫出大小兩種圓 —— 這就是「感測 → 決策 → 控制」的閉迴路"
next
stopall

title "完成 ✅"
note "第 5 章重點：create_publisher / create_subscription｜topic 名稱＋型別對上就能通｜跨語言｜-r 改名｜自訂 .msg｜閉迴路控制"
note "下一步第 6 章：Service —— 自己寫 server 和 client。"
exec bash

#!/bin/bash
# 《ROS 2 from Scratch》第 8 章：Parameter —— 宣告、啟動時給值、執行中修改、YAML 檔（快速 demo 模式）
source /opt/ros/jazzy/setup.bash
source ~/ros2-demo/gui-env.sh
REPO=~/ROS-2-from-Scratch/ch8
WS=${WS:-$HOME/ros2_ws}
YAML_DIR=$WS/yaml
C='\033[1;36m'; Y='\033[1;33m'; G='\033[1;32m'; N='\033[0m'
title() { clear; echo -e "${C}════════════════════════════════════════════${N}"; echo -e "${C} 第 8 章演練 $1${N}"; echo -e "${C}════════════════════════════════════════════${N}\n"; }
run()   { echo -e "${G}\$ $*${N}"; eval "$@"; echo; }
note()  { echo -e "${Y}💡 $*${N}"; }
next()  { echo; read -rp "👉 按 Enter 繼續…" _; }
bg()    { echo -e "${G}\$ $1 &${N}"; eval "$1" > "$2" 2>&1 & }
stopall() { pkill -f "[n]umber_publisher|[t]urtle_controller|[t]urtlesim_node" 2>/dev/null; sleep 1; }
build() { cd $WS && colcon build --packages-select "$@" 2>&1 | grep -E "Finished|Failed|Summary|rror"; source $WS/install/setup.bash; }
echo_number() { timeout 3 ros2 topic echo "${1:-/number}" --once 2>/dev/null | grep data; }
trap stopall EXIT
source $WS/install/setup.bash 2>/dev/null

title "(1/5) 在節點裡宣告參數"
run "cp $REPO/my_py_pkg/my_py_pkg/number_publisher.py $REPO/my_py_pkg/my_py_pkg/reset_counter_client.py $WS/src/my_py_pkg/my_py_pkg/"
run "grep -nE 'declare_parameter|get_parameter|add_post_set' $WS/src/my_py_pkg/my_py_pkg/number_publisher.py"
note "declare_parameter(名稱, 預設值)：宣告後才能從外部設定；get_parameter 讀出目前值"
run "build my_py_pkg"
bg "ros2 run my_py_pkg number_publisher" /tmp/ch08_pub.log
sleep 3
run "ros2 param list /number_publisher | grep -vE 'qos|use_sim|start_type'"
run "ros2 param get /number_publisher number"
run "echo_number"
stopall
next

title "(2/5) 啟動時給參數值：-p 名稱:=值"
note "不改程式，數字改 5、每 0.5 秒發一次："
bg "ros2 run my_py_pkg number_publisher --ros-args -p number:=5 -p publish_period:=0.5" /tmp/ch08_pub2.log
sleep 3
run "echo_number"
run "timeout 4 ros2 topic hz /number 2>/dev/null | grep average | head -1"
stopall
note "C++ 版同樣寫法（程式取自 repo ch8/my_cpp_pkg/number_publisher.cpp）："
run "cp $REPO/my_cpp_pkg/src/number_publisher.cpp $WS/src/my_cpp_pkg/src/ && grep -nE 'declare_parameter|get_parameter' $WS/src/my_cpp_pkg/src/number_publisher.cpp"
run "build my_cpp_pkg"
bg "ros2 run my_cpp_pkg number_publisher --ros-args -p number:=11" /tmp/ch08_cpppub.log
sleep 3
run "echo_number"
stopall
next

title "(3/5) 執行中修改參數：ros2 param set"
bg "ros2 run my_py_pkg number_publisher" /tmp/ch08_pub3.log
sleep 3
run "echo_number"
run "ros2 param set /number_publisher number 9"
sleep 1.5
run "echo_number"
note "馬上變 9 —— 因為程式用 add_post_set_parameters_callback 監聽參數變更："
run "sed -n '/def parameters_callback/,/self.number_ = param.value/p' $WS/src/my_py_pkg/my_py_pkg/number_publisher.py"
note "但 callback 只處理 number，所以執行中改 publish_period 不會生效（要重啟節點）"
stopall
next

title "(4/5) 用 YAML 檔管理參數"
run "mkdir -p $YAML_DIR && cp $REPO/YAML_files/*.yaml $YAML_DIR/ && ls $YAML_DIR"
run "sed -n '1,14p' $YAML_DIR/number_params.yaml"
note "格式：/節點名稱 → ros__parameters → 參數。一個檔可以設定好幾個節點。"
bg "ros2 run my_py_pkg number_publisher --ros-args --params-file $YAML_DIR/number_params.yaml" /tmp/ch08_y1.log
sleep 3
run "echo_number"
stopall
note "同一支程式開兩份，用 -r __node:= 改名，就會各自套用 YAML 裡 num_pub1 / num_pub2 的值："
bg "ros2 run my_py_pkg number_publisher --ros-args -r __node:=num_pub1 -r number:=n1 --params-file $YAML_DIR/number_params.yaml" /tmp/ch08_y2.log
bg "ros2 run my_py_pkg number_publisher --ros-args -r __node:=num_pub2 -r number:=n2 --params-file $YAML_DIR/number_params.yaml" /tmp/ch08_y3.log
sleep 3
run "echo \"num_pub1 → \$(echo_number /n1)\"; echo \"num_pub2 → \$(echo_number /n2)\""
note "把目前的參數匯出成 YAML（方便存檔、重複使用）："
run "ros2 param dump /num_pub1 | grep -vE 'qos|use_sim|start_type'"
stopall
next

title "(5/5) 小烏龜參數化：顏色與速度由 YAML 決定"
run "cp $REPO/turtle_controller/turtle_controller/turtle_controller.py $WS/src/turtle_controller/turtle_controller/"
run "grep -n declare_parameter $WS/src/turtle_controller/turtle_controller/turtle_controller.py"
run "cat $YAML_DIR/turtle_params.yaml"
note "預設是紅／綠、速度 1.0；YAML 改成黑／白、速度 1.5"
run "build turtle_controller"
note "小烏龜視窗直接開在螢幕 3："
bg "ros2 run turtlesim turtlesim_node $TURTLE_GEOM" /tmp/ch08_turtle.log
sleep 4
bg "ros2 run turtle_controller turtle_controller --ros-args --params-file $YAML_DIR/turtle_params.yaml" /tmp/ch08_ctrl.log
sleep 8
run "ros2 param get /turtle_controller turtle_velocity; ros2 param get /turtle_controller color_1"
run "grep 'Set color' /tmp/ch08_ctrl.log | tail -2"
note "看螢幕 3：軌跡變成黑白兩色，而且比上一章轉得快。"
next
stopall

title "完成 ✅"
note "第 8 章重點：declare_parameter 宣告｜-p 啟動給值｜param set 執行中改（要有 callback）｜--params-file 用 YAML｜param dump 匯出"
note "YAML 檔放在 ~/ros2_ws/yaml；下一步第 9 章：Launch 檔 —— 一個指令帶起整個系統。"
exec bash

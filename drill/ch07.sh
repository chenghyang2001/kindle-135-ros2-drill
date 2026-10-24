#!/bin/bash
# 《ROS 2 from Scratch》第 7 章：Action —— 目標／回報／結果、server 與 client、取消（快速 demo 模式）
source /opt/ros/jazzy/setup.bash
REPO=~/ROS-2-from-Scratch/ch7
WS=${WS:-$HOME/ros2_ws}
C='\033[1;36m'; Y='\033[1;33m'; G='\033[1;32m'; N='\033[0m'
title() { clear; echo -e "${C}════════════════════════════════════════════${N}"; echo -e "${C} 第 7 章演練 $1${N}"; echo -e "${C}════════════════════════════════════════════${N}\n"; }
run()   { echo -e "${G}\$ $*${N}"; eval "$@"; echo; }
note()  { echo -e "${Y}💡 $*${N}"; }
next()  { echo; read -rp "👉 按 Enter 繼續…" _; }
bg()    { echo -e "${G}\$ $1 &${N}"; eval "$1" > "$2" 2>&1 & }
stopall() { pkill -f "[c]ount_until_" 2>/dev/null; sleep 1; }
build() { cd $WS && colcon build --packages-select "$@" 2>&1 | grep -E "Finished|Failed|Summary|rror"; source $WS/install/setup.bash; }
trap stopall EXIT
source $WS/install/setup.bash 2>/dev/null

title "(1/5) 定義 Action 格式：.action"
note ".action 用兩條 --- 分成三段：Goal 目標｜Result 結果｜Feedback 過程回報"
run "cp -r $REPO/my_robot_interfaces/action $WS/src/my_robot_interfaces/ && cp $REPO/my_robot_interfaces/CMakeLists.txt $WS/src/my_robot_interfaces/"
run "cat $WS/src/my_robot_interfaces/action/CountUntil.action; echo"
note "意思：「數到 target_number，每數一次停 delay 秒；過程中回報目前數到幾；最後回傳數到幾」"
run "build my_robot_interfaces"
next

title "(2/5) Python action server：count_until_server"
run "cp $REPO/my_py_pkg/my_py_pkg/count_until_*.py $WS/src/my_py_pkg/my_py_pkg/ && cp $REPO/my_py_pkg/setup.py $WS/src/my_py_pkg/"
note "server 有三個 callback：goal_callback 決定收不收｜cancel_callback 決定准不准取消｜execute_callback 真的去做"
run "sed -n '/def goal_callback/,/return GoalResponse.ACCEPT/p' $WS/src/my_py_pkg/my_py_pkg/count_until_server.py | grep -v '^\s*#'"
run "sed -n '/for i in range/,/time.sleep/p' $WS/src/my_py_pkg/my_py_pkg/count_until_server.py"
run "build my_py_pkg"
bg "ros2 run my_py_pkg count_until_server" /tmp/ch07_srv.log
sleep 3
note "用命令列送目標：數到 5、每次 0.5 秒，並顯示過程回報"
run "ros2 action send_goal /count_until my_robot_interfaces/action/CountUntil \"{target_number: 5, delay: 0.5}\" --feedback | grep -E 'accepted|current_number|reached_number|status'"
note "送一個不合法的目標（-1），server 會拒絕："
run "ros2 action send_goal /count_until my_robot_interfaces/action/CountUntil \"{target_number: -1, delay: 0.5}\" | grep -iE 'reject|accepted'"
run "grep -E 'Rejecting|Accepting' /tmp/ch07_srv.log | tail -2"
next

title "(3/5) Python action client：count_until_client"
run "sed -n '/def send_goal/,/add_done_callback(self.goal_response_callback)/p' $WS/src/my_py_pkg/my_py_pkg/count_until_client.py | grep -v '^\s*#'"
note "流程：等 server → send_goal_async（掛 feedback callback）→ 收到「接受」後再 get_result_async 等結果"
run "timeout 6 ros2 run my_py_pkg count_until_client 2>&1 | grep -E 'INFO|WARN'"
next

title "(4/5) 中途取消 ＋ Action 的內部構造"
note "送出「數到 10」，2 秒後按 Ctrl+C（這裡用 timeout 模擬），client 會送出取消請求："
run "timeout -s INT 2.2 ros2 action send_goal /count_until my_robot_interfaces/action/CountUntil \"{target_number: 10, delay: 0.5}\" --feedback 2>/dev/null | grep -E 'current_number|cancel' ; sleep 1"
run "grep -E 'cancel|Cancel' /tmp/ch07_srv.log | tail -2"
note "Action 其實是 3 個 service ＋ 2 個 topic 組成的（平常被隱藏）："
run "ros2 service list --include-hidden-services | grep count_until"
run "ros2 topic list --include-hidden-topics | grep count_until"
run "ros2 action info /count_until"
stopall
next

title "(5/5) C++ 版 action server ＋ client"
run "cp $REPO/my_cpp_pkg/src/count_until_*.cpp $WS/src/my_cpp_pkg/src/ && cp $REPO/my_cpp_pkg/CMakeLists.txt $REPO/my_cpp_pkg/package.xml $WS/src/my_cpp_pkg/"
run "grep -nE 'create_server|create_client|async_send_goal|publish_feedback|succeed' $WS/src/my_cpp_pkg/src/count_until_server.cpp $WS/src/my_cpp_pkg/src/count_until_client.cpp | sed \"s|$WS/src/my_cpp_pkg/src/||\""
note "C++ 編譯稍久（這台約 10～20 秒）："
run "build my_cpp_pkg"
bg "ros2 run my_cpp_pkg count_until_server" /tmp/ch07_cppsrv.log
sleep 3
run "timeout 8 ros2 run my_cpp_pkg count_until_client 2>&1 | grep -E 'INFO|WARN' | grep -v signal_handler"
stopall
next

title "完成 ✅"
note "第 7 章重點：.action 三段（Goal/Result/Feedback）｜server 三個 callback｜client 非同步送目標＋收回報｜可拒絕、可取消｜底層是 3 service＋2 topic"
note "下一步第 8 章：Parameter —— 讓節點的設定值可以從外部調整。"
exec bash

#!/bin/bash
# 《ROS 2 from Scratch》第 4 章：建立工作區與套件，寫第一個 Python／C++ 節點（快速 demo 模式）
source /opt/ros/jazzy/setup.bash
REPO=~/ROS-2-from-Scratch/ch4
WS=${WS:-$HOME/ros2_ws}
C='\033[1;36m'; Y='\033[1;33m'; G='\033[1;32m'; N='\033[0m'
title() { clear; echo -e "${C}════════════════════════════════════════════${N}"; echo -e "${C} 第 4 章演練 $1${N}"; echo -e "${C}════════════════════════════════════════════${N}\n"; }
run()   { echo -e "${G}\$ $*${N}"; eval "$@"; echo; }
note()  { echo -e "${Y}💡 $*${N}"; }
next()  { echo; read -rp "👉 按 Enter 繼續…" _; }
cleanup() { pkill -f "[t]est_node" 2>/dev/null; }
trap cleanup EXIT

title "(1/6) 建立工作區 ros2_ws"
note "工作區＝放自己寫的套件的資料夾，固定結構：src/ 放原始碼，colcon 編譯後產生 build/ install/ log/"
run "mkdir -p $WS/src && cd $WS && pwd"
run "colcon build 2>&1 | tail -2"
run "ls $WS"
note "編譯完要 source 工作區的 setup.bash，ROS 2 才找得到你寫的套件："
run "source $WS/install/setup.bash && echo 已載入工作區"
grep -q "ros2_ws/install/setup.bash" ~/.bashrc || echo "source ~/ros2_ws/install/setup.bash" >> ~/.bashrc
note "（已把這行加進 ~/.bashrc，之後開新終端機會自動載入）"
next

title "(2/6) 建立 Python 套件 my_py_pkg"
cd $WS/src
if [ ! -d my_py_pkg ]; then
  run "ros2 pkg create my_py_pkg --build-type ament_python --dependencies rclpy > /dev/null && echo 已建立 my_py_pkg"
else note "my_py_pkg 已存在，略過建立"; fi
run "find my_py_pkg -not -path '*/test*' | sort"
note "重點檔案：package.xml（套件資訊與相依）、setup.py（執行檔進入點）、my_py_pkg/（放 Python 程式）"
next

title "(3/6) 寫第一個 Python 節點"
note "程式碼取自書本 repo：ch4/my_py_pkg/my_py_pkg/my_first_node.py"
run "cp $REPO/my_py_pkg/my_py_pkg/my_first_node.py my_py_pkg/my_py_pkg/ && chmod +x my_py_pkg/my_py_pkg/my_first_node.py"
run "cat my_py_pkg/my_py_pkg/my_first_node.py"
note "結構：繼承 Node → 建一個 1 秒觸發的 timer → 每次印 Hello N；main() 負責 init → spin → shutdown"
note "再到 setup.py 登記執行檔名稱 test_node（直接用書本 repo 的 setup.py）："
run "cp $REPO/my_py_pkg/setup.py my_py_pkg/setup.py && sed -n '/console_scripts/,/]/p' my_py_pkg/setup.py"
next

title "(4/6) 編譯並執行 Python 節點"
cd $WS
run "colcon build --packages-select my_py_pkg 2>&1 | tail -3"
source $WS/install/setup.bash
note "執行 4 秒看看："
run "timeout 4 ros2 run my_py_pkg test_node 2>&1 | grep INFO"
note "（書本範例在 Jazzy 被 Ctrl+C 中斷時會印 ExternalShutdownException，這是無害的結束訊息，已隱藏）"
next

title "(5/6) C++ 套件與節點"
cd $WS/src
if [ ! -d my_cpp_pkg ]; then
  run "ros2 pkg create my_cpp_pkg --build-type ament_cmake --dependencies rclcpp > /dev/null && echo 已建立 my_cpp_pkg"
else note "my_cpp_pkg 已存在，略過建立"; fi
note "放入書本的 C++ 節點，並用書本的 CMakeLists.txt（多了 add_executable 和 install 兩段）："
run "cp $REPO/my_cpp_pkg/src/my_first_node.cpp my_cpp_pkg/src/ && cp $REPO/my_cpp_pkg/CMakeLists.txt my_cpp_pkg/"
run "sed -n '/class/,/^};/p' my_cpp_pkg/src/my_first_node.cpp"
run "grep -A4 -E 'add_executable|install\(' my_cpp_pkg/CMakeLists.txt | grep -v '^--'"
note "C++ 要真的編譯成執行檔（Python 不用），這台大約 5～10 秒："
cd $WS
run "colcon build --packages-select my_cpp_pkg 2>&1 | tail -3"
source $WS/install/setup.bash
run "timeout 4 ros2 run my_cpp_pkg test_node 2>&1 | grep INFO | grep -v signal_handler"
next

title "(6/6) 同時跑兩個節點＋執行時改名"
note "兩個套件的執行檔都叫 test_node，節點名稱也都是 my_node_name —— 名稱重複會出問題。"
note "解法：啟動時用 --ros-args -r __node:=新名字 改名，不用改程式："
ros2 run my_py_pkg  test_node --ros-args -r __node:=py_hello  > /tmp/ch04_py.log 2>&1 &
ros2 run my_cpp_pkg test_node --ros-args -r __node:=cpp_hello > /tmp/ch04_cpp.log 2>&1 &
echo -e "${G}\$ ros2 run my_py_pkg  test_node --ros-args -r __node:=py_hello &${N}"
echo -e "${G}\$ ros2 run my_cpp_pkg test_node --ros-args -r __node:=cpp_hello &${N}"
sleep 4
run "ros2 node list"
run "tail -2 /tmp/ch04_py.log; tail -2 /tmp/ch04_cpp.log"
cleanup
note "小技巧：Python 套件加 --symlink-install 編譯，之後改 .py 不用重新編譯："
run "colcon build --packages-select my_py_pkg --symlink-install 2>&1 | tail -1"
next

title "完成 ✅"
note "第 4 章重點：工作區 ros2_ws｜ros2 pkg create 建套件｜Node 類別＋timer＋spin｜setup.py / CMakeLists 登記執行檔｜colcon build｜__node:= 改名"
note "你的程式在 ~/ros2_ws/src；下一步第 5 章：Topic —— 自己寫 publisher 和 subscriber。"
exec bash

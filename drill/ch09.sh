#!/bin/bash
# 《ROS 2 from Scratch》第 9 章：Launch 檔 —— 一個指令帶起多個節點（快速 demo 模式）
source /opt/ros/jazzy/setup.bash
source ~/ros2-demo/gui-env.sh
REPO=~/ROS-2-from-Scratch/ch9
WS=${WS:-$HOME/ros2_ws}
PKG=$WS/src/my_robot_bringup
C='\033[1;36m'; Y='\033[1;33m'; G='\033[1;32m'; N='\033[0m'
title() { clear; echo -e "${C}════════════════════════════════════════════${N}"; echo -e "${C} 第 9 章演練 $1${N}"; echo -e "${C}════════════════════════════════════════════${N}\n"; }
run()   { echo -e "${G}\$ $*${N}"; eval "$@"; echo; }
note()  { echo -e "${Y}💡 $*${N}"; }
next()  { echo; read -rp "👉 按 Enter 繼續…" _; }
bg()    { echo -e "${G}\$ $1 &${N}"; eval "$1" > "$2" 2>&1 & }
stopall() { pkill -INT -f "[r]os2 launch my_robot_bringup" 2>/dev/null; sleep 2; pkill -f "[n]umber_publisher|[n]umber_counter|[t]urtle_controller|[t]urtlesim_node" 2>/dev/null; sleep 1; }
build() { cd $WS && colcon build --packages-select "$@" 2>&1 | grep -E "Finished|Failed|Summary|rror"; source $WS/install/setup.bash; }
trap stopall EXIT
source $WS/install/setup.bash 2>/dev/null

title "(1/5) 建立 bringup 套件"
note "慣例：另開一個 xxx_bringup 套件，專門放 launch 檔和設定檔，不放程式碼"
run "rm -rf $PKG && cp -r $REPO/my_robot_bringup $WS/src/ && find $PKG -type f | sed \"s|$WS/src/||\" | sort"
run "grep -A4 'install(DIRECTORY' $PKG/CMakeLists.txt"
note "CMakeLists 只做一件事：把 launch/ 和 config/ 安裝到 share 目錄，ros2 launch 才找得到"
run "grep exec_depend $PKG/package.xml"
next

title "(2/5) number_app.launch.py：一次啟動 3 個節點"
run "sed -n '/number_publisher1 = Node/,/^    )/p' $PKG/launch/number_app.launch.py"
note "namespace=/abc（加前綴避免撞名）｜name 改節點名｜remappings 改 topic 名｜parameters 可直接寫值或指定 YAML"
run "build my_robot_bringup"
bg "ros2 launch my_robot_bringup number_app.launch.py" /tmp/ch09_num.log
sleep 6
run "ros2 node list | grep abc"
run "ros2 topic list | grep number"
run "ros2 param get /abc/num_pub1 number; ros2 param get /abc/num_pub2 number"
note "num_pub1 用 launch 檔直接給的 3；num_pub2 用 YAML 裡 /abc/num_pub2 的 4 → 計數器每次加 3 或 4："
run "grep -i counter /tmp/ch09_num.log | tail -4"
stopall
next

title "(3/5) 同樣內容的 XML 寫法"
run "cat $PKG/launch/number_app.launch.xml"
note "XML 比較短、好讀；Python 比較彈性（可以寫判斷式、迴圈）。兩種效果一樣："
bg "ros2 launch my_robot_bringup number_app.launch.xml" /tmp/ch09_numxml.log
sleep 6
run "ros2 node list | grep abc"
stopall
next

title "(4/5) turtlesim_control：兩組小烏龜同時跑"
note "兩個 turtlesim ＋ 兩個 controller，用 namespace /t1、/t2 分開，各自讀 YAML 裡自己的參數"
run "grep -A4 '^/t1/turtlesim\|^/t2/turtlesim\|^/t1/turtle_controller\|^/t2/turtle_controller' $PKG/config/turtle_params.yaml | grep -v '^--'"
note "【本演練加的】書本原檔沒指定視窗位置；為了讓兩個視窗直接開在螢幕 3，在 turtlesim 節點加了 arguments 指定座標："
python3 - "$PKG/launch/turtlesim_control.launch.py" <<'P'
import sys, re
p = sys.argv[1]; s = open(p, encoding="utf-8").read()
if "qwindowgeometry" not in s:
    s = s.replace('namespace="/t1",\n        parameters=[turtle_params]\n    )',
                  'namespace="/t1",\n        parameters=[turtle_params],\n        arguments=["-qwindowgeometry", "500x500+40+80"]  # 本演練加：開在螢幕 3 左側\n    )', 1)
    s = s.replace('namespace="/t2",\n        parameters= [turtle_params]\n    )',
                  'namespace="/t2",\n        parameters= [turtle_params],\n        arguments=["-qwindowgeometry", "500x500+680+80"]  # 本演練加：開在螢幕 3 右側\n    )', 1)
    open(p, "w", encoding="utf-8").write(s)
print("已加入視窗座標" if s.count("qwindowgeometry") == 2 else "⚠️ 加入失敗")
P
run "grep -n qwindowgeometry $PKG/launch/turtlesim_control.launch.py"
run "build my_robot_bringup"
note "一個指令啟動 4 個節點，兩個小烏龜視窗出現在螢幕 3（左紅底、右綠底）："
bg "ros2 launch my_robot_bringup turtlesim_control.launch.py" /tmp/ch09_turtle.log
sleep 8
run "ros2 node list | grep -E 't1|t2'"
run "ros2 param get /t1/turtle_controller turtle_velocity; ros2 param get /t2/turtle_controller turtle_velocity"
note "看螢幕 3：左邊 t1 速度 1.5、黑白筆；右邊 t2 速度 0.5、白黑筆。"
next
stopall

title "(5/5) 完成 ✅"
note "第 9 章重點：bringup 套件放 launch＋config｜Node(package, executable, namespace, name, remappings, parameters)｜Python 與 XML 兩種寫法｜namespace 讓同一程式開多份"
note "書的第一部分（基礎）到這裡結束；第 10 章起進入 TF、URDF、Gazebo（機器人模型與模擬）。"
exec bash

#!/bin/bash
# 《ROS 2 from Scratch》第 12 章：my_robot_description 套件＋display launch 檔（快速 demo 模式）
source /opt/ros/jazzy/setup.bash
source ~/ros2-demo/gui-env.sh
REPO=~/ROS-2-from-Scratch/ch12
WS=${WS:-$HOME/ros2_ws}
PKG=$WS/src/my_robot_description
C='\033[1;36m'; Y='\033[1;33m'; G='\033[1;32m'; N='\033[0m'
title() { clear; echo -e "${C}════════════════════════════════════════════${N}"; echo -e "${C} 第 12 章演練 $1${N}"; echo -e "${C}════════════════════════════════════════════${N}\n"; }
run()   { echo -e "${G}\$ $*${N}"; eval "$@"; echo; }
note()  { echo -e "${Y}💡 $*${N}"; }
next()  { echo; read -rp "👉 按 Enter 繼續…" _; }
bg()    { echo -e "${G}\$ $1 &${N}"; eval "$1" > "$2" 2>&1 & }
stopall() { pkill -INT -f "[r]os2 launch my_robot_description" 2>/dev/null; sleep 2; pkill -f "[r]obot_state_publisher|[r]viz2" 2>/dev/null; pkill -9 -f "[j]sp_gui_m3|[j]oint_state_publisher" 2>/dev/null; sleep 1; }
build() { cd $WS && colcon build --packages-select "$@" 2>&1 | grep -E "Finished|Failed|Summary|rror"; source $WS/install/setup.bash; }
trap stopall EXIT
source $WS/install/setup.bash 2>/dev/null

title "(1/5) 建立 my_robot_description 套件"
note "慣例：機器人模型放在 xxx_description 套件，裡面只有 urdf/ rviz/ launch/，沒有程式碼"
cd $WS/src
if [ ! -d my_robot_description ]; then
  run "ros2 pkg create my_robot_description --build-type ament_cmake > /dev/null && rm -rf my_robot_description/src my_robot_description/include && echo 已建立並移除 src/ include/"
fi
run "cp -r $REPO/my_robot_description/{urdf,rviz,launch,CMakeLists.txt,package.xml} $PKG/ && find $PKG -type f | sed \"s|$WS/src/||\" | sort"
run "grep -A3 'install(' $PKG/CMakeLists.txt"
note "Xacro 的 include 改用 \$(find 套件名) 找路徑，裝到哪裡都找得到："
run "grep include $PKG/urdf/my_robot.urdf.xacro"
next

title "(2/5) display.launch.py：一次啟動 3 個節點"
run "sed -n '/urdf_path = /,/^    )$/p' $PKG/launch/display.launch.py | head -12"
note "Command(['xacro ', 路徑]) 在啟動時展開 Xacro → 當作 robot_description 參數交給 robot_state_publisher"
run "grep -nE 'package=|executable=|arguments=' $PKG/launch/display.launch.py"
note "三個節點：robot_state_publisher（模型→TF）＋ joint_state_publisher_gui（滑桿）＋ rviz2（顯示）"
next

title "(3/5) 【本演練加的】讓視窗開在螢幕 3"
note "書本原檔的 RViz 設定記住的位置是 X=2197（＝螢幕 1），滑桿也沒指定位置。在工作區這份複製檔做兩處修改："
python3 - "$PKG" <<'P'
import sys, re, os
pkg = sys.argv[1]
rv = os.path.join(pkg, "rviz", "urdf_config.rviz")
s = open(rv, encoding="utf-8").read()
s = re.sub(r"\n  Height: \d+\n", "\n  Height: 600\n", s)
s = re.sub(r"\n  Width: \d+\n", "\n  Width: 880\n", s)
s = re.sub(r"\n  X: \d+\n", "\n  X: 40\n", s)
s = re.sub(r"\n  Y: \d+", "\n  Y: 20", s)
open(rv, "w", encoding="utf-8").write(s)
lp = os.path.join(pkg, "launch", "display.launch.py")
s = open(lp, encoding="utf-8").read()
if "jsp_gui_m3" not in s:
    s = s.replace("from launch_ros.actions import Node", "from launch_ros.actions import Node\nfrom launch.actions import ExecuteProcess  # 本演練加")
    s = re.sub(r"joint_state_publisher_gui_node = Node\(\n\s+package=\"joint_state_publisher_gui\",\n\s+executable=\"joint_state_publisher_gui\"\n\s+\)",
               "# 本演練加：改用包裝程式，讓滑桿視窗開在螢幕 3\n    joint_state_publisher_gui_node = ExecuteProcess(\n        cmd=['python3', os.path.expanduser('~/ros2-demo/jsp_gui_m3.py')], output='screen'\n    )", s)
    s = s.replace("arguments=['-d', rviz_config_path]", "arguments=['-d', rviz_config_path, '-qwindowgeometry', '880x600+40+20']  # 本演練加：指定位置")
    open(lp, "w", encoding="utf-8").write(s)
print("RViz 設定與 launch 檔已修改")
P
run "grep -nE '^  (Height|Width|X|Y):' $PKG/rviz/urdf_config.rviz"
run "grep -n '本演練加' $PKG/launch/display.launch.py"
next

title "(4/5) 編譯並啟動：ros2 launch my_robot_description display.launch.py"
run "build my_robot_description"
note "RViz（左）和滑桿（右）會開在螢幕 3。Fixed Frame 是 base_footprint（貼地座標）"
bg "ros2 launch my_robot_description display.launch.py" /tmp/ch12_launch.log
sleep 10
run "ros2 node list"
run "ros2 param get /robot_state_publisher robot_description | grep -c '<link' | xargs echo 'robot_description 裡的 link 數：'"
note "👉 去螢幕 3 拖動兩個輪子的滑桿看看。"
note "XML 版（display.launch.xml）內容相同，這裡只顯示不執行（它的滑桿無法指定位置）："
run "grep -vE '^\s*$' $PKG/launch/display.launch.xml"
next
stopall

title "(5/5) 完成 ✅"
note "第 12 章重點：xxx_description 套件放 urdf/rviz/launch｜CMake install 這三個目錄｜\$(find pkg) 路徑｜Command(xacro) 產生 robot_description｜一個 launch 帶起 RSP＋滑桿＋RViz"
note "下一步第 13 章：加上 Gazebo 物理屬性，在模擬器裡讓機器人真的動起來（最後一章）。"
exec bash

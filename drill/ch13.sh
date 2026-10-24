#!/bin/bash
# 《ROS 2 from Scratch》第 13 章：Gazebo 模擬 —— 物理屬性、差速驅動外掛、ROS↔Gazebo 橋接、遙控開車（快速 demo 模式）
source /opt/ros/jazzy/setup.bash
source ~/ros2-demo/gui-env.sh
REPO=~/ROS-2-from-Scratch/ch13
WS=${WS:-$HOME/ros2_ws}
DESC=$WS/src/my_robot_description
BRING=$WS/src/my_robot_bringup
C='\033[1;36m'; Y='\033[1;33m'; G='\033[1;32m'; N='\033[0m'
title() { clear; echo -e "${C}════════════════════════════════════════════${N}"; echo -e "${C} 第 13 章演練 $1${N}"; echo -e "${C}════════════════════════════════════════════${N}\n"; }
run()   { echo -e "${G}\$ $*${N}"; eval "$@"; echo; }
note()  { echo -e "${Y}💡 $*${N}"; }
next()  { echo; read -rp "👉 按 Enter 繼續…" _; }
bg()    { echo -e "${G}\$ $1 &${N}"; eval "$1" > "$2" 2>&1 & }
stopall() { pkill -INT -f "[r]os2 launch my_robot_bringup" 2>/dev/null; sleep 2; pkill -f "[r]obot_state_publisher|[r]viz2|[p]arameter_bridge|[g]z sim|[g]z-sim|[r]os_gz_sim" 2>/dev/null; sleep 1; pkill -9 -f "[g]z sim|[r]uby.*gz" 2>/dev/null; }
build() { cd $WS && colcon build --packages-select "$@" 2>&1 | grep -E "Finished|Failed|Summary|rror"; source $WS/install/setup.bash; }
trap stopall EXIT
source $WS/install/setup.bash 2>/dev/null

title "(1/6) 模型加上物理屬性"
run "cp $REPO/my_robot_description/urdf/*.xacro $DESC/urdf/ && ls $DESC/urdf"
note "Gazebo 要算物理，每個 link 除了 visual（長相）還要："
note "  collision 碰撞形狀（輪子用球形，滾動較穩）｜inertia 質量與慣性（用巨集依形狀自動算）"
run "sed -n '/<link name=\"base_link\">/,/<\/link>/p' $DESC/urdf/mobile_base.xacro | sed -n '/<collision>/,\$p'"
run "grep -A2 'macro name=\"box_inertia\"' $DESC/urdf/common_properties.xacro"
next

title "(2/6) Gazebo 外掛：差速驅動＋關節狀態"
run "grep -vE '^\s*\$' $DESC/urdf/mobile_base_gazebo.xacro | sed -n '/DiffDrive/,/<\/plugin>/p'"
note "DiffDrive：收到速度指令就轉左右輪，並算出里程計（odom → base_footprint 的 TF）"
note "JointStatePublisher：回報輪子轉到幾度；caster 球輪摩擦係數 mu 調低讓它好滑"
run "grep include $DESC/urdf/my_robot.urdf.xacro"
next

title "(3/6) ROS 2 ↔ Gazebo 橋接設定"
run "cp $REPO/my_robot_bringup/launch/my_robot.launch.xml $BRING/launch/ && mkdir -p $BRING/config && cp $REPO/my_robot_bringup/config/gazebo_bridge.yaml $BRING/config/ && cp $REPO/my_robot_bringup/CMakeLists.txt $REPO/my_robot_bringup/package.xml $BRING/"
run "cat $BRING/config/gazebo_bridge.yaml"
note "三條橋：/cmd_vel（ROS→Gazebo，開車指令）｜/joint_states、/tf（Gazebo→ROS，輪子角度與位置）"
run "grep -vE '^\s*\$' $BRING/launch/my_robot.launch.xml | grep -E 'node|include|arg'"
note "啟動順序：robot_state_publisher → 開 Gazebo（empty.sdf）→ create 把機器人放進世界 → bridge → RViz"
next

title "(4/6) 【本演練調整】Gazebo 不開畫面、RViz 開在螢幕 3"
note "① Gazebo 視窗無法保證開在哪個螢幕（實測位置設定無效），改用 -s 只跑物理模擬，不開畫面"
note "② RViz 書本設定記住 X=2197（＝螢幕 1），改成螢幕 3；Fixed Frame 改 odom 才看得到車子移動"
python3 - "$BRING/launch/my_robot.launch.xml" "$DESC/rviz/urdf_config.rviz" <<'P'
import sys, re
lp, rv = sys.argv[1], sys.argv[2]
s = open(lp, encoding="utf-8").read()
s = s.replace('value="empty.sdf -r"', 'value="empty.sdf -r -s"')  # 本演練調整：只跑模擬
s = s.replace('args="-d $(var rviz_config_path)"', 'args="-d $(var rviz_config_path) -qwindowgeometry 880x600+40+20"')
open(lp, "w", encoding="utf-8").write(s)
r = open(rv, encoding="utf-8").read()
r = re.sub(r"\n  Height: \d+\n", "\n  Height: 600\n", r); r = re.sub(r"\n  Width: \d+\n", "\n  Width: 880\n", r)
r = re.sub(r"\n  X: \d+\n", "\n  X: 40\n", r); r = re.sub(r"\n  Y: \d+", "\n  Y: 20", r)
r = r.replace("Fixed Frame: base_footprint", "Fixed Frame: odom")
open(rv, "w", encoding="utf-8").write(r)
print("已調整 launch 與 RViz 設定")
P
run "grep -nE 'gz_args|rviz2' $BRING/launch/my_robot.launch.xml"
run "grep -nE 'Fixed Frame|^  (Width|Height|X|Y):' $DESC/rviz/urdf_config.rviz"
next

title "(5/6) 啟動模擬並開車"
run "build my_robot_description my_robot_bringup"
note "RViz 開在螢幕 3。Gazebo 在背景跑物理（約 10 秒後機器人就位）："
bg "ros2 launch my_robot_bringup my_robot.launch.xml" /tmp/ch13_launch.log
sleep 14
run "ros2 node list"
run "ros2 topic list | grep -E 'cmd_vel|joint_states|^/tf'"
run "timeout 4 ros2 run tf2_ros tf2_echo odom base_footprint 2>/dev/null | grep -m1 -A1 Translation"
note "自動開一段：前進 0.5 m/s ＋ 左轉，持續 6 秒（看螢幕 3 的 RViz，車子會畫弧線移動）"
run "timeout 6 ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist \"{linear: {x: 0.5}, angular: {z: 0.5}}\" > /dev/null; sleep 1"
run "timeout 4 ros2 run tf2_ros tf2_echo odom base_footprint 2>/dev/null | grep -m1 -A1 Translation"
note "位置變了 —— 這是 Gazebo 物理引擎算出來的，經過橋接傳回 ROS 2"
next

title "(6/6) 換你開：鍵盤遙控"
if [ -n "$DEMO_RECORD" ]; then
  # 錄影時沒人在鍵盤前，teleop 會卡住等按鍵；改用 topic pub 模擬同樣的 cmd_vel
  note "（錄影模式：自動模擬鍵盤遙控，依序 前進→左轉→前進→右轉→停止）"
  note "按鍵：i 前進｜, 後退｜j 左轉｜l 右轉｜k 停止｜q/z 加速/減速"
  TW=geometry_msgs/msg/Twist
  echo -e "${Y}⌨️  按 i 前進（3 秒）${N}"
  run "timeout 3 ros2 topic pub -r 10 /cmd_vel $TW \"{linear: {x: 0.5}}\" > /dev/null"
  echo -e "${Y}⌨️  按 j 原地左轉（3 秒）${N}"
  run "timeout 3 ros2 topic pub -r 10 /cmd_vel $TW \"{angular: {z: 1.0}}\" > /dev/null"
  echo -e "${Y}⌨️  按 i 前進（3 秒）${N}"
  run "timeout 3 ros2 topic pub -r 10 /cmd_vel $TW \"{linear: {x: 0.5}}\" > /dev/null"
  echo -e "${Y}⌨️  按 l 原地右轉（3 秒）${N}"
  run "timeout 3 ros2 topic pub -r 10 /cmd_vel $TW \"{angular: {z: -1.0}}\" > /dev/null"
  echo -e "${Y}⌨️  按 k 停止${N}"
  run "ros2 topic pub --once /cmd_vel $TW \"{linear: {x: 0.0}, angular: {z: 0.0}}\" > /dev/null"
  note "開完一圈，看看車子現在的位置："
  run "timeout 4 ros2 run tf2_ros tf2_echo odom base_footprint 2>/dev/null | grep -m1 -A1 Translation"
elif [ -n "$DEMO_AUTO" ]; then
  note "（自動測試模式，略過鍵盤遙控）"
else
  note "按鍵：i 前進｜, 後退｜j 左轉｜l 右轉｜k 停止｜q/z 加速/減速"
  note "這個視窗要保持在最上層才收得到按鍵；開完按 Ctrl+C 回到導覽"
  echo -e "${G}\$ ros2 run teleop_twist_keyboard teleop_twist_keyboard${N}"
  ros2 run teleop_twist_keyboard teleop_twist_keyboard
fi
stopall
title "完成 ✅ 全書演練結束"
note "第 13 章重點：collision＋inertia｜Gazebo 外掛（DiffDrive、JointStatePublisher）｜ros_gz_bridge 橋接｜create 放入機器人｜cmd_vel 開車、odom 看位置"
note "從第 1 章到第 13 章都跑完了，你的程式都在 ~/ros2_ws。"
exec bash

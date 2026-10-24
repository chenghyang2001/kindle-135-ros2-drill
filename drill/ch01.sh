#!/bin/bash
# 《ROS 2 from Scratch》第 1 章觀念實機導覽（快速 demo 模式）
source /opt/ros/jazzy/setup.bash
C='\033[1;36m'; Y='\033[1;33m'; G='\033[1;32m'; N='\033[0m'
title() { clear; echo -e "${C}════════════════════════════════════════════${N}"; echo -e "${C} 第 1 章演練 $1${N}"; echo -e "${C}════════════════════════════════════════════${N}\n"; }
run()   { echo -e "${G}\$ $*${N}"; eval "$@"; echo; }
note()  { echo -e "${Y}💡 $*${N}"; }
next()  { echo; read -rp "👉 按 Enter 繼續…" _; }
cleanup() { pkill -f "[d]emo_nodes" 2>/dev/null; }
trap cleanup EXIT

title "(1/5) ROS 2 不是作業系統"
note "名字有 Operating System，但 ROS 2 其實是裝在 Ubuntu 上面的一套「機器人開發框架＋工具」。"
run "lsb_release -ds"
run "uname -sr"
note "下面這些環境變數是 source setup.bash 後才出現的，ROS 2 就是一層疊在 Linux 上的軟體："
run "printenv | grep -E '^ROS_' | sort"
next

title "(2/5) 版本（Distribution）：Jazzy"
note "ROS 2 每年 5 月出一版，偶數年是 LTS（長期支援 5 年）。"
note "本書用 Jazzy Jalisco（2024 年 5 月，LTS，支援到 2029 年 5 月），搭配 Ubuntu 24.04。"
run "echo \"目前版本：\$ROS_DISTRO（ROS_VERSION=\$ROS_VERSION）\""
run "ros2 doctor --report 2>/dev/null | grep -E 'distribution|platform name|middleware name' | head -5"
next

title "(3/5) ROS 2 的三大組成"
note "① Plumbing 管線：節點之間怎麼傳訊息（topic / service / action）"
note "② Tools 工具：命令列 ros2、RViz、rqt、Gazebo 模擬器"
note "③ Ecosystem 生態系：大量現成套件，不用從零寫"
run "echo \"本機已安裝的 ROS 2 套件數：\$(ros2 pkg list | wc -l)\""
run "ros2 --help | sed -n '/Commands:/,/^\$/p' | head -25"
run "ls /opt/ros/jazzy/bin | grep -E '^(rviz2|rqt|gz)' ; which gz"
next

title "(4/5) 不需要中央主機，Python 與 C++ 節點直接互通"
note "ROS 1 要先開 roscore（中央主機）；ROS 2 靠 DDS 中介軟體，節點會自己在網路上找到彼此。"
note "現在不開任何主機，直接啟動：C++ 寫的 talker ＋ Python 寫的 listener"
echo -e "${G}\$ ros2 run demo_nodes_cpp talker &   # C++${N}"
ros2 run demo_nodes_cpp talker > /tmp/ch01_talker.log 2>&1 &
sleep 1
echo -e "${G}\$ ros2 run demo_nodes_py listener &  # Python${N}"
ros2 run demo_nodes_py listener > /tmp/ch01_listener.log 2>&1 &
sleep 5
run "ros2 node list"
run "tail -3 /tmp/ch01_listener.log"
note "C++ 發、Python 收，中間沒有任何中央主機 —— 這就是 ROS 2 跨語言、去中心化的設計。"
next

title "(5/5) 為什麼要拆成多個節點？"
note "每個功能放在獨立節點：一個壞掉不會拖垮全部，也能各自重啟、各自用不同語言寫。"
note "現在故意把 listener 關掉："
run "pkill -f '[d]emo_nodes_py' && sleep 2 && ros2 node list"
note "talker 還在繼續發送（看最後幾行）："
run "tail -2 /tmp/ch01_talker.log"
note "重新啟動 listener，馬上又接上："
ros2 run demo_nodes_py listener > /tmp/ch01_listener2.log 2>&1 &
sleep 4
run "tail -2 /tmp/ch01_listener2.log"
next

title "完成 ✅"
note "第 1 章重點：ROS 2 是框架不是 OS｜Jazzy 是 LTS｜管線＋工具＋生態系｜無中央主機、跨語言｜拆節點容錯"
note "下一步：第 3 章（第 2 章安裝已完成），用小烏龜 turtlesim 實際操作節點、topic、service。"
cleanup
exec bash

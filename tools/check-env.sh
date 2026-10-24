#!/bin/bash
# 《ROS 2 from Scratch》演練環境檢查（在 WSL Ubuntu 內執行）
# 刻意不用 set -e：每一項檢查失敗都要記下來繼續跑，最後才一起總結
set -uo pipefail

# 套件清單需與 tools/setup-ros2.sh 保持一致
PACKAGES=(
  ros-jazzy-desktop ros-dev-tools ros-jazzy-ros-gz ros-jazzy-urdf-tutorial
  ros-jazzy-tf2-tools ros-jazzy-joint-state-publisher-gui ros-jazzy-xacro
  ros-jazzy-teleop-twist-keyboard xdotool xvfb x11-utils x11-xserver-utils
  mesa-utils liburdfdom-tools
)

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
用法：bash tools/check-env.sh

逐項檢查 ROS 2 Jazzy 演練環境，輸出 PASS / WARN / FAIL：
  Ubuntu 版本、/opt/ros/jazzy、必要套件、GPU（D3D12）繪圖、/dev/dxg、
  記憶體與磁碟空間、X 桌面與螢幕配置、範例 repo 與 ~/ros2-demo。
有任何 FAIL 時結束碼為 1。
EOF
  exit 0
fi

G='\033[1;32m'; Y='\033[1;33m'; R='\033[1;31m'; C='\033[1;36m'; N='\033[0m'
pass_count=0; warn_count=0; fail_count=0
pass() { echo -e "${G}[PASS]${N} $*"; pass_count=$((pass_count + 1)); }
warn() { echo -e "${Y}[WARN]${N} $*"; warn_count=$((warn_count + 1)); }
fail() { echo -e "${R}[FAIL]${N} $*"; fail_count=$((fail_count + 1)); }
section() { echo -e "\n${C}── $* ──${N}"; }

check_os() {
  section "作業系統"
  local version_id=""
  if [[ -r /etc/os-release ]]; then
    version_id=$(. /etc/os-release && echo "${VERSION_ID:-}")
  fi
  if [[ "$version_id" == "24.04" ]]; then
    pass "Ubuntu 24.04"
  else
    fail "Ubuntu 版本為「${version_id:-未知}」，ROS 2 Jazzy 需要 24.04"
  fi
  if [[ -d /opt/ros/jazzy ]]; then
    pass "/opt/ros/jazzy 存在"
  else
    fail "/opt/ros/jazzy 不存在（ROS 2 Jazzy 未安裝，請跑 tools/setup-ros2.sh）"
  fi
}

check_packages() {
  section "套件"
  local pkg
  for pkg in "${PACKAGES[@]}"; do
    if dpkg -s "$pkg" >/dev/null 2>&1; then
      pass "$pkg"
    else
      fail "$pkg 未安裝（sudo apt install -y $pkg）"
    fi
  done
}

check_gpu() {
  section "GPU 繪圖"
  if [[ -e /dev/dxg ]]; then
    pass "/dev/dxg 存在（WSL GPU 直通可用）"
  else
    warn "/dev/dxg 不存在：WSL 沒有 GPU 直通，RViz／Gazebo 會很慢"
  fi
  if ! command -v glxinfo >/dev/null 2>&1; then
    warn "找不到 glxinfo（需 mesa-utils），無法檢查繪圖器"
    return
  fi
  local renderer
  renderer=$(GALLIUM_DRIVER=d3d12 timeout 10 glxinfo -B 2>/dev/null | grep -i "OpenGL renderer" || true)
  if [[ "$renderer" == *D3D12* ]]; then
    pass "繪圖器：${renderer#*: }"
  else
    warn "繪圖器不是 D3D12（${renderer#*: }）：會用 CPU 繪圖（llvmpipe），3D 視窗會卡"
  fi
}

check_resources() {
  section "記憶體與磁碟"
  local mem_total_mb avail_gb
  mem_total_mb=$(free -m | awk '/^Mem:/ {print $2}')
  free -h | sed -n '1,2p'
  if [[ -n "$mem_total_mb" && "$mem_total_mb" -ge 7000 ]]; then
    pass "記憶體 ${mem_total_mb} MB"
  else
    warn "記憶體 ${mem_total_mb:-未知} MB，低於 8GB，Gazebo 可能吃緊（可調 .wslconfig）"
  fi
  avail_gb=$(df -BG --output=avail / | tail -1 | tr -dc '0-9')
  if [[ -n "$avail_gb" && "$avail_gb" -ge 20 ]]; then
    pass "根目錄剩餘 ${avail_gb} GB"
  else
    warn "根目錄剩餘 ${avail_gb:-未知} GB（< 20GB），安裝 ros-jazzy-desktop 與 Gazebo 可能不夠"
  fi
}

check_display() {
  section "X 桌面與螢幕"
  if [[ -z "${DISPLAY:-}" ]]; then
    warn "DISPLAY 未設定，跳過螢幕檢查（WSLg 通常為 :0）"
    return
  fi
  if command -v xdpyinfo >/dev/null 2>&1; then
    local dims
    dims=$(xdpyinfo 2>/dev/null | awk '/dimensions:/ {print $2}')
    if [[ -n "$dims" ]]; then
      pass "X 桌面大小：$dims"
    else
      warn "xdpyinfo 讀不到桌面大小（X 伺服器沒回應？）"
    fi
  else
    warn "找不到 xdpyinfo（需 x11-utils）"
  fi
  if command -v xrandr >/dev/null 2>&1; then
    echo "各螢幕段（xrandr）："
    xrandr 2>/dev/null | grep -E " connected" | sed 's/^/  /' || warn "xrandr 讀取失敗"
  else
    warn "找不到 xrandr（需 x11-xserver-utils）"
  fi
  echo -e "${Y}💡 演練腳本的座標是依 3|1|2、螢幕3 為 X 0~1280 設計，若不同需調整${N}"
  echo -e "${Y}   drill/gui-env.sh、urdf_m3.rviz、jsp_gui_m3.py、gz_gui_m3.config、ch09/ch12/ch13 內的 -qwindowgeometry${N}"
}

check_dirs() {
  section "範例與演練目錄"
  if [[ -d "$HOME/ROS-2-from-Scratch" ]]; then
    pass "~/ROS-2-from-Scratch 存在"
  else
    fail "~/ROS-2-from-Scratch 不存在（git clone https://github.com/PacktPublishing/ROS-2-from-Scratch.git）"
  fi
  if [[ -d "$HOME/ros2-demo" ]]; then
    pass "~/ros2-demo 存在"
  else
    fail "~/ros2-demo 不存在（跑 tools/setup-ros2.sh 會從 drill/ 複製過去）"
  fi
}

check_os
check_packages
check_gpu
check_resources
check_display
check_dirs

echo -e "\n${C}══ 總結：PASS ${pass_count}｜WARN ${warn_count}｜FAIL ${fail_count} ══${N}"
if [[ "$fail_count" -gt 0 ]]; then
  echo -e "${R}有 ${fail_count} 項 FAIL，請先處理再開始演練${N}"
  exit 1
fi
echo -e "${G}環境可以開始演練 ✅${N}"

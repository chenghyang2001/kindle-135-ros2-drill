#!/bin/bash
# 《ROS 2 from Scratch》演練環境一鍵安裝（WSL Ubuntu 24.04，一般使用者執行，過程需要 sudo）
# 可重複執行：已完成的步驟會略過
set -euo pipefail

# 套件清單需與 tools/check-env.sh 保持一致
PACKAGES=(
  ros-jazzy-desktop ros-dev-tools ros-jazzy-ros-gz ros-jazzy-urdf-tutorial
  ros-jazzy-tf2-tools ros-jazzy-joint-state-publisher-gui ros-jazzy-xacro
  ros-jazzy-teleop-twist-keyboard xdotool xvfb x11-utils x11-xserver-utils
  mesa-utils liburdfdom-tools
)
REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
SAMPLES_DIR="$HOME/ROS-2-from-Scratch"
DEMO_DIR="$HOME/ros2-demo"
DRY_RUN=0

usage() {
  cat <<'EOF'
用法：bash tools/setup-ros2.sh [--dry-run] [--help]

在 WSL Ubuntu 24.04 安裝 ROS 2 Jazzy 演練環境：
  1. 設定 locale（en_US.UTF-8）、啟用 universe
  2. 安裝 ros2-apt-source（ROS 官方 apt 來源）
  3. apt 安裝 ROS 2 Jazzy 與演練用工具
  4. ~/.bashrc 加入 source /opt/ros/jazzy/setup.bash 與 GALLIUM_DRIVER=d3d12
  5. clone 範例 repo 到 ~/ROS-2-from-Scratch
  6. 複製 drill/ 到 ~/ros2-demo/

  --dry-run   只印出要做的事，不實際執行
  --help      顯示本說明
EOF
}

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "錯誤：未知參數 $arg" >&2; usage >&2; exit 1 ;;
  esac
done

C='\033[1;36m'; G='\033[1;32m'; Y='\033[1;33m'; N='\033[0m'
step() { echo -e "\n${C}▶ $*${N}"; }
skip() { echo -e "${Y}  略過：$*${N}"; }
die()  { echo -e "\033[1;31m錯誤：$*\033[0m" >&2; exit 1; }
# 統一執行入口，dry-run 時只印不跑
run() {
  echo -e "${G}  \$ $*${N}"
  if [[ "$DRY_RUN" -eq 0 ]]; then
    "$@"
  fi
}

preflight() {
  [[ "$(id -u)" -ne 0 ]] || die "請用一般使用者執行（不要 sudo bash），腳本內需要時會自己呼叫 sudo"
  [[ -d "$REPO_ROOT/drill" ]] || die "找不到 $REPO_ROOT/drill，請在 repo 內執行本腳本"
  local codename
  codename=$(. /etc/os-release && echo "${VERSION_CODENAME:-}")
  [[ "$codename" == "noble" ]] || echo -e "${Y}⚠️  目前是 ${codename:-未知}，ROS 2 Jazzy 官方只支援 Ubuntu 24.04（noble）${N}"
  if [[ "$DRY_RUN" -eq 0 ]]; then
    sudo -v || die "取得 sudo 權限失敗"
  fi
}

setup_locale_and_universe() {
  step "1/6 設定 locale 與 universe 套件庫"
  run sudo apt-get update || die "apt-get update 失敗（檢查網路）"
  run sudo apt-get install -y locales software-properties-common curl git || die "安裝基本工具失敗"
  run sudo locale-gen en_US en_US.UTF-8 || die "locale-gen 失敗"
  run sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 || die "update-locale 失敗"
  export LANG=en_US.UTF-8
  run sudo add-apt-repository -y universe || die "啟用 universe 失敗"
}

install_ros_apt_source() {
  step "2/6 安裝 ros2-apt-source"
  if dpkg -s ros2-apt-source >/dev/null 2>&1; then
    skip "ros2-apt-source 已安裝"
    return
  fi
  local version codename deb_file deb_url
  version=$(curl -s https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest \
    | grep -F '"tag_name"' | cut -d'"' -f4 || true)
  [[ -n "$version" ]] || die "取不到 ros-apt-source 最新版本（GitHub API 失敗或被限流），請稍後再試"
  codename=$(. /etc/os-release && echo "$VERSION_CODENAME")
  deb_file="/tmp/ros2-apt-source_${version}.${codename}_all.deb"
  deb_url="https://github.com/ros-infrastructure/ros-apt-source/releases/download/${version}/ros2-apt-source_${version}.${codename}_all.deb"
  echo "  版本：$version（$codename）"
  run curl -fL -o "$deb_file" "$deb_url" || die "下載 $deb_url 失敗"
  run sudo dpkg -i "$deb_file" || die "dpkg -i $deb_file 失敗"
}

install_packages() {
  step "3/6 安裝 ROS 2 Jazzy 與演練工具（第一次約需 10～30 分鐘）"
  run sudo apt-get update || die "apt-get update 失敗"
  run sudo apt-get install -y "${PACKAGES[@]}" || die "套件安裝失敗，請看上方 apt 訊息"
}

append_bashrc_line() {
  local line="$1"
  if grep -qxF "$line" "$HOME/.bashrc" 2>/dev/null; then
    skip "~/.bashrc 已有：$line"
    return
  fi
  echo -e "${G}  \$ echo '$line' >> ~/.bashrc${N}"
  if [[ "$DRY_RUN" -eq 0 ]]; then
    echo "$line" >> "$HOME/.bashrc" || die "寫入 ~/.bashrc 失敗"
  fi
}

setup_bashrc() {
  step "4/6 設定 ~/.bashrc"
  append_bashrc_line "source /opt/ros/jazzy/setup.bash"
  # WSLg 預設用 CPU 軟體繪圖；指定 d3d12 才會走 Windows GPU
  append_bashrc_line "export GALLIUM_DRIVER=d3d12"
}

clone_samples() {
  step "5/6 取得書附範例 repo"
  if [[ -d "$SAMPLES_DIR" ]]; then
    skip "$SAMPLES_DIR 已存在"
    return
  fi
  run git clone https://github.com/PacktPublishing/ROS-2-from-Scratch.git "$SAMPLES_DIR" \
    || die "git clone 失敗（檢查網路）"
}

copy_drill() {
  step "6/6 複製演練腳本到 $DEMO_DIR"
  run mkdir -p "$DEMO_DIR" || die "建立 $DEMO_DIR 失敗"
  # 用 drill/. 複製內容而非資料夾本身；重跑時覆蓋成 repo 最新版
  run cp -r "$REPO_ROOT/drill/." "$DEMO_DIR/" || die "複製 drill/ 失敗"
  if [[ "$DRY_RUN" -eq 0 ]]; then
    chmod +x "$DEMO_DIR"/*.sh || die "chmod 失敗"
  else
    echo -e "${G}  \$ chmod +x $DEMO_DIR/*.sh${N}"
  fi
}

main() {
  [[ "$DRY_RUN" -eq 1 ]] && echo -e "${Y}【dry-run 模式】只印出要做的事，不會實際執行${N}"
  preflight
  setup_locale_and_universe
  install_ros_apt_source
  install_packages
  setup_bashrc
  clone_samples
  copy_drill
  echo -e "\n${G}✅ 安裝流程完成${N}"
  echo "接著執行 tools/check-env.sh，並在有 DISPLAY 的環境執行 python3 tools/set-rqt-geometry.py"
  echo "（新開終端機或執行 source ~/.bashrc 讓 ROS 環境生效）"
}

main

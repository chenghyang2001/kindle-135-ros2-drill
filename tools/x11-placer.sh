#!/bin/bash
# 兩螢幕版面（m2right）的圖形視窗搬移器（在 WSL 執行）
#
# 用法：
#   bash x11-placer.sh <監看的父 PID>     # 父程序結束就自己結束
#   bash x11-placer.sh [<父 PID>] --once  # 只跑一輪（測試用）
#
# 為什麼需要：
#   這台電腦兩螢幕 [主螢幕 1 X 0~1920][螢幕 2 X 1920~3840]，WSLg 會忽略 Qt 的
#   -qwindowgeometry「位置」（大小仍有效），新視窗一律開在主螢幕左上角。
#   但視窗出現後用 xdotool windowmove 搬移有效、且不會被拉回，
#   所以在背景輪詢，把演練圖形視窗搬到螢幕 2 右半（X 2880~3840）。
#   三螢幕原版不需要這支：那邊靠 Windows 端 window-guardian.py 把視窗趕到螢幕 3。
#
# 為什麼不用 set -e：迴圈中視窗隨時可能關掉，xdotool 失敗是常態，要容忍。
set -uo pipefail

export DISPLAY=${DISPLAY:-:0}

# 螢幕 2 右半左緣；視窗 X 小於此值才搬，已在右半就不動，讓使用者能自行拖動
RIGHT_HALF_LEFT=2880
MIN_SIZE=50
POLL_INTERVAL=0.5

parent_pid=""
is_once=0
for arg in "$@"; do
  case "$arg" in
    --once) is_once=1 ;;
    *) parent_pid="$arg" ;;
  esac
done

if ! command -v xdotool >/dev/null 2>&1; then
  echo "錯誤：找不到 xdotool（請先 sudo apt install xdotool）" >&2
  exit 1
fi

if [ -z "$parent_pid" ] && [ "$is_once" -eq 0 ]; then
  echo "錯誤：缺少父 PID。用法：bash x11-placer.sh <父 PID> [--once]" >&2
  exit 1
fi

if [ -n "$parent_pid" ] && ! [[ "$parent_pid" =~ ^[0-9]+$ ]]; then
  echo "錯誤：父 PID 必須是數字：$parent_pid" >&2
  exit 1
fi

log_line() {
  echo "$(date '+%H:%M:%S') $*"
}

# 讀視窗幾何，輸出「X Y WIDTH HEIGHT」；失敗（視窗已關）回傳非 0
get_geometry() {
  local win_id="$1" geom_text
  geom_text=$(xdotool getwindowgeometry --shell "$win_id" 2>/dev/null) || return 1
  local x="" y="" w="" h=""
  while IFS='=' read -r key value; do
    case "$key" in
      X) x="$value" ;;
      Y) y="$value" ;;
      WIDTH) w="$value" ;;
      HEIGHT) h="$value" ;;
    esac
  done <<< "$geom_text"
  [ -n "$x" ] && [ -n "$y" ] && [ -n "$w" ] && [ -n "$h" ] || return 1
  echo "$x $y $w $h"
}

# 列出符合名稱樣式、且大小夠大的可見視窗 id（數字排序）
# 太小的通常是 Qt 的隱藏輔助視窗，搬了沒意義
find_windows() {
  local pattern="$1" win_id geom w h
  xdotool search --onlyvisible --name "$pattern" 2>/dev/null | sort -n -u | while read -r win_id; do
    [ -n "$win_id" ] || continue
    geom=$(get_geometry "$win_id") || continue
    read -r _ _ w h <<< "$geom"
    if [ "$w" -ge "$MIN_SIZE" ] && [ "$h" -ge "$MIN_SIZE" ]; then
      echo "$win_id"
    fi
  done
}

# 搬移單一視窗；is_force=1 時不論目前 X 都搬
place_window() {
  local win_id="$1" target_x="$2" target_y="$3" is_force="$4" label="$5"
  local geom cur_x
  geom=$(get_geometry "$win_id") || return 0
  read -r cur_x _ _ _ <<< "$geom"
  if [ "$is_force" -eq 0 ] && [ "$cur_x" -ge "$RIGHT_HALF_LEFT" ]; then
    return 0
  fi
  if xdotool windowmove "$win_id" "$target_x" "$target_y" 2>/dev/null; then
    log_line "搬移 $label id=$win_id → ($target_x,$target_y)"
  else
    log_line "搬移失敗 $label id=$win_id（視窗可能已關閉）"
  fi
}

# 同一個視窗可能同時符合多個樣式（例如標題含 rqt 又含 RViz），用此表避免重複搬
declare -A handled_ids
prev_turtle_count=0

place_turtles() {
  local -a turtle_ids=()
  local win_id
  while read -r win_id; do
    [ -n "$win_id" ] && turtle_ids+=("$win_id")
  done < <(find_windows "TurtleSim")

  local count=${#turtle_ids[@]}
  # 數量變了（例如第 9 章開第二隻烏龜）就全部重排，否則只搬不在右半的
  local is_force=0
  if [ "$count" -ne "$prev_turtle_count" ]; then
    is_force=1
  fi
  prev_turtle_count=$count

  if [ "$count" -eq 1 ]; then
    place_window "${turtle_ids[0]}" 3180 100 "$is_force" "TurtleSim"
  elif [ "$count" -ge 2 ]; then
    # 第 9 章兩隻烏龜上下排；第 3 隻以後不處理
    place_window "${turtle_ids[0]}" 2916 40 "$is_force" "TurtleSim#1"
    place_window "${turtle_ids[1]}" 2916 530 "$is_force" "TurtleSim#2"
  fi
  for win_id in "${turtle_ids[@]}"; do
    handled_ids["$win_id"]=1
  done
}

place_by_pattern() {
  local pattern="$1" target_x="$2" target_y="$3" win_id
  while read -r win_id; do
    [ -n "$win_id" ] || continue
    [ -n "${handled_ids[$win_id]:-}" ] && continue
    handled_ids["$win_id"]=1
    place_window "$win_id" "$target_x" "$target_y" 0 "$pattern"
  done < <(find_windows "$pattern")
}

run_round() {
  handled_ids=()
  place_turtles
  place_by_pattern "RViz" 2916 20
  place_by_pattern "Joint State Publisher" 2916 300
  place_by_pattern "rqt" 2916 40
}

is_parent_alive() {
  [ -z "$parent_pid" ] && return 0
  kill -0 "$parent_pid" 2>/dev/null
}

log_line "x11-placer 啟動（DISPLAY=$DISPLAY 父 PID=${parent_pid:-無}）"

if [ "$is_once" -eq 1 ]; then
  run_round
  log_line "x11-placer --once 完成"
  exit 0
fi

while is_parent_alive; do
  run_round
  sleep "$POLL_INTERVAL"
done

log_line "父程序 $parent_pid 已結束，x11-placer 停止"
exit 0

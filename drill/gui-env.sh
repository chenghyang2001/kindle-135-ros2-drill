# 圖形視窗統一設定：X11 模式＋指定座標，讓視窗直接開在螢幕 3（X 0～1280）
export DISPLAY=${DISPLAY:-:0}
export QT_QPA_PLATFORM=${QT_QPA_PLATFORM:-xcb}
export GALLIUM_DRIVER=d3d12
TURTLE_GEOM="-qwindowgeometry 500x500+720+100"

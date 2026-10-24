#!/usr/bin/env python3
"""包裝 joint_state_publisher_gui：建立視窗時補上 -qwindowgeometry，讓滑桿視窗直接開在螢幕 3。"""
import os
import joint_state_publisher_gui.joint_state_publisher_gui as jsp

GEOM = os.environ.get("JSP_GEOM", "300x540+880+60")
_orig_qapp = jsp.QApplication
jsp.QApplication = lambda argv: _orig_qapp(list(argv) + ["-qwindowgeometry", GEOM])

if __name__ == "__main__":
    jsp.main()

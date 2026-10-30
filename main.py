#!/usr/bin/env python3
"""
proj-publisher — 入口点

设置日志、创建 QApplication，启动主窗口。
"""

import sys
import logging

# 配置基础日志（控制台输出）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from PySide6.QtWidgets import QApplication

from main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ProjPublisher")
    app.setOrganizationName("AI_Mine")

    win = MainWindow()
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

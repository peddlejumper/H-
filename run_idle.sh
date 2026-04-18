#!/bin/bash
# H# IDLE 启动脚本

# 切换到脚本所在目录
cd "$(dirname "$0")"

# 清除Python缓存
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null

# 启动IDLE
/usr/local/bin/python3 idle_pyqt.py "$@"

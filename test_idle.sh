#!/bin/bash
echo "清除所有Python缓存..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null

echo "启动H# IDLE..."
/usr/local/bin/python3 idle_pyqt.py "$@"

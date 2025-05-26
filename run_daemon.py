#!/usr/bin/env python3
# filepath: /workspace/run_daemon.py

# 确保 supysonic 包可导入
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入并运行守护进程
from supysonic.daemon import main

if __name__ == "__main__":
    main()
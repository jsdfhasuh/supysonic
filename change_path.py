#!/usr/bin/env python3
# filepath: /workspace/supysonic/debug_scan_logic.py

import sys
from supysonic.config import IniConfig
from supysonic.db import Folder, init_database, release_database,Track,Image
from supysonic.scanner import Scanner


def change_path():
    """直接调试底层的扫描逻辑而不使用 CLI 层"""



        # 初始化配置和数据库
    config = IniConfig.from_common_locations()
    init_database(config.BASE["database_uri"])
    folders = Folder.select()
    for folder in folders:
        path = folder.path
        if 'test' in path:
            new_path = path.replace('test', 'completed')
            print(f"Changing path from {path} to {new_path}")
            folder.path = new_path
            folder.save()
        pass
    pass
    tracks = Track.select()
    for track in tracks:
        path = track.path
        if 'test' in path:
            new_path = path.replace('/test', '/completed')
            print(f"Changing path from {path} to {new_path}")
            track.path = new_path
            track.save()
    pass
    for image in Image.select():
        path = image.path
        if 'test' in path:
            new_path = path.replace('/test', '/completed')
            print(f"Changing path from {path} to {new_path}")
            image.path = new_path
            image.save()



if __name__ == "__main__":
    change_path()

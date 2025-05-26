#!/usr/bin/env python3
# filepath: /workspace/supysonic/debug_scan_logic.py

import sys
from supysonic.config import IniConfig
from supysonic.db import Folder, init_database, release_database
from supysonic.scanner import Scanner

def debug_scan_logic():
    """直接调试底层的扫描逻辑而不使用 CLI 层"""
    
    # 初始化配置和数据库
    config = IniConfig.from_common_locations()
    init_database(config.BASE["database_uri"])
    
    try:
        # 获取扩展名列表
        extensions = config.BASE["scanner_extensions"]
        if extensions:
            extensions = extensions.split(" ")
        
        # 创建扫描器
        scanner = Scanner(
            force=False,
            extensions=extensions,
            follow_symlinks=config.BASE["follow_symlinks"]
        )
        
        # 获取要扫描的文件夹
        folder_name = "test"  # 替换为你要扫描的文件夹名称
        folders = []
        
        try:
            folder = Folder.get(Folder.name == folder_name, Folder.root == True)
            folders.append(folder)
            print(f"找到文件夹: {folder.name} - {folder.path}")
        except Folder.DoesNotExist:
            print(f"找不到文件夹: {folder_name}")
            return
        
        # 添加文件夹到扫描队列
        for folder in folders:
            scanner.queue_folder(folder_name)
        
        # 运行扫描
        scanner.run()
        
        # 获取扫描统计信息
        stats = scanner.stats()
        print("\n扫描完成")
        print(
            f"添加: {stats.added.artists} 位艺术家, {stats.added.albums} 张专辑, {stats.added.tracks} 首歌曲"
        )
        print(
            f"删除: {stats.deleted.artists} 位艺术家, {stats.deleted.albums} 张专辑, {stats.deleted.tracks} 首歌曲"
        )
        if stats.errors:
            print("错误:")
            for err in stats.errors:
                print("- " + err)
    finally:
        release_database()

if __name__ == "__main__":
    debug_scan_logic()
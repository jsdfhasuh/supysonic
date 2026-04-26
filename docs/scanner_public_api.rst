扫描器公开 API
==============

本页聚焦于 ``supysonic/scanner.py`` 暴露出来的公开审查面。

当你审查调用方如何与扫描器交互时，使用本文档。如果你想跟踪 ``scanner_func`` 下辅助层的执行细节，请使用
:doc:`scanner_internal_flow`。

.. contents:: 本页内容
   :local:
   :depth: 2


模块 ``scanner.py``
-------------------

模块角色
~~~~~~~~

``scanner.py`` 现在是扫描功能的公开门面。它负责：

* ``Scanner`` 线程对象，
* 回调与队列的连接，
* 调用方使用的一组稳定公开方法，
* 将工作委托给 ``scanner_func`` 下的辅助模块。


类 ``Scanner(Thread)``
----------------------

``Scanner.__init__(force=False, extensions=None, follow_symlinks=False, progress=None, on_folder_start=None, on_folder_end=None, on_done=None)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  初始化扫描选项、回调钩子、队列状态、运行时统计信息，以及已加载的应用配置。

输入
  ``force``
    即使文件修改时间没有增加，也强制重新扫描。

  ``extensions``
    可选的可扫描文件扩展名白名单。提供时，该值必须是 ``list``。

  ``follow_symlinks``
    控制目录遍历时是否跟随符号链接。

  ``progress``
    可选回调，接收 ``(folder_name, scanned_count)``。

  ``on_folder_start``
    可选回调，在某个文件夹开始扫描前接收根 ``Folder`` 行。

  ``on_folder_end``
    可选回调，在某个文件夹扫描结束后接收根 ``Folder`` 行。

  ``on_done``
    可选回调，在完整的队列扫描生命周期结束后触发。

返回
  ``None``。

说明
  当 ``extensions`` 不为 ``None`` 且不是列表时，会抛出 ``TypeError``。


``Scanner.scanned``
~~~~~~~~~~~~~~~~~~~

目的
  暴露 ``stats.scanned`` 的属性。

返回
  已扫描文件的整数计数。


``Scanner.force_scan``
~~~~~~~~~~~~~~~~~~~~~~

目的
  暴露是否启用了强制重新扫描模式的属性。

返回
  ``bool``。


``Scanner.follow_symlinks``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  暴露目录遍历是否跟随符号链接的属性。

返回
  ``bool``。


``Scanner.scan_config``
~~~~~~~~~~~~~~~~~~~~~~~

目的
  暴露已加载 ``IniConfig`` 对象的属性。

返回
  ``IniConfig``。


``Scanner.stop_requested``
~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  暴露是否已请求调用 ``stop()`` 的属性。

返回
  ``bool``。


``Scanner.report_progress(folder_name, scanned)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  在已配置时触发进度回调。

输入
  ``folder_name``
    当前正在扫描的根文件夹名称。

  ``scanned``
    在该根文件夹内已扫描的文件数量。

返回
  ``None``。

调用方
  ``scanner_func.scanner_folder._scanFolderEntries``。


``Scanner.handle_folder_start(folder)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  在已配置时触发文件夹开始回调。

输入
  根 ``Folder`` 行。

返回
  ``None``。

调用方
  ``scanner_func.scanner_folder.scanFolder``。


``Scanner.handle_folder_end(folder)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  在已配置时触发文件夹结束回调。

输入
  根 ``Folder`` 行。

返回
  ``None``。

调用方
  ``scanner_func.scanner_folder.scanFolder``。


``Scanner.handle_done()``
~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  在已配置时触发扫描完成回调。

返回
  ``None``。

调用方
  ``scanner_func.scanner_runtime.runScanner``。


``Scanner.queue_folder(folder_name)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  将一个根文件夹名称加入扫描队列。

输入
  作为 ``str`` 的 ``folder_name``。

返回
  ``None``。

说明
  当输入不是字符串时，会抛出 ``TypeError``。


``Scanner.next_queued_folder()``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  供运行时辅助层使用的非阻塞队列弹出辅助方法。

返回
  下一个文件夹名称字符串；如果队列为空，则返回 ``None``。


``Scanner.run()``
~~~~~~~~~~~~~~~~~

目的
  完整队列扫描生命周期的线程入口点。

返回
  ``None``。

调用
  ``scanner_func.scanner_runtime.runScanner``。


``Scanner.stop()``
~~~~~~~~~~~~~~~~~~

目的
  请求关闭扫描器。

返回
  ``None``。


``Scanner.scan_folder(folder)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  用于扫描一个根文件夹并执行相关清理的公开入口。

输入
  根 ``Folder`` 行。

返回
  ``None``。

调用
  ``scanner_func.scanner_folder.scanFolder``。


``Scanner.prune()``
~~~~~~~~~~~~~~~~~~~

目的
  在遍历后移除已删除或为空的媒体库行。

返回
  ``None``。

调用
  ``scanner_func.scanner_runtime.pruneLibrary``。


``Scanner.should_scan_extension(path)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  判断文件路径是否应被视为可扫描的媒体文件。

输入
  文件路径字符串。

返回
  ``True`` 或 ``False``。

说明
  如果未配置扩展名过滤器，此函数始终返回 ``True``。


``Scanner.scan_file(path_or_direntry)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  公开的单文件扫描入口。

输入
  路径字符串或 ``os.DirEntry``。

返回
  ``None``。

调用
  ``scanner_func.scanner_pipeline.processScanFile``。


``Scanner.remove_file(path)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  删除已消失或变为无效的文件对应的 ``Track`` 行。

输入
  文件路径字符串。

返回
  ``None``。

调用
  ``scanner_func.scanner_records.removeFile``。


``Scanner.move_file(src_path, dst_path)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  为移动或重命名事件更新 ``Track`` 行。

输入
  源路径和目标路径字符串。

返回
  ``None``。

调用
  ``scanner_func.scanner_records.moveFile``。


``Scanner.find_cover(dirpath)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  刷新单个目录的文件夹级封面发现。

输入
  目录路径字符串。

返回
  ``None``。

调用
  ``scanner_func.scanner_cover.findCover``。


``Scanner.add_cover(path)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  处理新创建或已更新的封面图片文件。

输入
  封面图片路径字符串。

返回
  ``None``。

调用
  ``scanner_func.scanner_cover.addCover``。


``Scanner.find_lost_information()``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  执行扫描后的元数据补全。

返回
  ``None``。

调用
  ``scanner_func.scanner_enrich.findLostInformation``。


``Scanner.decideAllPositions()``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  在扫描后修复专辑艺术家和曲目艺术家的位置顺序。

返回
  ``None``。

调用
  ``scanner_func.scanner_positions.decideAllPositions``。


``Scanner.renow_album_by_nfo(path)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  应用由 ``album.nfo`` 驱动的专辑和曲目修复。

输入
  ``album.nfo`` 的路径，或专辑目录的路径。

返回
  ``None``。

调用
  ``scanner_func.scanner_nfo.renowAlbumByNfo``。


``Scanner.stats()``
~~~~~~~~~~~~~~~~~~~

目的
  返回可变的运行时统计对象。

返回
  ``scanner_func.scanner_state.Stats``。


顶层辅助函数 ``renow_track_hash()``
-----------------------------------

目的
  当存储值等于字面字符串 ``"NULL"`` 时，回填 ``Track.content_hash`` 的值。

返回
  ``None``。

调用
  ``scanner_func.scanner_records.renowTrackHash``。

说明
  此函数检查的是字符串 ``"NULL"``，而不是 SQL ``NULL``。


公开生命周期摘要
----------------

公开调用流程如下：

1. 创建 ``Scanner``。
2. 调用一次或多次 ``queue_folder()``。
3. 启动线程，或在受控上下文中调用 ``run()``。
4. 运行时辅助层清空已排队的根文件夹。
5. 每个根文件夹都会通过 ``scan_folder()`` 扫描。
6. 文件通过 ``scan_file()`` 处理。
7. 遍历完成后，扫描器会修复关系位置、清理陈旧行、执行元数据补全，最后触发 ``handle_done()``。


面向审查的行为说明
------------------

以下这些面向公开接口的行为在审查功能时很重要：

* 队列项是根文件夹名称，而不是路径。
* 队列实现基于集合，因此处理顺序不是确定性的。
* ``should_scan_extension()`` 在匹配前会将扩展名转换为小写。
* ``renow_track_hash()`` 只会更新哈希值字面等于 ``"NULL"`` 的行。
* 所有重量级实现细节现在都位于 :doc:`scanner_internal_flow`。

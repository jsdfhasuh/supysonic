文件夹进入扫描后的完整流程
==========================

本页说明一个根文件夹从进入扫描队列，到整个扫描线程完成后处理阶段的真实执行顺序。

如果你想查看 ``Scanner`` 的公开门面，使用 `scanner_public_api`_。
如果你想查看 ``scanner_func`` 下每个辅助模块的职责，使用 `scanner_internal_flow`_。

.. _scanner_public_api: scanner_public_api.html
.. _scanner_internal_flow: scanner_internal_flow.html

.. contents:: 本页内容
   :local:
   :depth: 2


总览
----

当前源码中的主链路如下：

::

   Scanner.queue_folder()
   -> Scanner.run()
   -> runScanner()
   -> _scanQueuedFolders()
   -> Scanner.scan_folder()
   -> scanFolder()
   -> _scanFolderEntries()
   -> Scanner.scan_file()
   -> processScanFile()
   -> _removeDeletedFolders() / _removeDeletedTracks() / _refreshFolderCovers()
   -> decideAllPositions()
   -> pruneLibrary()
   -> findLostInformation()
   -> Scanner.handle_done()


1. 文件夹如何进入队列
----------------------

入口是 ``Scanner.queue_folder(folder_name)``。

它只做两件事：

* 校验 ``folder_name`` 必须是 ``str``。
* 把该名称放入 ``ScanQueue``。

这里要注意，当前入队的不是路径，而是根文件夹名称。后续真正取出队列时，运行时层会用
``Folder.get(name=folderName, root=True)`` 回查数据库里的根 ``Folder``。

``ScanQueue`` 还有两个当前行为值得提前说明：

* 它基于 ``set`` 去重。
* 它不保证插入顺序。

这意味着队列更像一个“待扫描根文件夹集合”，而不是严格 FIFO 队列。


2. 扫描线程如何开始工作
------------------------

``Scanner.run()`` 不直接展开扫描逻辑，而是委托给 ``scanner_func.scanner_runtime.runScanner()``。

``runScanner()`` 的总体顺序是：

1. ``open_connection(True)`` 打开数据库连接。
2. 调用 ``_scanQueuedFolders(scanner)`` 逐个消费队列中的根文件夹。
3. 队列处理结束后，依次执行：

   * ``scanner.decideAllPositions()``
   * ``pruneLibrary(scanner)``
   * ``scanner.find_lost_information()``
   * ``scanner.handle_done()``

4. 在 ``finally`` 中关闭数据库连接。

也就是说，一个文件夹进入扫描后，不只是会触发该文件夹自身的遍历；当整个队列扫描结束时，
还会触发一次全库范围的关系修复、清理和元数据补全。


3. 队列项如何转换成根文件夹扫描
--------------------------------

``_scanQueuedFolders(scanner)`` 会循环调用 ``scanner.next_queued_folder()``。

对每个出队项，当前行为是：

1. 取出一个 ``folderName``。
2. 如果队列空了，返回 ``None``，循环结束。
3. 通过 ``Folder.get(name=folderName, root=True)`` 查找根文件夹。
4. 如果数据库里找不到该根文件夹，直接跳过这个队列项。
5. 找到后调用 ``scanner.scan_folder(folder)``。

这里说明了一个很重要的边界：真正开始扫描前，数据库里必须已经存在对应的根 ``Folder`` 记录。


4. 单个根文件夹的扫描入口
--------------------------

``Scanner.scan_folder(folder)`` 只是公开门面，实际实现位于 ``scanFolder(scanner, folder, logger)``。

``scanFolder()`` 的顺序固定为：

1. 记录日志 ``Scanning folder %s``。
2. 调用 ``scanner.handle_folder_start(folder)``。
3. 调用 ``_scanFolderEntries(scanner, folder)``，遍历文件系统并处理单文件。
4. 调用 ``_removeDeletedFolders(scanner, folder)``，清理数据库中已不存在的目录树。
5. 调用 ``_removeDeletedTracks(scanner, folder)``，清理已删除或扩展名已不再允许的曲目。
6. 调用 ``_refreshFolderCovers(scanner, folder)``，重扫该根目录下的目录级封面。
7. 如果没有收到停止请求，写回 ``folder.last_scan`` 并 ``folder.save()``。
8. 调用 ``scanner.handle_folder_end(folder)``。

因此，单个根文件夹的扫描不是“只遍历文件”，而是“遍历 + 清理 + 封面刷新 + 状态回写”。


5. 文件系统遍历阶段
--------------------

``_scanFolderEntries(scanner, folder)`` 负责真正走磁盘目录。

当前实现使用一个 ``toScan`` 列表保存待遍历目录，初始值是 ``[folder.path]``。循环过程中会：

1. ``pop()`` 一个目录路径。
2. 用 ``os.scandir(path)`` 遍历该目录下的条目。
3. 对每个条目按顺序判断：

   * 名称以 ``.`` 开头时直接跳过。
   * 是符号链接且 ``scanner.follow_symlinks`` 为 ``False`` 时跳过。
   * 是目录时，把 ``entry.path`` 加入 ``toScan``。
   * 是文件且 ``scanner.should_scan_extension(entry.path)`` 为真时，进入单文件扫描。

单文件扫描时会额外做这些事情：

* 调用 ``scanner.scan_file(entry)``。
* ``scanner.stats().scanned += 1``。
* 更新当前根文件夹内的 ``scanned`` 计数。
* 调用 ``scanner.report_progress(folder.name, scanned)``。

这说明进度回调看到的是“当前根文件夹内已处理文件数”，不是整个线程的全局百分比。


6. 单文件是如何被处理的
------------------------

``Scanner.scan_file(path_or_direntry)`` 会委托给 ``processScanFile(scanner, path_or_direntry)``。

``processScanFile()`` 的实际顺序如下。

``getScanTargetInfo()``：规范化输入
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* 如果输入是字符串，就检查路径是否存在，并读取 ``basename`` 与 ``os.stat``。
* 如果输入是 ``os.DirEntry``，就直接使用 ``entry.path``、``entry.name`` 与 ``entry.stat()``。
* 如果目标路径不存在，直接返回，不进入后续流程。

``_validateScanPath()``：校验路径是否可编码
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* 尝试执行 ``path.encode("utf-8")``。
* 如果抛出 ``UnicodeError``，把该路径追加到 ``scanner.stats().errors``，然后终止该文件扫描。

``existing_tracks``：当前 FLAC 计数
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

如果 ``os.path.isfile(path)`` 且路径字符串里包含 ``".flac"``，就递增
``scanner.stats().existing_tracks``。

这是当前实现保留的统计行为，它使用的是字符串包含判断，不是严格的扩展名比较。

``loadTrackForScan()``：决定是否继续扫描
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

这个步骤会先查数据库里的现有 ``Track`` 记录，然后决定是否需要继续处理：

1. ``Track.get_or_none(path=path)`` 查旧记录。
2. 如果旧记录存在，且 ``scanner.force_scan`` 为 ``False``，且当前 ``mtime`` 没有大于
   ``track.last_modification``，则直接返回 ``(track, None, None)``，表示跳过该文件。
3. 否则调用 ``tryLoadTag(path)`` 读取媒体标签。
4. 如果标签读取失败：

   * 若数据库已有旧 ``Track``，调用 ``scanner.remove_file(path)`` 删除旧记录。
   * 返回 ``(track, None, None)``。

5. 如果标签读取成功：

   * 已有 ``Track`` 时，准备一个空字典作为更新载荷。
   * 新 ``Track`` 时，先准备 ``{"path": path}`` 作为初始载荷。

``resolveAlbumContext()``：准备专辑上下文
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

这一阶段会读取当前音频文件所在目录下的 ``album.nfo``，然后组合 NFO 和 tag 中的专辑级信息。

具体顺序是：

1. 读取 ``album.nfo``。
2. 从原始 tag 中取 ``artist`` 和 ``albumartist``。
3. 优先使用 NFO 中的 ``album.albumartist`` 和 ``album.artist``。
4. 如果 NFO 没有对应值，就回退到 tag 值。
5. 如果两者都没有，就回退为 ``["unknown"]``。
6. 调用 ``recordAlbumArtists(scanner, album_artists, sanitizeString(tag.album))``。

``recordAlbumArtists()`` 会继续完成三件事：

* 归一化艺术家名称；
* 通过 ``findArtist()`` 确保 ``Artist`` 存在；
* 通过 ``Album.get_or_create(...)`` 和 ``AlbumArtist.get_or_create(...)`` 保证专辑与专辑艺术家关系存在。

最终这个阶段会返回：

* ``nfo_data``
* 回退用的 ``artists`` 列表
* 专辑行对象 ``album``

``buildTrackData()``：构造 Track 字段
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

这里会根据 tag 组装稍后写入 ``Track`` 的字段字典，包括：

* ``disc``
* ``number``
* ``title``
* ``year``
* ``genre``
* ``duration``
* ``has_art``
* ``bitrate``
* ``last_modification``

其中 ``title`` 会在缺失时回退到文件名，并截断到 255 个字符。

``resolveTrackArtists()``：决定曲目艺术家
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

这个阶段会优先尝试从 ``nfo_data['album']['track']`` 中找到与当前曲目匹配的记录，并读取其
``artist``；如果没有匹配到，就回退为前面的 ``artists`` 列表。

随后它会返回：

* 当前曲目的艺术家列表 ``track_artists``
* 主艺术家 ``track_artist``，它来自 ``findArtist(scanner, track_artists[0])``

``createOrUpdateTrack()``：写入 Track
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

如果当前文件对应的 ``Track`` 不存在：

1. 用 ``findRootFolder(path)`` 找到所属根文件夹。
2. 用 ``findFolder(path)`` 找到或补建中间 ``Folder`` 层级。
3. 写入 ``album``、``artist``、``created`` 等字段。
4. 调用 ``Track.create(**track_data)`` 新建记录。

如果当前文件已有 ``Track``：

1. 比较专辑和主艺术家是否变化。
2. 对 ``track_data`` 中的字段逐个 ``setattr``。
3. 调用 ``track.save()`` 保存。

无论新建还是更新，只要发生 ``ValueError``，就会把路径记到 ``scanner.stats().errors`` 并终止。

``recordTrackArtists()``：写入曲目艺术家关系
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

当 ``Track`` 保存成功后，最后一步是调用 ``recordTrackArtists(scanner, track_artists, track)``。

这个函数会：

* 归一化艺术家列表；
* 通过 ``findArtist()`` 确保每个 ``Artist`` 存在；
* 通过 ``TrackArtist.get_or_create(...)`` 保证曲目与艺术家关系存在。


7. 单个根文件夹扫描完成后的清理
--------------------------------

``scanFolder()`` 在完成文件遍历后，会继续执行三个清理步骤。

``_removeDeletedFolders()``：清理已不存在的目录树
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

它会从当前根 ``Folder`` 开始遍历数据库中的目录层级：

* 如果某个非根目录的 ``path`` 在磁盘上已经不是目录，就调用
  ``currentFolder.delete_hierarchy()`` 删除该目录树对应的数据，并把删除的 track 数量累计到
  ``scanner.stats().deleted.tracks``。
* 如果目录仍存在，就继续检查它的子目录。

``_removeDeletedTracks()``：清理已失效曲目
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

它会遍历当前根目录下数据库中的所有 ``Track``：

* 如果磁盘上文件已经不存在，调用 ``scanner.remove_file(track.path)``。
* 如果文件仍存在，但扩展名已经不在当前允许集合里，也调用 ``scanner.remove_file(track.path)``。

``_refreshFolderCovers()``：刷新目录级封面
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

它会遍历当前根目录及其所有子目录，对每个目录调用 ``scanner.find_cover(currentFolder.path)``。

``findCover()`` 的核心行为是：

* 先通过目录路径找到对应 ``Folder``。
* 取该目录下第一首曲目作为专辑上下文。
* 用 ``find_cover_in_folder(folder.path, album_name)`` 查找最合适的封面文件。
* 找到后建立或复用 ``Image`` 记录。


8. 文件夹扫描结束时会发生什么
--------------------------------

如果没有收到 ``stop_requested``：

* ``scanFolder()`` 会把 ``folder.last_scan`` 更新为当前时间戳。
* 然后 ``folder.save()``。

无论是否更新 ``last_scan``，函数最后都会调用 ``scanner.handle_folder_end(folder)``。

这意味着“文件夹结束回调”比 ``last_scan`` 更新更稳定；停止扫描时，回调仍然可能被触发。


9. 队列全部处理完之后的全局后处理
----------------------------------

当 ``_scanQueuedFolders()`` 结束后，``runScanner()`` 还会继续执行整库后处理。

``decideAllPositions()``：修复位置和主艺术家
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

这个阶段会：

* 删除无效的 ``AlbumArtist(position == 0)`` 关系；
* 找出仍需要修复位置的专辑；
* 根据专辑内各艺术家在 ``TrackArtist`` 中出现的次数排序；
* 回写 ``AlbumArtist.position``；
* 把第一名艺术家设为 ``album.artist``；
* 把同一专辑下相关 ``TrackArtist.position`` 与 ``track.artist`` 一并修正。

``pruneLibrary()``：清理孤立库记录
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

如果没有收到停止请求，它会：

* 执行 ``Album.prune()``
* 执行 ``Artist.prune()``
* 执行 ``Folder.prune()``

其中 album 和 artist 的删除计数会累计到 ``scanner.stats().deleted``。

``findLostInformation()``：补全缺失元数据
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

这是扫描完成后的补全阶段，主要做三类事情：

1. 对缺少年份的专辑调用 ``repairAlbumYear()``。
2. 对缺少封面的专辑调用 ``repairAlbumCover()``。
3. 对缺少资料或图片的艺术家调用 ``repairArtistProfiles()`` 与 ``repairMissingArtistImages()``。

这个阶段可能会读取本地文件，也可能会依赖 Last.fm、Spotify、MusicBrainz 等外部信息源。

``Scanner.handle_done()``：整个扫描线程结束
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

这是整次队列扫描生命周期的最后一个公开回调点。它不是“某个文件夹结束”，而是“整个队列及其
后处理全部完成”。


10. 当前实现里值得注意的行为
-------------------------------

以下行为都直接来自当前源码，阅读扫描日志或排查问题时需要一起考虑。

* ``queue_folder()`` 入队的是根文件夹名称，不是路径。
* ``ScanQueue`` 基于 ``set``，因此会去重且不保证顺序。
* 遍历时会跳过隐藏项；默认也不会跟随符号链接。
* 已有 ``Track`` 且文件修改时间没有变新时，单文件会被直接短路跳过。
* ``processScanFile()`` 对 ``existing_tracks`` 的统计是 ``".flac" in path.lower()``。
* ``resolveTrackArtists()`` 当前对 NFO 中 ``disc`` / ``number`` 的匹配顺序存在对调现象，因此
  某些曲目可能不会按预期命中 NFO 中的曲目艺术家。
* ``runScanner()`` 在队列处理结束后，仍会继续执行 ``decideAllPositions()`` 和
  ``find_lost_information()``；其中只有 ``pruneLibrary()`` 自身先检查了 ``stop_requested``。

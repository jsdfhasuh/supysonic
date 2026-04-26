扫描器内部流程
==============

本页记录 ``supysonic/scanner_func`` 下的辅助层实现。

当你审查扫描生命周期如何被拆分为更小的模块，以及数据如何从文件系统遍历流转到数据库更新与扫描后修复步骤时，请使用本文档。

.. contents:: 本页内容
   :local:
   :depth: 2


scanner_func/__init__.py
------------------------

模块角色
~~~~~~~~

此文件不实现业务逻辑。它的职责是通过一个稳定的导入面重新导出扫描器辅助类和函数。


scanner_func/scanner_state.py
-----------------------------

模块角色
~~~~~~~~

供扫描器门面和辅助模块使用的运行时状态容器。


类 ``StatsDetails``
~~~~~~~~~~~~~~~~~~~

``StatsDetails.__init__()``
  目的
    初始化一个小型计数桶，将 ``artists``、``albums`` 和 ``tracks`` 全部设为 ``0``。
  返回
    ``None``。


类 ``Stats``
~~~~~~~~~~~~

``Stats.__init__()``
  目的
    初始化聚合扫描统计结构。
  返回
    ``None``。
  已初始化状态
    ``scanned``
      当前运行期间已扫描文件的总数。

    ``existing_tracks``
      供逐文件流水线使用、用于当前 FLAC 记账的计数器。

    ``added``
      为新建 artists/albums/tracks 准备的 ``StatsDetails``。

    ``deleted``
      为已删除 artists/albums/tracks 准备的 ``StatsDetails``。

    ``errors``
      路径校验或持久化失败的文件路径列表。

    ``lost_covers``
      供补全和封面修复使用的 ``StatsDetails``。

    ``lost_covers_albums``
      将专辑名映射到代表性路径的字典，用于审查缺失的专辑封面。

    ``lost_covers_artists``
      缺少简介/图片数据的艺术家名称列表。

    ``lost_year_albums``
      将专辑名映射到代表性路径的字典，用于审查缺失年份的专辑。


类 ``ScanQueue(Queue)``
~~~~~~~~~~~~~~~~~~~~~~~

``ScanQueue._init(maxsize)``
  目的
    用 ``set`` 替换队列存储，并初始化最近一次返回的哨兵值。
  返回
    ``None``。

``ScanQueue._put(item)``
  目的
    将一个项目插入基于集合的队列，除非它与 ``_get`` 最近一次返回的项目相同。
  返回
    ``None``。
  说明
    该队列会进行激进去重，并且不保留插入顺序。

``ScanQueue._get()``
  目的
    从基于集合的队列中弹出一个项目，并将其记录为最近一次结果。
  返回
    被弹出的队列项。


scanner_func/scanner_common.py
------------------------------

模块角色
~~~~~~~~

在多个扫描器模块之间共享的底层辅助函数。


``sanitizeString(value)``
~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  从字符串中移除嵌入的空字节以及两端空白。

输入
  字符串或 ``None``。

返回
  清洗后的字符串；如果输入为 ``None``，则返回 ``None``。


``tryLoadTag(path)``
~~~~~~~~~~~~~~~~~~~~

目的
  通过 ``mediafile.MediaFile`` 加载媒体元数据。

输入
  文件路径字符串。

返回
  成功时返回 ``MediaFile`` 实例；如果抛出 ``mediafile.UnreadableFileError``，则返回 ``None``。

说明
  这里不会处理其他异常类型。


scanner_func/scanner_types.py
-----------------------------

模块角色
~~~~~~~~

供扫描流水线使用的小型共享类型定义。


类 ``ScanTarget``
~~~~~~~~~~~~~~~~~

目的
  表示一个已规范化扫描目标的不可变打包对象。

字段
  ``path``
    媒体文件路径。

  ``basename``
    路径的最后一个组成部分。

  ``stat``
    目标的 ``os.stat_result``。


scanner_func/scanner_file.py
----------------------------

模块角色
~~~~~~~~

规范化文件系统输入，并在开始写入数据库前准备原始专辑/曲目上下文。


``getScanTargetInfo(path_or_direntry)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  将路径字符串或 ``os.DirEntry`` 规范化为 ``ScanTarget``。

输入
  路径字符串或目录项。

返回
  如果目标存在，则返回 ``ScanTarget``；如果路径字符串缺失，则返回 ``None``。

调用方
  ``scanner_pipeline.processScanFile``。


``loadTrackForScan(scanner, path, mtime)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  加载已有的 ``Track`` 行，判断某个文件是否仍需要扫描，并在流水线应继续时加载媒体标签。

输入
  ``scanner``、文件 ``path`` 和整数 ``mtime``。

返回
  当文件应被跳过或标签加载失败时，返回 ``(track, None, None)``。

  当文件应继续处理时，返回 ``(track_or_none, tag, track_data_dict)``。

调用
  ``Track.get_or_none``、``tryLoadTag`` 和 ``scanner.remove_file``。

行为说明
  当已存储的 ``last_modification`` 更新或相等，且 ``scanner.force_scan`` 为 false 时，该文件会被跳过。


``resolveAlbumContext(scanner, path, tag)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  加载 ``album.nfo``，确定专辑艺术家和回退曲目艺术家，并确保专辑行及专辑-艺术家关系存在。

输入
  ``scanner``、文件 ``path`` 和已解析的标签对象。

返回
  ``(nfo_data, artists, album_row)``。

  ``artists`` 是回退到曲目级别的艺术家列表。

调用
  ``readNfo``、``sanitizeString`` 和 ``recordAlbumArtists``。

行为说明
  第三个返回值是专辑行对象，尽管旧命名可能暗示它是一个 id。


``buildTrackData(scanner, basename, mtime, tag)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  构建稍后会写入 ``Track`` 的字段字典。

输入
  ``scanner``（当前未使用）、文件 ``basename``、整数 ``mtime`` 以及标签对象。

返回
  包含以下内容的字典：

  * ``disc``
  * ``number``
  * ``title``
  * ``year``
  * ``genre``
  * ``duration``
  * ``has_art``
  * ``bitrate``
  * ``last_modification``

行为说明
  ``title`` 会回退为 basename，并被截断到 255 个字符。


scanner_func/scanner_pipeline.py
--------------------------------

模块角色
~~~~~~~~

负责从目标发现到关系更新的单文件扫描流水线。


``_validateScanPath(scanner, path)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  拒绝无法编码为 UTF-8 的文件路径。

输入
  ``scanner`` 和文件 ``path``。

返回
  有效时返回 ``True``，否则返回 ``False``。

副作用
  失败时将路径追加到 ``scanner.stats().errors``。


``processScanFile(scanner, path_or_direntry)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  运行完整的逐文件扫描流水线。

输入
  ``scanner`` 和路径字符串或 ``os.DirEntry``。

返回
  ``None``。

调用
  ``getScanTargetInfo``
  ``_validateScanPath``
  ``loadTrackForScan``
  ``resolveAlbumContext``
  ``buildTrackData``
  ``resolveTrackArtists``
  ``createOrUpdateTrack``
  ``recordTrackArtists``

行为说明
  只要路径字符串中的任意位置出现 ``".flac"``，它就会递增 ``scanner.stats().existing_tracks``。

  艺术家关系更新发生在 ``Track`` 行创建或更新之后。


scanner_func/scanner_persist.py
-------------------------------

模块角色
~~~~~~~~

选择主曲目艺术家，并持久化 ``Track`` 行本身。


``resolveTrackArtists(scanner, nfo_data, track_data, fallback_artists)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  尽可能从 NFO 曲目条目中选择逐曲目艺术家，否则使用回退艺术家。

输入
  ``scanner``、已解析的 ``nfo_data``、准备好的 ``track_data`` 和 ``fallback_artists``。

返回
  ``(track_artists, main_artist_row)``。

调用
  ``findArtist``。

当前实现说明
  当前代码会同时从 ``cdnum`` 读取 ``nfo_track_number`` 和 ``nfo_track_disc``，并以对调的方式与
  ``track_data["number"]`` 和 ``track_data["disc"]`` 进行比较。这会直接影响 NFO 中逐曲目艺术家是否能按预期匹配。


``createOrUpdateTrack(scanner, track, path, mtime, track_data, album, artist)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  创建新的 ``Track`` 行或更新已有行。

输入
  已存在的 ``track`` 或 ``None``、文件 ``path``、整数 ``mtime``、已准备好的 ``track_data`` 字典、已解析的 ``album`` 行以及已解析的主 ``artist`` 行。

返回
  更新后或新创建的 ``Track`` 行；发生 ``ValueError`` 时返回 ``None``。

调用
  ``findRootFolder``
  ``findFolder``
  ``Track.create``
  ``track.save()``

副作用
  创建时递增 ``scanner.stats().added.tracks``。


scanner_func/scanner_relations.py
---------------------------------

模块角色
~~~~~~~~

维护 ``AlbumArtist`` 和 ``TrackArtist`` 关系表。


``_normalize_artist_names(scanner, artists)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  清洗艺术家名称，并保证返回非空列表。

输入
  艺术家可迭代对象。

返回
  清洗后的艺术家名称列表，默认值为 ``["unknown"]``。

说明
  ``scanner`` 当前未使用。


``recordAlbumArtists(scanner, artists, album, main_artist=None)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  解析专辑艺术家、确保专辑行存在，并确保匹配的 ``AlbumArtist`` 行存在。

输入
  艺术家列表、专辑名称字符串，以及可选的 ``main_artist`` 覆盖值。

返回
  ``(relations, album_row, first_resolved_artist)``。

调用
  ``_normalize_artist_names``
  ``findArtist``
  ``Album.get_or_create``
  ``AlbumArtist.get_or_create``

行为说明
  该函数在数据库事务中运行。

  在出现 ``IntegrityError`` 时，它会重新加载或重新解析艺术家，然后重试关系创建。


``recordTrackArtists(scanner, artists, track)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  确保某个曲目的 ``TrackArtist`` 行存在。

输入
  艺术家列表和目标 ``Track`` 行。

返回
  ``(relations, first_resolved_artist)``。

调用
  ``_normalize_artist_names``
  ``findArtist``
  ``TrackArtist.get_or_create``

行为说明
  使用与 ``recordAlbumArtists`` 相同的 ``IntegrityError`` 恢复模式。


scanner_func/scanner_lookup.py
------------------------------

模块角色
~~~~~~~~

查找或创建数据库侧的 ``Artist``、``Album`` 和 ``Folder`` 上下文行。


``findAlbum(scanner, artist, album)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  在已解析艺术家之下解析专辑；如果缺失则创建。

输入
  艺术家名称和专辑名称。

返回
  ``Album`` 行。

调用
  ``findArtist`` 和 ``Album.create``。

副作用
  新建专辑时递增 ``scanner.stats().added.albums``。


``findArtist(scanner, artist)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  解析艺术家行；如果存在 ``real_artist`` 间接引用，则跟随它。

输入
  艺术家名称字符串。

返回
  ``Artist`` 行。

调用
  ``Artist.get`` 和 ``Artist.create``。

副作用
  创建时递增 ``scanner.stats().added.artists``。


``findRootFolder(path)``
~~~~~~~~~~~~~~~~~~~~~~~~

目的
  找出其路径为文件目录前缀的根文件夹行。

输入
  文件路径字符串。

返回
  根 ``Folder`` 行。

当前实现说明
  匹配方式是简单的 ``startswith`` 前缀匹配；当没有匹配到根文件夹时，该函数会抛出通用 ``Exception``。


``findFolder(path)``
~~~~~~~~~~~~~~~~~~~~

目的
  从文件路径向上查找或创建中间文件夹行，直到找到已存在的祖先为止。

输入
  文件路径字符串。

返回
  该文件父目录对应的叶子 ``Folder`` 行。

调用
  ``Folder.get``
  ``Folder.create``
  ``os.path.getmtime``

行为说明
  该函数假定某个祖先文件夹行已经存在，并以 ``assert folder is not None`` 结束。


scanner_func/scanner_nfo.py
---------------------------

模块角色
~~~~~~~~

读取 ``album.nfo``，并应用由 NFO 驱动的专辑和曲目修复。


``_splitArtists(value)``
~~~~~~~~~~~~~~~~~~~~~~~~

目的
  将逗号分隔的艺术家字符串拆分为列表。

输入
  字符串或假值。

返回
  艺术家字符串列表。


``readNfo(nfoPath)``
~~~~~~~~~~~~~~~~~~~~

目的
  解析 NFO 文件，并将类似艺术家的字段规范化为列表。

输入
  NFO 文件路径。

返回
  已解析的 NFO 字典；如果文件不存在，则返回 ``{}``。

调用
  ``NfoHandler.read``。

行为说明
  该函数同时支持嵌套的 ``album`` 布局和顶层布局。如果 ``album.track`` 是单个字典，它会将其转换为只包含一个元素的列表。


``_loadAlbumNfo(scanner, path)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  接受 NFO 文件路径或专辑目录，并从中加载专辑 NFO。

输入
  ``scanner`` 和目标路径。

返回
  ``(nfo_data_or_none, folder_path_or_none)``。

说明
  ``scanner`` 当前未使用。


``_loadAlbumFolderState(folderPath)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  加载文件夹行、其中的第一个曲目以及完整曲目列表。

输入
  文件夹路径字符串。

返回
  ``(folder_row, first_track, all_tracks)`` 或 ``(None, None, None)``。


``_renowAlbumMetadata(scanner, albumElement, nfoData, logger)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  应用来自 NFO 的专辑年份、主艺术家和专辑-艺术家关系。

输入
  ``scanner``、专辑行、已解析 NFO 字典和 logger。

返回
  ``None``。

调用
  ``findArtist``
  ``AlbumArtist.delete(...).execute()``
  ``recordAlbumArtists``
  ``albumElement.save()``

行为说明
  主艺术家来自 ``album.albumartist``，而关系刷新使用的是 ``album.artist``。


``_validateTrackNumbers(allTracks, logger)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  在执行逐曲目 NFO 艺术家修复之前，检查数据库中的曲目是否具有非空且不重复的 ``(disc, number)`` 对。

输入
  曲目列表和 logger。

返回
  ``True`` 或 ``False``。

当前实现说明
  当前重复检测并不一致，因为代码存储的是元组 ``(disc, number)``，但检查成员关系时只使用了 ``dbTrack.number``。


``_renowTrackArtists(scanner, albumElement, nfoData, logger)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  从 NFO 曲目条目重建逐曲目的艺术家分配。

输入
  ``scanner``、专辑行、NFO 字典和 logger。

返回
  ``None``。

调用
  ``Track.select().where(...)``
  ``TrackArtist.delete(...).execute()``
  ``recordTrackArtists``
  ``track.save()``

行为说明
  对于匹配到的曲目，主 ``track.artist`` 会被设置为专辑的主艺术家，而不是 NFO 中该曲目的第一个艺术家。


``renowAlbumByNfo(scanner, path, logger)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  公开的 NFO 驱动修复入口。

输入
  ``scanner``、文件或目录路径，以及 logger。

返回
  ``None``。

调用
  ``_loadAlbumNfo``
  ``_loadAlbumFolderState``
  ``_renowAlbumMetadata``
  ``_validateTrackNumbers``
  ``_renowTrackArtists``


scanner_func/scanner_positions.py
---------------------------------

模块角色
~~~~~~~~

在扫描完成后修复专辑艺术家和曲目艺术家的排序。


``_album_artist_exists_in_tracks(album, artist)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  检查某个专辑艺术家是否仍被该专辑中的任意曲目引用。

输入
  专辑行和艺术家行。

返回
  ``True`` 或 ``False``。


``_remove_invalid_album_artist_relations()``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  删除 ``position == 0`` 且已不再出现在任何曲目中的 ``AlbumArtist`` 行。

返回
  ``None``。


``_get_albums_needing_position_repair()``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  收集 ``AlbumArtist.position`` 仍为 ``0`` 的唯一专辑。

返回
  专辑行列表。


``_count_album_track_artists(album)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  统计某个专辑中 ``TrackArtist`` 行上的艺术家频次。

输入
  专辑行。

返回
  按计数降序排序的 ``[(artist, count), ...]`` 列表。


``_apply_album_artist_positions(album, sorted_artists)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  写入一致的专辑艺术家和曲目艺术家位置值。

输入
  专辑行和已排序的艺术家计数列表。

返回
  ``None``。

行为说明
  位置为 1 的艺术家会同时成为该专辑的 ``album.artist`` 和该专辑中每个曲目的主 ``artist``。


``decideAllPositions(scanner)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  位置修复的公开入口。

输入
  ``scanner``。

返回
  ``None``。

调用
  ``_remove_invalid_album_artist_relations``
  ``_get_albums_needing_position_repair``
  ``_count_album_track_artists``
  ``_apply_album_artist_positions``

说明
  ``scanner`` 当前未使用，但被保留以保持辅助函数接口一致。


scanner_func/scanner_records.py
-------------------------------

模块角色
~~~~~~~~

维护 ``Track`` 行，用于删除、移动以及哈希回填操作。


``removeFile(scanner, path)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  删除某个路径上的 ``Track`` 行。

输入
  ``scanner`` 和文件路径字符串。

返回
  ``None``。

副作用
  当行存在时，递增 ``scanner.stats().deleted.tracks``。

说明
  缺失的行会被静默忽略。


``moveFile(scanner, src_path, dst_path)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  将 ``Track`` 行更新到新路径，并调整根文件夹/文件夹归属。

输入
  ``scanner``、源路径和目标路径字符串。

返回
  ``None``。

调用
  ``Track.get``
  ``removeFile``
  ``findRootFolder``
  ``findFolder``
  ``track.save()``

行为说明
  当目标行已存在时，会先复用其 ``root_folder`` 和 ``folder``，然后再删除陈旧的目标行。


``renowTrackHash(logger)``
~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  为 ``content_hash`` 等于字面字符串 ``"NULL"`` 的曲目补全缺失的文件哈希。

输入
  logger 实例。

返回
  ``None``。

调用
  ``get_file_md5`` 和 ``track.save()``。


scanner_func/scanner_cover.py
-----------------------------

模块角色
~~~~~~~~

从本地文件和外部服务发现、创建或修复专辑封面记录。


``collectAlbumsMissingCover(scanner)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  收集当前不存在类型为 ``"album"`` 的 ``Image`` 行的专辑。

输入
  ``scanner``。

返回
  专辑行列表。

副作用
  填充 ``scanner.stats().lost_covers_albums``，并递增
  ``scanner.stats().lost_covers.albums``。


``findCover(scanner, dirpath)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  为该文件夹中第一个曲目所代表的专辑发现最佳本地文件夹封面。

输入
  ``scanner`` 和目录路径。

返回
  ``None``。

调用
  ``Folder.get``
  ``find_cover_in_folder``
  ``Image.get_or_create``

行为说明
  使用文件夹中的第一个曲目来推断专辑。


``addCover(path, logger)``
~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  处理某个可能成为专辑封面的特定图片文件。

输入
  文件路径和 logger。

返回
  ``None``。

调用
  ``Folder.get``
  ``Image.get_or_none``
  ``Image.create``
  ``CoverFile`` 评分

行为说明
  只有当新文件评分高于当前封面文件名时，才会发生替换。


``markAlbumCoverRestored(scanner, album)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  在封面被恢复后更新缺失封面统计。

输入
  ``scanner`` 和专辑行。

返回
  ``None``。


``repairAlbumCover(scanner, album, get_cover_interner=False, lfm=None, logger=None)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  按如下顺序修复单个专辑封面：

  * 本地文件夹图片文件，
  * 曲目内嵌艺术图，
  * MusicBrainz 图片 API，
  * Last.fm 图片 URL。

输入
  ``scanner``、专辑行、功能开关、Last.fm 客户端和 logger。

返回
  ``None``。

调用
  ``find_cover_in_folder``
  ``mediafile.MediaFile(track.path).art``
  ``download_image``
  ``Image.get_or_create``
  ``Image.create``
  ``markAlbumCoverRestored``

行为说明
  内嵌图片会被写入
  ``<tempdatafolder>/album/<album.name>.png``。


scanner_func/scanner_enrich.py
------------------------------

模块角色
~~~~~~~~

针对缺失的专辑年份、专辑封面和艺术家元数据执行扫描后补全。


``buildExternalMetadataClients(scanner)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  判断是否可以进行外部元数据修复，并在可用时构造 Last.fm 和 Spotify 客户端。

输入
  ``scanner``。

返回
  ``(user, enabled, lfm_client_or_none, spotify_client_or_none)``。

行为说明
  外部修复要求 root 用户、已关联的 Last.fm 状态，以及已配置的 Spotify ``client_id``。


``collectAlbumsMissingYear(scanner)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  收集缺失年份元数据的专辑，并将其代表性文件夹路径存入统计信息。

输入
  ``scanner``。

返回
  专辑行列表。


``repairAlbumYear(scanner, album, lfm=None, sp=None)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  按如下顺序修复单个专辑年份：

  * 第一个曲目的年份，
  * MusicBrainz 发行日期，
  * Last.fm wiki 或 published 元数据。

输入
  ``scanner``、专辑行、可选 Last.fm 客户端和可选 Spotify 客户端。

返回
  找到年份时返回 ``True``，否则返回 ``False``。

调用
  ``extract_year``
  ``search_musicbrainz_album``
  ``get_musicbrainz_album``
  ``lfm.get_albuminfo``
  ``album.save()``

当前实现说明
  ``sp`` 仅被用作真假值门控；函数体内部不会调用 Spotify。


``collectArtistsMissingInfo(scanner)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  收集其 ``artist_info_json`` 仍为空的艺术家。

输入
  ``scanner``。

返回
  艺术家行列表。

副作用
  更新缺失艺术家统计。


``repairArtistProfiles(scanner, lost_cover_artist, get_cover_interner=False, user=None, logger=None)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  下载艺术家简介元数据和图片，然后写入 ``info.json`` 并将其重新绑定到艺术家行。

输入
  ``scanner``、缺失的艺术家列表、功能开关、root 用户和 logger。

返回
  ``None``。

调用
  ``MySpotify``
  ``LastFm``
  ``lfm.get_artistinfo``
  ``lfm.get_lastfm_wiki``
  ``sp.get_artist_info``
  ``download_image``
  ``write_dict_to_json``
  ``artist.save()``

行为说明
  名称为 ``Various Artists`` 的艺术家会被跳过。

  名称长度小于 2 的艺术家会被跳过。


``repairMissingArtistImages(scanner, get_cover_interner=False, user=None, logger=None)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  重新下载现有 ``info.json`` 文件所引用但缺失的艺术家图片文件。

输入
  与 ``repairArtistProfiles`` 相同的门控输入。

返回
  ``None``。


``findLostInformation(scanner, logger=None)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  顶层扫描后元数据补全序列。

输入
  ``scanner`` 和可选 logger。

返回
  ``None``。

调用
  ``buildExternalMetadataClients``
  ``collectAlbumsMissingYear`` -> ``repairAlbumYear``
  ``collectAlbumsMissingCover`` -> ``repairAlbumCover``
  ``collectArtistsMissingInfo`` -> ``repairArtistProfiles``
  ``repairMissingArtistImages``


scanner_func/scanner_folder.py
------------------------------

模块角色
~~~~~~~~

遍历一个根文件夹，并在该遍历前后执行清理步骤。


``_scanFolderEntries(scanner, folder)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  遍历一个根文件夹下的文件系统，并扫描符合条件的文件。

输入
  ``scanner`` 和根文件夹行。

返回
  ``None``。

调用
  ``os.scandir``
  ``scanner.should_scan_extension``
  ``scanner.scan_file``
  ``scanner.report_progress``

行为说明
  隐藏项会被跳过。

  除非启用了 ``scanner.follow_symlinks``，否则符号链接会被跳过。


``_removeDeletedFolders(scanner, folder)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  删除其目录已不存在的数据库文件夹层级。

输入
  ``scanner`` 和根文件夹行。

返回
  ``None``。

副作用
  将已删除层级中的曲目数量累加到 ``scanner.stats().deleted.tracks``。


``_removeDeletedTracks(scanner, folder)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  删除文件已不存在或扩展名已不再符合扫描条件的曲目行。

输入
  ``scanner`` 和根文件夹行。

返回
  ``None``。

行为说明
  因此，扩展名过滤器变更即使在文件仍存在于磁盘上时，也可能删除数据库行。


``_refreshFolderCovers(scanner, folder)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  为根文件夹及其所有后代重新执行本地封面发现。

输入
  ``scanner`` 和根文件夹行。

返回
  ``None``。


``scanFolder(scanner, folder, logger)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  单个根文件夹扫描的完整包装器。

输入
  ``scanner``、根文件夹行和 logger。

返回
  ``None``。

调用
  ``scanner.handle_folder_start``
  ``_scanFolderEntries``
  ``_removeDeletedFolders``
  ``_removeDeletedTracks``
  ``_refreshFolderCovers``
  ``folder.save()``
  ``scanner.handle_folder_end``

行为说明
  只有在没有 stop 请求时，``folder.last_scan`` 才会被更新。


scanner_func/scanner_runtime.py
-------------------------------

模块角色
~~~~~~~~

在根文件夹入队之后，负责整个排队扫描生命周期。


``_scanQueuedFolders(scanner)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  清空已排队的根文件夹名称，并扫描匹配的根 ``Folder`` 行。

输入
  ``scanner``。

返回
  ``None``。

调用
  ``scanner.next_queued_folder()``
  ``Folder.get(name=folderName, root=True)``
  ``scanner.scan_folder(folder)``

行为说明
  队列项是文件夹名称，而不是路径。


``pruneLibrary(scanner)``
~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  在遍历之后删除已删除或为空的专辑、艺术家和文件夹。

输入
  ``scanner``。

返回
  ``None``。

调用
  ``Album.prune()``
  ``Artist.prune()``
  ``Folder.prune()``


``runScanner(scanner, logger)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

目的
  完整的排队扫描生命周期包装器。

输入
  ``scanner`` 和 logger。

返回
  ``None``。

调用
  ``open_connection(True)``
  ``_scanQueuedFolders``
  ``scanner.decideAllPositions()``
  ``pruneLibrary(scanner)``
  ``scanner.find_lost_information()``
  ``scanner.handle_done()``
  ``close_connection()``

行为说明
  位置修复发生在 prune 和补全之前。


执行摘要
--------

主扫描流程
~~~~~~~~~~

1. 调用方通过 ``Scanner.queue_folder()`` 将根文件夹名称加入队列。
2. ``Scanner.run()`` 委托给 ``runScanner``。
3. ``runScanner`` 打开数据库并清空队列。
4. 每个根文件夹都由 ``scanFolder`` 处理。
5. ``scanFolder`` 遍历文件，并将每个文件委托给 ``processScanFile``。
6. ``processScanFile`` 执行目标发现、标签加载、专辑上下文解析、曲目持久化以及曲目-艺术家关系写入。
7. 遍历完成后，``scanFolder`` 会删除已删除的文件夹和曲目，然后刷新本地封面行。
8. 所有文件夹完成后，``runScanner`` 会修复位置、清理陈旧媒体库行、执行元数据补全，并触发完成回调。

Watcher 风格维护流程
~~~~~~~~~~~~~~~~~~~~

* ``Scanner.remove_file`` -> ``removeFile``
* ``Scanner.move_file`` -> ``moveFile``
* ``Scanner.find_cover`` -> ``findCover``
* ``Scanner.add_cover`` -> ``addCover``
* ``Scanner.renow_album_by_nfo`` -> ``renowAlbumByNfo``
* ``renow_track_hash`` -> ``renowTrackHash``


当前审查说明
------------

以下是当前实现中会实质性影响行为审查的事实：

* ``resolveTrackArtists`` 当前会同时从 ``cdnum`` 读取 ``nfo_track_number`` 和
  ``nfo_track_disc``，并以对调的方式进行比较。
* ``_validateTrackNumbers`` 存储的是元组 ``(disc, number)``，但检查成员关系时只使用
  ``dbTrack.number``。
* ``processScanFile`` 是基于子串判断 ``".flac" in path.lower()`` 来递增 ``existing_tracks``，
  而不是严格的扩展名匹配。
* ``findRootFolder`` 使用简单的路径前缀匹配；当没有根文件夹匹配时，会抛出通用
  ``Exception``。
* ``ScanQueue`` 基于集合，因此队列处理顺序不是确定性的。
* ``repairAlbumYear`` 会同时以 ``lfm`` 和 ``sp`` 作为某些 Last.fm 逻辑的门控条件，
  尽管函数体内部并未使用 Spotify 客户端。

# This file is part of Supysonic.
# Supysonic is a Python implementation of the Subsonic server API.
#
# Copyright (C) 2013-2023 Alban 'spl0k' Féron
#
# Distributed under terms of the GNU AGPLv3 license.

from __future__ import annotations

import logging
import os
import os.path

from queue import Empty as QueueEmpty
from threading import Thread, Event
from typing import Callable, List, Optional, TYPE_CHECKING, Union

from .config import IniConfig

# Keep the high-level scan orchestration in this module and delegate
# file parsing, persistence, and metadata repair details to scanner_func.
from .scanner_func import (
    addCover,
    decideAllPositions,
    findCover,
    findLostInformation,
    moveFile,
    processScanFile,
    pruneLibrary,
    removeFile,
    renowAlbumByNfo,
    renowTrackHash,
    runScanner,
    ScanQueue,
    scanFolder,
    Stats,
)
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .db import Folder

ProgressCallback = Optional[Callable[[str, int], None]]
FolderCallback = Optional[Callable[["Folder"], None]]
DoneCallback = Optional[Callable[[], None]]


class Scanner(Thread):
    def __init__(
        self,
        force: bool = False,
        extensions: Optional[List[str]] = None,
        follow_symlinks: bool = False,
        progress: ProgressCallback = None,
        on_folder_start: FolderCallback = None,
        on_folder_end: FolderCallback = None,
        on_done: DoneCallback = None,
    ) -> None:
        super().__init__()

        if extensions is not None and not isinstance(extensions, list):
            raise TypeError("Invalid extensions type")

        self.__force = force
        self.__extensions = extensions
        self.__follow_symlinks = follow_symlinks

        self.__progress = progress
        self.__on_folder_start = on_folder_start
        self.__on_folder_end = on_folder_end
        self.__on_done = on_done

        self.__stopped = Event()
        self.__queue = ScanQueue()
        self.__stats = Stats()
        self.__config = IniConfig.from_common_locations()

    scanned = property(lambda self: self.__stats.scanned)
    force_scan = property(lambda self: self.__force)
    follow_symlinks = property(lambda self: self.__follow_symlinks)
    scan_config = property(lambda self: self.__config)
    stop_requested = property(lambda self: self.__stopped.is_set())

    def report_progress(self, folder_name: str, scanned: int) -> None:
        if self.__progress is None:
            return

        self.__progress(folder_name, scanned)

    def handle_folder_start(self, folder: Folder) -> None:
        if self.__on_folder_start is not None:
            self.__on_folder_start(folder)

    def handle_folder_end(self, folder: Folder) -> None:
        if self.__on_folder_end is not None:
            self.__on_folder_end(folder)

    def handle_done(self) -> None:
        if self.__on_done is not None:
            self.__on_done()

    def queue_folder(self, folder_name: str) -> None:
        if not isinstance(folder_name, str):
            raise TypeError("Expecting string, got " + str(type(folder_name)))

        self.__queue.put(folder_name)

    def next_queued_folder(self) -> Optional[str]:
        try:
            return self.__queue.get(False)
        except QueueEmpty:
            return None

    def run(self) -> None:
        runScanner(self, logger)

    def stop(self) -> None:
        self.__stopped.set()

    def scan_folder(self, folder: Folder) -> None:
        # Keep folder traversal in a helper so Scanner stays focused on orchestration.
        scanFolder(self, folder, logger)

    def prune(self) -> None:
        pruneLibrary(self)

    def should_scan_extension(self, path: str) -> bool:
        if not self.__extensions:
            return True
        return os.path.splitext(path)[1][1:].lower() in self.__extensions

    def scan_file(self, path_or_direntry: Union[str, os.DirEntry]) -> None:
        # Keep the public Scanner method stable while the per-file pipeline
        # lives in a dedicated helper module.
        processScanFile(self, path_or_direntry)

    def remove_file(self, path: str) -> None:
        removeFile(self, path)

    def move_file(self, src_path: str, dst_path: str) -> None:
        moveFile(self, src_path, dst_path)

    def find_cover(self, dirpath: str) -> None:
        findCover(self, dirpath)

    def add_cover(self, path: str) -> None:
        addCover(path, logger)

    def find_lost_information(self) -> None:
        # Post-scan enrichment is centralized in scanner_enrich so the
        # main scanner loop stays focused on traversal and persistence.
        findLostInformation(self, logger=logger)

    def decideAllPositions(self) -> None:
        decideAllPositions(self)

    def renow_album_by_nfo(self, path: str) -> None:
        renowAlbumByNfo(self, path, logger)

    def stats(self) -> Stats:
        return self.__stats


def renow_track_hash() -> None:
    renowTrackHash(logger)

"""Traverse one library folder and run cleanup steps around the scan."""

from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING

from ..db import Folder, Track
from ..logging_utils import format_log_event

if TYPE_CHECKING:
    from ..scanner import Scanner


def _scanFolderEntries(scanner: Scanner, folder: Folder) -> None:
    toScan = [folder.path]
    scanned = 0

    # Walk the filesystem first so changed media files are indexed before cleanup.
    while not scanner.stop_requested and toScan:
        path = toScan.pop()
        try:
            entries = list(os.scandir(path))
        except OSError:
            scanner.stats().errors.append(path)
            continue

        for entry in entries:
            try:
                if entry.name.startswith("."):
                    continue
                if entry.is_symlink() and not scanner.follow_symlinks:
                    continue
                if entry.is_dir():
                    toScan.append(entry.path)
                    continue
                if entry.is_file() and scanner.should_scan_extension(entry.path):
                    scanner.scan_file(entry)
                    scanner.stats().scanned += 1
                    scanned += 1
                    scanner.report_progress(folder.name, scanned)
            except OSError:
                scanner.stats().errors.append(entry.path)


def _removeDeletedFolders(scanner: Scanner, folder: Folder) -> None:
    folders = [folder]
    while not scanner.stop_requested and folders:
        currentFolder = folders.pop()
        if not currentFolder.root and not os.path.isdir(currentFolder.path):
            scanner.stats().deleted.tracks += currentFolder.delete_hierarchy()
            continue

        folders += currentFolder.children[:]


def _removeDeletedTracks(scanner: Scanner, folder: Folder) -> None:
    if scanner.stop_requested:
        return

    # Keep DB rows aligned with the files that still exist under this root folder.
    for track in Track.select().where(Track.root_folder == folder):
        if not os.path.exists(track.path) or not scanner.should_scan_extension(track.path):
            scanner.remove_file(track.path)


def _refreshFolderCovers(scanner: Scanner, folder: Folder) -> None:
    folders = [folder]
    while not scanner.stop_requested and folders:
        currentFolder = folders.pop()
        scanner.find_cover(currentFolder.path)
        folders += currentFolder.children[:]


def scanFolder(scanner: Scanner, folder: Folder, logger: logging.Logger) -> None:
    logger.info(format_log_event("scanner", "folder_start", folder=folder.name, path=folder.path))
    scanner.handle_folder_start(folder)

    _scanFolderEntries(scanner, folder)
    _removeDeletedFolders(scanner, folder)
    _removeDeletedTracks(scanner, folder)
    _refreshFolderCovers(scanner, folder)

    if not scanner.stop_requested:
        folder.last_scan = int(time.time())
        folder.save()

    logger.info(
        format_log_event(
            "scanner",
            "folder_end",
            folder=folder.name,
            stopped=scanner.stop_requested,
        )
    )
    scanner.handle_folder_end(folder)

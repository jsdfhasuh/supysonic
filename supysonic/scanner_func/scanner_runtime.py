"""Run the queued scanner lifecycle and library cleanup stages."""

from __future__ import annotations

import logging

from ..db import Album, Artist, Folder, close_connection, open_connection

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..scanner import Scanner

def _scanQueuedFolders(scanner: Scanner) -> None:
    while not scanner.stop_requested:
        folderName = scanner.next_queued_folder()
        if folderName is None:
            break

        try:
            folder = Folder.get(name=folderName, root=True)
        except Folder.DoesNotExist:
            continue

        scanner.scan_folder(folder)


def pruneLibrary(scanner: Scanner) -> None:
    if scanner.stop_requested:
        return

    scanner.stats().deleted.albums += Album.prune()
    scanner.stats().deleted.artists += Artist.prune()
    Folder.prune()


def runScanner(scanner: Scanner, logger: logging.Logger) -> None:
    opened = open_connection(True)
    try:
        _scanQueuedFolders(scanner)
        if scanner.stop_requested:
            return

        # Queue processing finishes first. The remaining steps depend on
        # having a complete view of the library state after traversal.
        scanner.decideAllPositions()
        pruneLibrary(scanner)
        logger.info("begin to find all covers")
        scanner.find_lost_information()
        scanner.handle_done()
    finally:
        if opened:
            close_connection()

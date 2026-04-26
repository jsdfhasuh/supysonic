"""Resolve scanner-side Artist, Album, and Folder rows from file inputs."""

from __future__ import annotations

import os

from datetime import datetime
from typing import Any, Dict, List, TYPE_CHECKING

from ..db import Album, Artist, Folder

if TYPE_CHECKING:
    from ..scanner import Scanner


def findAlbum(scanner: Scanner, artist: str, album: str) -> Album:
    artistRow = findArtist(scanner, artist)
    albumRow = artistRow.albums.where(Album.name == album).first()
    if albumRow:
        return albumRow

    scanner.stats().added.albums += 1
    return Album.create(name=album, artist=artistRow)


def findArtist(scanner: Scanner, artist: str) -> Artist:
    try:
        artistRow = Artist.get(name=artist)
        if artistRow.real_artist:
            return artistRow.real_artist
        return artistRow
    except Artist.DoesNotExist:
        scanner.stats().added.artists += 1
        return Artist.create(name=artist)


def findRootFolder(path: str) -> Folder:
    currentPath = os.path.abspath(os.path.dirname(path))
    matchedFolder = None
    matchedPathLength = -1
    for folder in Folder.select().where(Folder.root):
        folderPath = os.path.abspath(folder.path)
        try:
            if os.path.commonpath([currentPath, folderPath]) != folderPath:
                continue
        except ValueError:
            continue

        if len(folderPath) > matchedPathLength:
            matchedFolder = folder
            matchedPathLength = len(folderPath)

    if matchedFolder is not None:
        return matchedFolder

    raise Exception(
        "Couldn't find the root folder for '{}'.\nDon't scan files that aren't located in a defined music folder".format(
            currentPath
        )
    )


def findFolder(path: str) -> Folder:
    children: List[Dict[str, Any]] = []
    drive, _ = os.path.splitdrive(path)
    currentPath = os.path.dirname(path)
    folder = None

    while currentPath not in (drive, "/"):
        try:
            folder = Folder.get(path=currentPath)
            break
        except Folder.DoesNotExist:
            pass

        created = datetime.fromtimestamp(os.path.getmtime(currentPath))
        children.append(
            {
                "root": False,
                "name": os.path.basename(currentPath),
                "path": currentPath,
                "created": created,
            }
        )
        currentPath = os.path.dirname(currentPath)

    assert folder is not None
    while children:
        folder = Folder.create(parent=folder, **children.pop())

    return folder

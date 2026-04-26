"""Define scanner runtime state containers and queue behavior."""

from __future__ import annotations

from queue import Queue
from typing import Optional


class StatsDetails:
    def __init__(self) -> None:
        self.artists = 0
        self.albums = 0
        self.tracks = 0


class Stats:
    def __init__(self) -> None:
        self.scanned = 0
        self.existing_tracks = 0
        self.added = StatsDetails()
        self.deleted = StatsDetails()
        self.errors = []
        self.lost_covers = StatsDetails()
        self.lost_covers_albums = {}
        self.lost_covers_artists = []
        self.lost_year_albums = {}


class ScanQueue(Queue):
    def _init(self, maxsize: int) -> None:
        self.queue = set()
        self.__last_got: Optional[str] = None

    def _put(self, item: str) -> None:
        if self.__last_got != item:
            self.queue.add(item)

    def _get(self) -> str:
        self.__last_got = self.queue.pop()
        return self.__last_got

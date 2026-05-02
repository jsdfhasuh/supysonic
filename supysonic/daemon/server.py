# This file is part of Supysonic.
# Supysonic is a Python implementation of the Subsonic server API.
#
# Copyright (C) 2019-2023 Alban 'spl0k' Féron
#
# Distributed under terms of the GNU AGPLv3 license.

import logging
import time

from multiprocessing.connection import Listener, Client
from threading import Thread, Event

from .client import DaemonCommand
from ..db import Folder, open_connection, close_connection
from ..jukebox import Jukebox
from ..logging_utils import format_log_event
from ..recommend import getRecommendationDay, refreshDailyRecommendPlaylists
from ..scanner import Scanner
from ..utils import get_secret_key
from ..watcher import SupysonicWatcher

__all__ = ["Daemon"]

logger = logging.getLogger(__name__)


class Daemon:
    def __init__(self, config):
        self.__config = config
        self.__listener = None
        self.__watcher = None
        self.__scanner = None
        self.__jukebox = None
        self.__recommendRefreshThread = None
        self.__lastRecommendRefreshDay = None
        self.__stopped = Event()

    watcher = property(lambda self: self.__watcher)
    scanner = property(lambda self: self.__scanner)
    jukebox = property(lambda self: self.__jukebox)

    def __handle_connection(self, connection):
        cmd = connection.recv()
        logger.debug("Received %s", cmd)
        if cmd is None:
            pass
        elif isinstance(cmd, DaemonCommand):
            cmd.apply(connection, self)
        else:
            logger.warning(
                format_log_event(
                    "daemon",
                    "unknown_command",
                    command_type=type(cmd).__name__,
                )
            )

    def run(self):
        self.__listener = Listener(
            address=self.__config.DAEMON["socket"], authkey=get_secret_key("daemon_key")
        )
        logger.info(format_log_event("daemon", "listening", socket=self.__listener.address))

        if self.__config.DAEMON["run_watcher"]:
            self.__watcher = SupysonicWatcher(self.__config)
            self.__watcher.start()
            logger.info(format_log_event("daemon", "watcher_started"))

        if self.__config.DAEMON["jukebox_command"]:
            self.__jukebox = Jukebox(self.__config.DAEMON["jukebox_command"])

        close_connection()

        Thread(target=self.__listen).start()
        if self.__config.DAEMON.get("recommend_daily_refresh", True):
            self.__recommendRefreshThread = Thread(
                target=self.__run_recommend_refresh_loop,
                daemon=True,
            )
            self.__recommendRefreshThread.start()
            logger.info(
                format_log_event(
                    "daemon",
                    "recommend_refresh_scheduler_started",
                    interval=self.__get_recommend_refresh_interval(),
                )
            )
        while not self.__stopped.is_set():
            time.sleep(1)
            
    

    def __listen(self):
        while not self.__stopped.is_set():
            conn = self.__listener.accept()
            self.__handle_connection(conn)

        self.__listener.close()

    def __get_recommend_refresh_interval(self):
        return max(60, int(self.__config.DAEMON.get("recommend_refresh_interval", 300)))

    def __get_recommend_playlist_size(self):
        return max(1, int(self.__config.DAEMON.get("recommend_playlist_size", 50)))

    def __refresh_recommend_playlists_if_needed(self, current_day=None):
        recommendationDay = getRecommendationDay() if current_day is None else current_day
        if recommendationDay == self.__lastRecommendRefreshDay:
            return False

        opened = False
        try:
            opened = open_connection(True)
            logger.info(
                format_log_event(
                    "daemon",
                    "recommend_refresh_started",
                    day=recommendationDay,
                )
            )
            createdCount = refreshDailyRecommendPlaylists(
                num_songs=self.__get_recommend_playlist_size(),
                day=recommendationDay,
            )
            self.__lastRecommendRefreshDay = recommendationDay
            logger.info(
                format_log_event(
                    "daemon",
                    "recommend_refresh_completed",
                    day=recommendationDay,
                    created=createdCount,
                )
            )
            return True
        except Exception as exc:
            logger.exception(
                format_log_event(
                    "daemon",
                    "recommend_refresh_failed",
                    day=recommendationDay,
                    error_type=exc.__class__.__name__,
                )
            )
            return False
        finally:
            if opened:
                close_connection()

    def __run_recommend_refresh_loop(self):
        interval = self.__get_recommend_refresh_interval()
        while not self.__stopped.is_set():
            self.__refresh_recommend_playlists_if_needed()
            self.__stopped.wait(interval)

    def start_scan(self, folders=[], force=False):
        logger.info(
            format_log_event(
                "daemon",
                "scan_requested",
                folders=len(folders) if folders else "all",
                force=force,
            )
        )
        if not folders:
            open_connection()
            folders = [
                t[0] for t in Folder.select(Folder.name).where(Folder.root).tuples()
            ]
            close_connection()

        if self.__scanner is not None and self.__scanner.is_alive():
            for f in folders:
                self.__scanner.queue_folder(f)
            logger.info(
                format_log_event(
                    "daemon",
                    "scan_queued",
                    folders=len(folders),
                    force=force,
                    reason="scanner_already_running",
                )
            )
            return

        extensions = self.__config.BASE["scanner_extensions"]
        if extensions:
            extensions = extensions.split(" ")

        self.__scanner = Scanner(
            force=force,
            extensions=extensions,
            follow_symlinks=self.__config.BASE["follow_symlinks"],
            on_folder_start=self.__unwatch,
            on_folder_end=self.__watch,
        )
        for f in folders:
            self.__scanner.queue_folder(f)

        self.__scanner.start()
        logger.info(
            format_log_event(
                "daemon",
                "scan_started",
                folders=len(folders),
                force=force,
            )
        )

    def __watch(self, folder):
        if self.__watcher is not None:
            self.__watcher.add_folder(folder.path)

    def __unwatch(self, folder):
        if self.__watcher is not None:
            self.__watcher.remove_folder(folder.path)

    def terminate(self):
        with Client(self.__listener.address, authkey=self.__listener._authkey) as c:
            self.__stopped.set()
            c.send(None)

        if self.__scanner is not None:
            self.__scanner.stop()
            self.__scanner.join()
        if self.__watcher is not None:
            self.__watcher.stop()
        if self.__recommendRefreshThread is not None:
            self.__recommendRefreshThread.join()
        if self.__jukebox is not None:
            self.__jukebox.terminate()

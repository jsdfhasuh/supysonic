# This file is part of Supysonic.
# Supysonic is a Python implementation of the Subsonic server API.
#
# Copyright (C) 2014-2023 Alban 'spl0k' Féron
#
# Distributed under terms of the GNU AGPLv3 license.

import logging

from logging.handlers import TimedRotatingFileHandler
from signal import signal, SIGTERM, SIGINT

from .client import DaemonClient
from .server import Daemon

from ..config import IniConfig
from ..db import init_database, release_database
import os

__all__ = ["Daemon", "DaemonClient"]

logger = logging.getLogger("supysonic")

daemon = None


def setup_logging(config):
    # 始终添加控制台日志处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(console_handler)

    # 如果配置了日志文件，也添加文件日志处理器
    if config["log_file"]:
        if config["log_rotate"]:
            os.makedirs(os.path.dirname(config["log_file"]), exist_ok=True)
            file_handler = TimedRotatingFileHandler(config["log_file"], when="midnight")
        else:
            file_handler = logging.FileHandler(config["log_file"])
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        logger.addHandler(file_handler)

    # 设置日志级别
    if "log_level" in config:
        level = getattr(logging, config["log_level"].upper(), logging.NOTSET)
        logger.setLevel(level)


def __terminate(signum, frame):
    global daemon

    logger.debug("Got signal %i. Stopping...", signum)
    daemon.terminate()
    release_database()


def main():
    global daemon

    config = IniConfig.from_common_locations()
    setup_logging(config.DAEMON)

    signal(SIGTERM, __terminate)
    signal(SIGINT, __terminate)

    init_database(config.BASE["database_uri"])
    daemon = Daemon(config)
    daemon.run()

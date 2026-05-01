# This file is part of Supysonic.
# Supysonic is a Python implementation of the Subsonic server API.
#
# Copyright (C) 2014-2023 Alban 'spl0k' Féron
#
# Distributed under terms of the GNU AGPLv3 license.

import logging
from signal import signal, SIGTERM, SIGINT

from .client import DaemonClient
from .server import Daemon

from ..config import IniConfig
from ..db import init_database, release_database
from ..logging_utils import format_log_event
from ..logging_manager import configure_daemon_logging

__all__ = ["Daemon", "DaemonClient"]

logger = logging.getLogger("supysonic")

daemon = None


def setup_logging(config):
    configure_daemon_logging(config, logger_name=logger.name)


def __terminate(signum, frame):
    global daemon

    logger.info(format_log_event("daemon", "stop", signal=signum))
    daemon.terminate()
    release_database()


def main():
    global daemon

    config = IniConfig.from_common_locations()
    setup_logging(config.DAEMON)
    logger.info(
        format_log_event(
            "daemon",
            "start",
            socket=config.DAEMON["socket"],
            watcher=config.DAEMON["run_watcher"],
            log_level=config.DAEMON.get("log_level", "-"),
        )
    )

    signal(SIGTERM, __terminate)
    signal(SIGINT, __terminate)

    init_database(config.BASE["database_uri"])
    daemon = Daemon(config)
    try:
        daemon.run()
    except Exception as exc:
        logger.exception(
            format_log_event("daemon", "crash", error_type=exc.__class__.__name__)
        )
        raise

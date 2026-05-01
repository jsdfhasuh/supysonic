# This file is part of Supysonic.
# Supysonic is a Python implementation of the Subsonic server API.
#
# Copyright (C) 2020 Alban 'spl0k' Féron
#               2020 Vincent Ducamps
#
# Distributed under terms of the GNU AGPLv3 license.

import logging

from flask import request
from flask import current_app

from ..daemon.client import DaemonClient
from ..daemon.exceptions import DaemonUnavailableError

from . import api_routing, log_api_event
from .user import admin_only
from .exceptions import ServerError
from ..db import Folder, Artist, Album, Track


@api_routing("/startScan")
@admin_only
def startScan():
    try:
        daemonclient = DaemonClient(current_app.config["DAEMON"]["socket"])
        daemonclient.scan()
        scanned = daemonclient.get_scanning_progress()
    except DaemonUnavailableError as e:
        log_api_event(
            logging.WARNING,
            "scan_request_failed",
            result="failed",
            reason="daemon_unavailable",
        )
        raise ServerError(str(e))
    log_api_event(
        logging.INFO,
        "scan_requested",
        result="queued",
        scanning=scanned is not None,
        count=scanned or 0,
    )
    return request.formatter(
        "scanStatus",
        {
            "scanning": scanned is not None,
            "count": scanned or 0,
        },
    )


@api_routing("/getScanStatus")
@admin_only
def getScanStatus():
    if request.values['c'] == 'Stream Music':
        return request.formatter(
            "scanStatus",
            {
                "scanning": False,
                "count": Track.select().count(),
            },
        )    

    try:
        scanned = DaemonClient(
            current_app.config["DAEMON"]["socket"]
        ).get_scanning_progress()
    except DaemonUnavailableError as e:
        log_api_event(
            logging.WARNING,
            "scan_status_failed",
            result="failed",
            reason="daemon_unavailable",
        )
        raise ServerError(str(e))
    return request.formatter(
        "scanStatus",
        {
            "scanning": scanned is not None,
            "count": scanned or 0,
        },
    )

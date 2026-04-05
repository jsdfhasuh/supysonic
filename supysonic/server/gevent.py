# This file is part of Supysonic.
# Supysonic is a Python implementation of the Subsonic server API.
#
# Copyright (C) 2021-2023 Alban 'spl0k' Féron
#
# Distributed under terms of the GNU AGPLv3 license.

import os
import os.path
import sys

from datetime import datetime

from gevent import socket
from gevent.pywsgi import WSGIServer
from geventwebsocket.handler import WebSocketHandler

from ._base import BaseServer


class FlushingStream:
    def __init__(self, stream):
        self._stream = stream

    def write(self, data):
        self._stream.write(data)
        self._stream.flush()

    def flush(self):
        self._stream.flush()


class EmosonicWebSocketHandler(WebSocketHandler):
    def format_request(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = (self._orig_status or self.status or "000").split()[0]
        length = self.response_length or "-"
        if self.time_finish:
            duration = f"{(self.time_finish - self.time_start):.6f}s"
        else:
            duration = "-"

        client_address = (
            self.client_address[0]
            if isinstance(self.client_address, tuple)
            else self.client_address
        ) or "-"
        method = self.command or "-"
        path = self.path or "-"
        if path.startswith("/emo/ws"):
            category = "SOCKET"
        elif path.startswith("/rest/stream"):
            category = "STREAM"
        elif path.startswith("/rest/"):
            category = "REST"
        else:
            category = "HTTP"
        return (
            f"[{now}] [ACCESS:{category}] {client_address} {method} {path} "
            f"status={status} bytes={length} duration={duration}"
        )

    def log_request(self):
        self.server.log.write(self.format_request() + "\n")


class GeventServer(BaseServer):
    def _build_kwargs(self):
        rv = {
            "application": self._load_app(),
            "handler_class": EmosonicWebSocketHandler,
            "log": FlushingStream(sys.stdout),
            "error_log": FlushingStream(sys.stderr),
        }

        if self._socket is not None:
            if os.path.exists(self._socket):
                os.remove(self._socket)

            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            listener.bind(self._socket)
            listener.listen()

            rv["listener"] = listener
        else:
            rv["listener"] = (self._host, self._port)

        return rv

    def _run(self, **kwargs):
        return WSGIServer(**kwargs).serve_forever()


server = GeventServer

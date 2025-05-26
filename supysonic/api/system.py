#
# This file is part of Supysonic.
# Supysonic is a Python implementation of the Subsonic server API.
#
# Copyright (C) 2013-2018 Alban 'spl0k' Féron
#
# Distributed under terms of the GNU AGPLv3 license.

from flask import request

from . import api_routing


@api_routing("/ping")
def ping():
    # 返回空内容但有正确的响应包装
    return request.formatter("connect_status", {"status": "OK"})  # 或者 return request.formatter.respond()


@api_routing("/getLicense")
def license():
    return request.formatter("license", {"valid": True})

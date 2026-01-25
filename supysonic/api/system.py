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


@api_routing("/getOpenSubsonicExtensions")
def open_subsonic_extensions():
    pass
    response_data = {}
    response_data["subsonic-response"] = {}
    response_data["subsonic-response"]["status"] = "ok"
    response_data["subsonic-response"]["version"] = "1.16.1"
    response_data["subsonic-response"]["type"] = "AwesomeServerName"
    response_data["subsonic-response"]["serverVersion"] = "0.1.3 (tag)"
    response_data["subsonic-response"]["openSubsonic"] = True
    response_data["subsonic-response"]["openSubsonicExtensions"] = [
        {
            "name": "template",
            "versions": [1, 2],
        },
        {           "name": "transcodeOffset",           
            "versions": [1],      
        },
    ]
    return response_data
        




    """{
    "subsonic-response": {
        "status": "ok",
        "version": "1.16.1",
        "type": "AwesomeServerName",
        "serverVersion": "0.1.3 (tag)",
        "openSubsonic": true,
        "openSubsonicExtensions": [
            {
                "name": "template",
                "versions": [
                    1,
                    2
                ]
            },
            {
                "name": "transcodeOffset",
                "versions": [
                    1
                ]
            }
        ]
    }
}
    """
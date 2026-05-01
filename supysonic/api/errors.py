# This file is part of Supysonic.
# Supysonic is a Python implementation of the Subsonic server API.
#
# Copyright (C) 2018-2022 Alban 'spl0k' Féron
#
# Distributed under terms of the GNU AGPLv3 license.

import logging

from flask import request
from peewee import DoesNotExist
from werkzeug.exceptions import BadRequestKeyError

from . import api, log_api_event
from .exceptions import GenericError, MissingParameter, NotFound, ServerError


@api.errorhandler(ValueError)
def value_error(e):
    log_api_event(logging.WARNING, "bad_request", reason=e.__class__.__name__)
    return GenericError("{0.__class__.__name__}: {0}".format(e))


@api.errorhandler(BadRequestKeyError)
def key_error(e):
    param = str(e.args[0]).strip("'") if e.args else "-"
    log_api_event(logging.WARNING, "bad_request", param=param, reason="missing_parameter")
    return MissingParameter()


@api.errorhandler(DoesNotExist)
def object_not_found(e):
    entity_name = e.__class__.__name__[: -len("DoesNotExist")]
    log_api_event(logging.WARNING, "entity_not_found", entity=entity_name)
    return NotFound(entity_name)


@api.errorhandler(500)
def generic_error(e):  # pragma: nocover
    log_api_event(logging.ERROR, "server_error", error_type=e.__class__.__name__)
    return ServerError("{0.__class__.__name__}: {0}".format(e))


# @api.errorhandler(404)
@api.route("/<path:invalid>", methods=["GET", "POST"])  # blueprint 404 workaround
def not_found(*args, **kwargs):
    log_api_event(logging.WARNING, "unknown_method", route=request.path)
    return GenericError("Unknown method"), 404

from . import api_routing
from .exceptions import GenericError
from flask import request

Version = "1.0.0"

@api_routing('/getVersion')
def get_version():
    return request.formatter("version", Version)
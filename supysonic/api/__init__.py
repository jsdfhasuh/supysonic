# This file is part of Supysonic.
# Supysonic is a Python implementation of the Subsonic server API.
#
# Copyright (C) 2013-2023 Alban 'spl0k' Féron
#
# Distributed under terms of the GNU AGPLv3 license.

API_VERSION = "1.12.0"

import binascii
import logging
import uuid
from flask import request
from flask import Blueprint
from flask import session
from peewee import IntegrityError

from ..db import ClientPrefs, Folder
from ..managers.user import UserManager

from .exceptions import GenericError, Unauthorized, NotFound
from .formatters import JSONFormatter, JSONPFormatter, XMLFormatter

api = Blueprint("api", __name__)
logger = logging.getLogger(__name__)


def api_routing(endpoint):
    def decorator(func):
        viewendpoint = f"{endpoint}.view"
        api.add_url_rule(endpoint, view_func=func, methods=["GET", "POST"])
        api.add_url_rule(viewendpoint, view_func=func, methods=["GET", "POST"])
        return func

    return decorator


@api.before_request
def set_formatter():
    """Return a function to create the response."""
    f, callback = map(request.values.get, ("f", "callback"))
    if f == "jsonp":
        request.formatter = JSONPFormatter(callback)
    elif f == "json":
        request.formatter = JSONFormatter()
    else:
        request.formatter = XMLFormatter()


def decode_password(password):
    if not password.startswith("enc:"):
        return password

    try:
        return binascii.unhexlify(password[4:].encode("utf-8")).decode("utf-8")
    except ValueError:
        return password


@api.before_request
def authorize():
    # 跳过不需要身份验证的端点
    # 尝试 HTTP 基本认证
    if request.authorization:
        username = request.authorization.username
        user = UserManager.try_auth(username, request.authorization.password)
        if user is not None:
            request.user = user
            return
        logger.warn("Failed login attempt for '%s'", username)
        logger.error(
            "Failed login attempt for user %s (IP: %s)", username, request.remote_addr
        )
        raise Unauthorized()
    
    # 必需参数检查
    
    if 'u' in request.values:
        username = request.values['u']
    elif session.get("userid"):
        try:
            user = UserManager.get(session.get("userid"))
            request.user = user
            return
        except (ValueError, User.DoesNotExist):
            session.clear()
            raise Unauthorized("Please login")
    
    # 方法 1: 明文密码
    if 'p' in request.values:
        password = request.values['p']
        if password.startswith('enc:'):
            # 处理编码密码（hex编码）
            try:
                password = binascii.unhexlify(password[4:]).decode('utf-8')
            except:
                raise Unauthorized("Invalid encoded password")
        
        user = UserManager.try_auth(username, password)
    
    # 方法 2: 散列密码
    elif 't' in request.values and 's' in request.values:
        token = request.values['t']  # md5(密码+盐)
        salt = request.values['s']   # 随机盐
        
        # 从数据库获取用户信息
        try:
            from ..db import User
            stored_user = User.get(User.name == username)
            
            # 生成预期的散列值
            import hashlib
            expected_token = hashlib.md5((stored_user.password + salt).encode('utf-8')).hexdigest()
            
            # 比较令牌
            if token.lower() == expected_token.lower():
                user = stored_user
            else:
                user = None
        except:
            user = None
    else:
        raise Unauthorized("Missing authentication parameters")
    
    # 检查认证结果
    if user is None:
        logger.warn("Failed login attempt for '%s'", username)
        raise Unauthorized("Wrong username or password")
    request.user = user


@api.before_request
def get_client_prefs():
    client = request.values["c"]
    try:
        request.client = ClientPrefs[request.user, client]
    except ClientPrefs.DoesNotExist:
        try:
            request.client = ClientPrefs.create(user=request.user, client_name=client)
        except IntegrityError:
            # We might have hit a race condition here, another request already created
            # the ClientPrefs. Issue #220
            request.client = ClientPrefs[request.user, client]


def get_entity(cls, param="id"):
    eid = request.values[param]
    if cls == Folder:
        eid = int(eid)
    else:
        eid = uuid.UUID(eid)
    return cls[eid]

def get_entity_by_name(cls, param):
    name = request.values[param]
    return cls.get(name=name) or cls.select().where(cls.name == name).first()

def get_entity_id(cls, eid):
    """Return the entity ID as its proper type."""
    if cls == Folder:
        if isinstance(eid, uuid.UUID):
            raise GenericError("Invalid ID")
        try:
            return int(eid)
        except ValueError as e:
            raise GenericError("Invalid ID") from e
    try:
        return uuid.UUID(eid)
    except (AttributeError, ValueError) as e:
        raise GenericError("Invalid ID") from e


def get_root_folder(id):
    if id is None:
        return None

    try:
        fid = int(id)
    except ValueError as e:
        raise ValueError("Invalid folder ID") from e

    try:
        return Folder.get(id=fid, root=True)
    except Folder.DoesNotExist as e:
        raise NotFound("Folder") from e


from .errors import *

from .system import *
from .browse import *
from .user import *
from .albums_songs import *
from .media import *
from .annotation import *
from .chat import *
from .search import *
from .playlists import *
from .jukebox import *
from .radio import *
from .unsupported import *
from .scan import *

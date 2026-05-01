import logging
import os
import time
import uuid

from urllib.parse import unquote_plus

from logging.handlers import TimedRotatingFileHandler

from flask import g, request

from .logging_utils import SENSITIVE_FIELD_NAMES, format_log_event


LOG_FILE_NAMES = {
  "summary": "supysonic.log",
  "debug": "web.debug.log",
  "access": "access.log",
  "task": "task.log",
  "emo": "emo.log",
  "metadata": "metadata.log",
  "scanner": "scanner.log",
  "api": "api.log",
}

DAEMON_LOG_FILE_NAMES = {
  "summary": "supysonic.log",
  "daemon": "daemon.log",
  "watcher": "watcher.log",
  "scanner": "scanner.log",
}


class _LoggerPrefixFilter(logging.Filter):
  def __init__(self, prefixes=None, exact_names=None):
    super().__init__()
    self.prefixes = tuple(prefixes or ())
    self.exact_names = tuple(exact_names or ())

  def filter(self, record):
    if record.name in self.exact_names:
      return True
    return any(record.name == prefix or record.name.startswith(prefix + ".") for prefix in self.prefixes)


class _MinLevelFilter(logging.Filter):
  def __init__(self, level):
    super().__init__()
    self.level = level

  def filter(self, record):
    return record.levelno >= self.level


def build_web_log_paths(log_dir):
  return {name: os.path.join(log_dir, filename) for name, filename in LOG_FILE_NAMES.items()}


def build_web_logging_config(webapp_config):
  log_dir = webapp_config.get("log_dir")
  if not log_dir and webapp_config.get("log_file"):
    log_dir = os.path.dirname(webapp_config["log_file"]) or "."
  return {
    "log_dir": log_dir,
    "log_rotate": webapp_config.get("log_rotate", True),
    "log_level": webapp_config.get("log_level", "WARNING"),
    "log_backup_count": webapp_config.get("log_backup_count", 7),
  }


def build_daemon_log_paths(log_dir):
  return {name: os.path.join(log_dir, filename) for name, filename in DAEMON_LOG_FILE_NAMES.items()}


def _close_managed_handlers(logger):
  remaining_handlers = []
  for handler in logger.handlers:
    if getattr(handler, "_supysonic_managed", False):
      handler.close()
      continue
    remaining_handlers.append(handler)
  logger.handlers = remaining_handlers


def _build_file_handler(log_path, log_rotate, log_backup_count, prefixes=None, exact_names=None, min_level=None):
  if log_rotate:
    handler = TimedRotatingFileHandler(log_path, when="midnight", backupCount=log_backup_count)
  else:
    handler = logging.FileHandler(log_path)
  handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
  if prefixes or exact_names:
    handler.addFilter(_LoggerPrefixFilter(prefixes=prefixes, exact_names=exact_names))
  if min_level is not None:
    handler.addFilter(_MinLevelFilter(min_level))
  handler._supysonic_managed = True
  return handler


def _build_route_prefixes(logger_name):
  return {
    "access": (f"{logger_name}.access",),
    "task": (f"{logger_name}.TaskManger",),
    "emo": (f"{logger_name}.emo",),
    "metadata": (f"{logger_name}.frontend.metadata",),
    "scanner": (
      f"{logger_name}.scanner",
      f"{logger_name}.scanner_func",
      f"{logger_name}.watcher",
    ),
    "api": (f"{logger_name}.api",),
  }


def _build_daemon_route_prefixes(logger_name):
  return {
    "daemon": {
      "prefixes": (f"{logger_name}.daemon",),
      "exact_names": (logger_name,),
    },
    "watcher": {
      "prefixes": (f"{logger_name}.watcher",),
      "exact_names": (),
    },
    "scanner": {
      "prefixes": (
        f"{logger_name}.scanner",
        f"{logger_name}.scanner_func",
      ),
      "exact_names": (),
    },
  }


def _get_debug_log_file(log_path):
  root, ext = os.path.splitext(log_path)
  if ext:
    return f"{root}.debug{ext}"
  return f"{log_path}.debug"


def _set_logger_level(logger, log_level):
  if log_level:
    logger.setLevel(getattr(logging, str(log_level).upper(), logging.NOTSET))


def _configure_console_handler(logger):
  console_handler = logging.StreamHandler()
  console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
  console_handler._supysonic_managed = True
  logger.addHandler(console_handler)


def _configure_legacy_daemon_files(logger, config):
  log_file = config.get("log_file")
  if not log_file:
    return

  log_dir = os.path.dirname(log_file)
  if log_dir:
    os.makedirs(log_dir, exist_ok=True)

  main_handler = _build_file_handler(
    log_file,
    config.get("log_rotate", True),
    config.get("log_backup_count", 7),
    min_level=logging.INFO,
  )
  logger.addHandler(main_handler)

  if str(config.get("log_level", "")).upper() == "DEBUG":
    logger.addHandler(
      _build_file_handler(
        _get_debug_log_file(log_file),
        config.get("log_rotate", True),
        config.get("log_backup_count", 7),
      )
    )


def _configure_category_handlers(logger, log_paths, route_prefixes, config):
  logger.addHandler(
      _build_file_handler(
        log_paths["summary"],
        config.get("log_rotate", True),
        config.get("log_backup_count", 7),
        min_level=logging.INFO,
      )
    )
  for category, route in route_prefixes.items():
    logger.addHandler(
      _build_file_handler(
        log_paths[category],
        config.get("log_rotate", True),
        config.get("log_backup_count", 7),
        prefixes=route.get("prefixes"),
        exact_names=route.get("exact_names"),
        min_level=logging.INFO,
      )
    )


def _get_access_type(request_path):
  if request_path.startswith("/rest/"):
    return "REST"
  if request_path.startswith("/emo/ws"):
    return "SOCKET"
  return "WEB"


def _get_request_target():
  query_string = request.query_string.decode("utf-8") if request.query_string else ""
  if not query_string:
    return request.path
  return f"{request.path}?{query_string}"


def _sanitize_query_string(query_string):
  if not query_string:
    return "-"

  sanitized_parts = []
  for part in query_string.split("&"):
    if "=" not in part:
      sanitized_parts.append(part)
      continue

    key, value = part.split("=", 1)
    normalized_key = unquote_plus(key).strip().lower()
    if normalized_key in SENSITIVE_FIELD_NAMES:
      sanitized_parts.append(f"{key}=***")
      continue

    sanitized_parts.append(part)

  return "&".join(sanitized_parts)


def _sanitize_request_id(request_id):
  if request_id is None:
    return None

  request_id = str(request_id).strip()
  if not request_id:
    return None

  sanitized = []
  for char in request_id:
    if char.isalnum() or char in "-_.:":
      sanitized.append(char)
    elif char.isspace() or char in "/\\":
      sanitized.append("-")

  request_id = "".join(sanitized).strip("-.")
  if not request_id:
    return None

  return request_id[:128]


def _get_or_create_request_id():
  request_id = _sanitize_request_id(request.headers.get("X-Request-ID"))
  if request_id:
    return request_id
  return uuid.uuid4().hex


def _get_response_size(response):
  content_length = response.calculate_content_length()
  if content_length is not None:
    return content_length

  if response.content_length is not None:
    return response.content_length

  if response.direct_passthrough or response.is_streamed:
    return "-"

  return len(response.get_data())


def register_access_logging(app, logger_name="supysonic"):
  if app.extensions.get("supysonic_access_logging"):
    return

  access_logger = logging.getLogger(f"{logger_name}.access")

  @app.before_request
  def _record_access_start_time():
    g.supysonic_access_started_at = time.perf_counter()
    g.supysonic_request_id = _get_or_create_request_id()

  @app.after_request
  def _log_access(response):
    started_at = getattr(g, "supysonic_access_started_at", None)
    request_id = getattr(g, "supysonic_request_id", None) or _get_or_create_request_id()
    duration = 0.0
    if started_at is not None:
      duration = time.perf_counter() - started_at

    content_length = _get_response_size(response)
    response.headers["X-Request-ID"] = request_id

    access_logger.info(
      format_log_event(
        "access",
        "request",
        type=_get_access_type(request.path),
        request_id=request_id,
        remote=request.remote_addr or "-",
        method=request.method,
        path=request.path,
        query=_sanitize_query_string(request.query_string.decode("utf-8") if request.query_string else ""),
        status=response.status_code,
        bytes=content_length,
        duration=f"{duration:.6f}s",
      )
    )
    return response

  app.extensions["supysonic_access_logging"] = True
  app.extensions["supysonic_access_logger_name"] = logger_name


def configure_web_logging(config, logger_name="supysonic"):
  logger = logging.getLogger(logger_name)
  log_dir = config.get("log_dir")

  _close_managed_handlers(logger)
  _configure_console_handler(logger)

  if log_dir:
    os.makedirs(log_dir, exist_ok=True)
    log_paths = build_web_log_paths(log_dir)
    route_prefixes = {
      category: {"prefixes": prefixes, "exact_names": ()}
      for category, prefixes in _build_route_prefixes(logger_name).items()
    }
    _configure_category_handlers(logger, log_paths, route_prefixes, config)
    if str(config.get("log_level", "")).upper() == "DEBUG":
      logger.addHandler(
        _build_file_handler(
          log_paths["debug"],
          config.get("log_rotate", True),
          config.get("log_backup_count", 7),
        )
      )

  _set_logger_level(logger, config.get("log_level"))
  return logger


def configure_daemon_logging(config, logger_name="supysonic"):
  logger = logging.getLogger(logger_name)
  log_dir = config.get("log_dir")

  _close_managed_handlers(logger)
  _configure_console_handler(logger)

  if log_dir:
    os.makedirs(log_dir, exist_ok=True)
    log_paths = build_daemon_log_paths(log_dir)
    _configure_category_handlers(logger, log_paths, _build_daemon_route_prefixes(logger_name), config)
    if str(config.get("log_level", "")).upper() == "DEBUG":
      logger.addHandler(
        _build_file_handler(
          _get_debug_log_file(log_paths["daemon"]),
          config.get("log_rotate", True),
          config.get("log_backup_count", 7),
        )
      )
  else:
    _configure_legacy_daemon_files(logger, config)

  _set_logger_level(logger, config.get("log_level"))
  return logger

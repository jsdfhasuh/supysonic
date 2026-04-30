import logging
import os
import time

from logging.handlers import TimedRotatingFileHandler

from flask import g, request


LOG_FILE_NAMES = {
  "summary": "supysonic.log",
  "access": "access.log",
  "task": "task.log",
  "emo": "emo.log",
  "scanner": "scanner.log",
  "api": "api.log",
}


class _LoggerPrefixFilter(logging.Filter):
  def __init__(self, prefixes):
    super().__init__()
    self.prefixes = tuple(prefixes)

  def filter(self, record):
    return any(record.name == prefix or record.name.startswith(prefix + ".") for prefix in self.prefixes)


def build_web_log_paths(log_dir):
  return {name: os.path.join(log_dir, filename) for name, filename in LOG_FILE_NAMES.items()}


def _close_managed_handlers(logger):
  remaining_handlers = []
  for handler in logger.handlers:
    if getattr(handler, "_supysonic_managed", False):
      handler.close()
      continue
    remaining_handlers.append(handler)
  logger.handlers = remaining_handlers


def _build_file_handler(log_path, log_rotate, log_backup_count, prefixes=None):
  if log_rotate:
    handler = TimedRotatingFileHandler(log_path, when="midnight", backupCount=log_backup_count)
  else:
    handler = logging.FileHandler(log_path)
  handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
  if prefixes:
    handler.addFilter(_LoggerPrefixFilter(prefixes))
  handler._supysonic_managed = True
  return handler


def _build_route_prefixes(logger_name):
  return {
    "access": (f"{logger_name}.access",),
    "task": (f"{logger_name}.TaskManger",),
    "emo": (f"{logger_name}.emo",),
    "scanner": (
      f"{logger_name}.scanner",
      f"{logger_name}.scanner_func",
      f"{logger_name}.watcher",
    ),
    "api": (f"{logger_name}.api",),
  }


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


def register_access_logging(app, logger_name="supysonic"):
  if app.extensions.get("supysonic_access_logging"):
    return

  access_logger = logging.getLogger(f"{logger_name}.access")

  @app.before_request
  def _record_access_start_time():
    g.supysonic_access_started_at = time.perf_counter()

  @app.after_request
  def _log_access(response):
    started_at = getattr(g, "supysonic_access_started_at", None)
    duration = 0.0
    if started_at is not None:
      duration = time.perf_counter() - started_at

    content_length = response.calculate_content_length()
    if content_length is None:
      content_length = len(response.get_data())

    access_logger.info(
      "[ACCESS:%s] %s %s %s status=%s bytes=%s duration=%.6fs",
      _get_access_type(request.path),
      request.remote_addr or "-",
      request.method,
      _get_request_target(),
      response.status_code,
      content_length,
      duration,
    )
    return response

  app.extensions["supysonic_access_logging"] = True
  app.extensions["supysonic_access_logger_name"] = logger_name


def configure_web_logging(config, logger_name="supysonic"):
  logger = logging.getLogger(logger_name)
  log_dir = config.get("log_dir")

  _close_managed_handlers(logger)
  console_handler = logging.StreamHandler()
  console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
  console_handler._supysonic_managed = True
  logger.addHandler(console_handler)

  if log_dir:
    os.makedirs(log_dir, exist_ok=True)
    log_paths = build_web_log_paths(log_dir)
    route_prefixes = _build_route_prefixes(logger_name)

    logger.addHandler(
      _build_file_handler(
        log_paths["summary"],
        config.get("log_rotate", True),
        config.get("log_backup_count", 7),
      )
    )
    for category, prefixes in route_prefixes.items():
      logger.addHandler(
        _build_file_handler(
          log_paths[category],
          config.get("log_rotate", True),
          config.get("log_backup_count", 7),
          prefixes=prefixes,
        )
      )

  log_level = config.get("log_level")
  if log_level:
    logger.setLevel(getattr(logging, str(log_level).upper(), logging.NOTSET))
  return logger

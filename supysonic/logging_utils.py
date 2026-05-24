import re


SENSITIVE_FIELD_NAMES = {
    "authorization",
    "cookie",
    "p",
    "password",
    "proxy-authorization",
    "s",
    "salt",
    "set-cookie",
    "t",
    "token",
    "x-api-key",
    "x-auth-token",
    "x-csrf-token",
    "x-release-token",
}
SAFE_VALUE_RE = re.compile(r"^[A-Za-z0-9._/@,:+\-*]+$")


def _normalize_field_name(name):
    return str(name).strip().lower()


def _stringify_scalar(value):
    if value is None:
        return "-"

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, float):
        return f"{value:.6f}"

    return str(value)


def _sanitize_text(value):
    return value.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")


def _format_value(value):
    if isinstance(value, (list, tuple, set)):
        items = [_stringify_scalar(item) for item in value]
        value = ",".join(items) if not isinstance(value, set) else ",".join(sorted(items))
    else:
        value = _stringify_scalar(value)

    value = _sanitize_text(value)
    if not value or not SAFE_VALUE_RE.match(value):
        return '"' + value.replace('"', '\\"') + '"'
    return value


def format_log_event(domain, event, **fields):
    parts = [str(domain), f"event={_format_value(event)}"]

    for key, value in fields.items():
        field_name = _normalize_field_name(key)
        if field_name in SENSITIVE_FIELD_NAMES:
            value = "***"
        parts.append(f"{field_name}={_format_value(value)}")

    return " ".join(parts)

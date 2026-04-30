"""Build compact debug trace blocks for scanner decisions."""

from __future__ import annotations

from typing import Iterable, Mapping, Optional


def _formatFieldValue(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        if not value:
            return None
        return ", ".join(str(item) for item in value)

    text = str(value)
    return text or None


def buildTraceBlock(
    traceType: str,
    headerFields: Mapping[str, object],
    detailLines: Iterable[str],
) -> str:
    header = [traceType]
    for key, value in headerFields.items():
        formatted_value = _formatFieldValue(value)
        if formatted_value is None:
            continue
        header.append(f"{key}={formatted_value}")

    lines = list(detailLines)
    if not lines:
        lines = ["no details"]

    return "\n".join([" ".join(header)] + [f"  - {line}" for line in lines])


def logTrace(
    logger,
    traceType: str,
    headerFields: Mapping[str, object],
    detailLines: Iterable[str],
) -> None:
    logger.debug(buildTraceBlock(traceType, headerFields, detailLines))

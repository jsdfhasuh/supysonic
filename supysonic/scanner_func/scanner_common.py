"""Provide low-level shared helpers used across scanner modules."""

from __future__ import annotations

import mediafile
from typing import Optional


def sanitizeString(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return value.replace("\x00", "").strip()


def tryLoadTag(path: str) -> Optional[mediafile.MediaFile]:
    try:
        return mediafile.MediaFile(path)
    except mediafile.UnreadableFileError:
        return None

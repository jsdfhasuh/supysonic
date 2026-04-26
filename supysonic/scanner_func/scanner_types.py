"""Define lightweight shared data structures used by scanner helper modules."""

from dataclasses import dataclass
from os import stat_result


@dataclass(frozen=True)
class ScanTarget:
    path: str
    basename: str
    stat: stat_result

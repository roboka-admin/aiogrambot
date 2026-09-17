"""Read container memory limits/usage from cgroup files.

On PaaS containers (Koyeb, Northflank, ...) ``psutil.virtual_memory()``
reports the *host* machine, so a 512 MB container can look like it has
tens of gigabytes free. The kernel exposes the real limit through cgroup
v2 (``/sys/fs/cgroup/memory.max``) or v1
(``/sys/fs/cgroup/memory/memory.limit_in_bytes``). When neither exists
(local dev, tests) we return ``None`` and callers fall back to psutil.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_V2_LIMIT = Path("/sys/fs/cgroup/memory.max")
_V2_USAGE = Path("/sys/fs/cgroup/memory.current")
_V1_LIMIT = Path("/sys/fs/cgroup/memory/memory.limit_in_bytes")
_V1_USAGE = Path("/sys/fs/cgroup/memory/memory.usage_in_bytes")

# cgroup v1 reports "no limit" as a huge number close to 2**63.
_V1_UNLIMITED_THRESHOLD = 1 << 60


@dataclass(frozen=True, slots=True)
class CgroupMemory:
    used_bytes: int
    limit_bytes: int

    @property
    def percent(self) -> float:
        if self.limit_bytes <= 0:
            return 0.0
        return round(self.used_bytes / self.limit_bytes * 100, 1)


def _read_int(path: Path) -> int | None:
    try:
        raw = path.read_text().strip()
    except OSError:
        return None
    if raw == "max":
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def read_cgroup_memory() -> CgroupMemory | None:
    """Return container memory usage/limit, or ``None`` when not limited."""
    for limit_path, usage_path in ((_V2_LIMIT, _V2_USAGE), (_V1_LIMIT, _V1_USAGE)):
        limit = _read_int(limit_path)
        if limit is None or limit >= _V1_UNLIMITED_THRESHOLD:
            continue
        used = _read_int(usage_path)
        if used is None:
            continue
        return CgroupMemory(used_bytes=used, limit_bytes=limit)
    return None

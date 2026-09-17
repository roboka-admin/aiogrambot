from pathlib import Path

import pytest

from core import cgroup


def _point_to(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **files: str) -> None:
    for attr in ("_V2_LIMIT", "_V2_USAGE", "_V1_LIMIT", "_V1_USAGE"):
        monkeypatch.setattr(cgroup, attr, tmp_path / f"missing-{attr}")
    for attr, content in files.items():
        path = tmp_path / attr
        path.write_text(content)
        monkeypatch.setattr(cgroup, attr, path)


def test_returns_none_when_no_cgroup_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _point_to(monkeypatch, tmp_path)
    assert cgroup.read_cgroup_memory() is None


def test_reads_cgroup_v2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _point_to(monkeypatch, tmp_path, _V2_LIMIT="536870912\n", _V2_USAGE="268435456\n")

    memory = cgroup.read_cgroup_memory()

    assert memory is not None
    assert memory.limit_bytes == 512 * 1024 * 1024
    assert memory.used_bytes == 256 * 1024 * 1024
    assert memory.percent == 50.0


def test_v2_max_means_unlimited_and_falls_back_to_v1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _point_to(
        monkeypatch,
        tmp_path,
        _V2_LIMIT="max\n",
        _V2_USAGE="1\n",
        _V1_LIMIT="1048576\n",
        _V1_USAGE="524288\n",
    )

    memory = cgroup.read_cgroup_memory()

    assert memory is not None
    assert memory.limit_bytes == 1048576
    assert memory.percent == 50.0


def test_v1_huge_limit_means_unlimited(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _point_to(monkeypatch, tmp_path, _V1_LIMIT="9223372036854771712\n", _V1_USAGE="1\n")
    assert cgroup.read_cgroup_memory() is None

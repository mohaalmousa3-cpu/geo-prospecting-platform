from __future__ import annotations

import os
from pathlib import Path

import pytest

from geo_common.storage import LocalStorage, StorageKeyError


@pytest.fixture
def store(tmp_path: Path) -> LocalStorage:
    return LocalStorage(tmp_path / "root")


def test_roundtrip_and_overwrite(store: LocalStorage) -> None:
    store.put("aoi/1/a.bin", b"one")
    assert store.exists("aoi/1/a.bin") and store.get("aoi/1/a.bin") == b"one"
    store.put("aoi/1/a.bin", b"two")
    assert store.get("aoi/1/a.bin") == b"two"
    assert store.open_path("aoi/1/a.bin").read_bytes() == b"two"
    store.delete("aoi/1/a.bin")
    assert not store.exists("aoi/1/a.bin")
    store.delete("aoi/1/a.bin")  # idempotent


@pytest.mark.parametrize(
    "key",
    ["../x", "a/../../x", "/etc/passwd", "", "a//b", "./a", "a/./b", "a\x00b", "a\\..\\b", ".."],
)
def test_unsafe_keys_rejected(store: LocalStorage, key: str) -> None:
    for op in (store.exists, store.get, store.delete, store.open_path):
        with pytest.raises(StorageKeyError):
            op(key)
    with pytest.raises(StorageKeyError):
        store.put(key, b"x")


def test_symlink_escape_rejected(store: LocalStorage, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "root" / "link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(StorageKeyError):
        store.put("link/evil.txt", b"x")
    with pytest.raises(StorageKeyError):
        store.get("link/evil.txt")
    assert not (outside / "evil.txt").exists()


def test_no_stray_temp_files(store: LocalStorage, tmp_path: Path) -> None:
    store.put("k/v", b"x")
    assert os.listdir(tmp_path / "root" / "k") == ["v"]

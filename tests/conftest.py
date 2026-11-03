from __future__ import annotations

import pytest

from yuji import config
from yuji.store import Store


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("YUJI_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def store(home):
    s = Store(path=config.db_path())
    yield s
    s.close()

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from zhiji.bus import Bus
from zhiji.engine import Engine
from zhiji.store import Store

ROOT = Path(__file__).parent.parent


@pytest.fixture()
def store(tmp_path):
    return Store(tmp_path / "test.db")


@pytest.fixture()
def engine(store, tmp_path):
    bus = Bus(store)
    eng = Engine(store, bus, ROOT / "skills", tmp_path / "data")
    eng.init_skills()
    return eng

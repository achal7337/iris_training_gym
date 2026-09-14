import os

import pytest

from trajectory_gym.env.database import connect, reset_from_dump
from trajectory_gym.env.state import EpisodeState
from trajectory_gym.llm.client import MOCK_MODE_ENV_VAR

# Force every LLM role onto the mock provider for the whole test session,
# regardless of what config/models.yaml points real runs at. This is what
# keeps `make test` at zero cost and zero network (NON-NEGOTIABLE 6 / Phase 1
# accept criteria) even after agent/judge/writer are wired to live providers.
os.environ[MOCK_MODE_ENV_VAR] = "1"


@pytest.fixture
def db():
    conn = connect(":memory:")
    reset_from_dump(conn)
    yield conn
    conn.close()


@pytest.fixture
def state(db):
    return EpisodeState(conn=db, scenario_id="TEST_SCENARIO_01")

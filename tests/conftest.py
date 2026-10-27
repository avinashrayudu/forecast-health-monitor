import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="session")
def cfgs():
    from world.inject_events import load_configs
    return load_configs()


@pytest.fixture(scope="session")
def dev(cfgs):
    from world.inject_events import DEV_EVENTS, build_scenario
    return build_scenario(cfgs, DEV_EVENTS, "dev")

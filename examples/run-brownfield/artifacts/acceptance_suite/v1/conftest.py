import os

import pytest


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.environ["BASE_URL"]

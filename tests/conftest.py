import shutil
from pathlib import Path

import pytest

from orchestrator.config import load_config
from orchestrator.human.gate import ScriptedIO
from orchestrator.llm.backends import FakeBackend
from orchestrator.runtime.context import create_run

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    for rel in ("policy", "catalog"):
        shutil.copytree(REPO_ROOT / rel, tmp_path / rel)
    (tmp_path / "config").mkdir()
    shutil.copy(REPO_ROOT / "config/pricing.yaml", tmp_path / "config/pricing.yaml")
    return tmp_path


@pytest.fixture
def config(project_root: Path):
    return load_config(project_root, env={"ANTHROPIC_API_KEY": "test-key"})


@pytest.fixture
def make_run(project_root, config):
    def _make(answers=None, scripts=None):
        io = ScriptedIO(list(answers or []))
        backend = FakeBackend(scripts or {})
        ctx = create_run(project_root, config, io, backend)
        return ctx, io, backend

    return _make

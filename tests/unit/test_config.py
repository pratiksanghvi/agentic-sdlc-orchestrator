import shutil
from pathlib import Path

import pytest

from orchestrator.cli import main
from orchestrator.config import ConfigError, load_config
from orchestrator.config.loader import parse_properties

REPO_ROOT = Path(__file__).resolve().parents[2]
FAKE_ENV = {"ANTHROPIC_API_KEY": "test-key"}


@pytest.fixture
def root(tmp_path: Path) -> Path:
    for rel in ("policy", "catalog"):
        shutil.copytree(REPO_ROOT / rel, tmp_path / rel)
    (tmp_path / "config").mkdir()
    shutil.copy(REPO_ROOT / "config/pricing.yaml", tmp_path / "config/pricing.yaml")
    return tmp_path


def test_repo_config_is_valid(root: Path) -> None:
    config = load_config(root, env=FAKE_ENV)
    assert config.stacks.stacks["java21-springboot3-maven"].validated
    assert set(config.nfr.entries) == {"RL-BASIC", "SEC-INPUT", "OBS-METRICS"}
    assert set(config.governance_hashes) == {"policy", "stacks", "nfr"}


def test_missing_api_key_refuses(root: Path) -> None:
    with pytest.raises(ConfigError, match="api_key is empty"):
        load_config(root, env={})


def test_properties_file_used_and_env_overrides(root: Path) -> None:
    (root / "config/application.properties").write_text(
        "anthropic.api_key=from-file\napprover.name=alice\n"
    )
    assert load_config(root, env={}).app.anthropic_api_key == "from-file"
    config = load_config(root, env={"ANTHROPIC_API_KEY": "from-env"})
    assert config.app.anthropic_api_key == "from-env"
    assert config.app.approver_name == "alice"


def test_api_key_not_in_repr(root: Path) -> None:
    config = load_config(root, env={"ANTHROPIC_API_KEY": "super-secret-value"})
    assert "super-secret-value" not in repr(config)


def test_unknown_property_refuses(root: Path) -> None:
    (root / "config/application.properties").write_text("anthropic.apikey=typo\n")
    with pytest.raises(ConfigError, match="unknown keys"):
        load_config(root, env=FAKE_ENV)


def test_invalid_policy_refuses(root: Path) -> None:
    policy = root / "policy/policy.yaml"
    policy.write_text(policy.read_text().replace("verify_auto_fixes: 3", "verify_auto_fixes: -1"))
    with pytest.raises(ConfigError, match="verify_auto_fixes"):
        load_config(root, env=FAKE_ENV)


def test_nfr_outside_supported_category_refuses(root: Path) -> None:
    nfr = root / "catalog/nfr_catalog.yaml"
    nfr.write_text(nfr.read_text().replace("category: rate_limit", "category: performance"))
    with pytest.raises(ConfigError):
        load_config(root, env=FAKE_ENV)


def test_model_without_pricing_refuses(root: Path) -> None:
    with pytest.raises(ConfigError, match="no entry in config/pricing.yaml"):
        load_config(root, env={**FAKE_ENV, "ORCHESTRATOR_MODEL_CODING": "unknown-model"})


def test_governance_hash_changes_with_policy(root: Path) -> None:
    before = load_config(root, env=FAKE_ENV).governance_hashes["policy"]
    policy = root / "policy/policy.yaml"
    policy.write_text(policy.read_text() + "\n# edited\n")
    assert load_config(root, env=FAKE_ENV).governance_hashes["policy"] != before


def test_parse_properties_rejects_garbage() -> None:
    with pytest.raises(ConfigError, match="line 2"):
        parse_properties("# comment\nnot-a-pair\n")


def test_cli_check_config(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    assert main(["--root", str(root), "check-config"]) == 0
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    assert main(["--root", str(root), "check-config"]) == 2

"""Load and validate all configuration files from a project root."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import yaml
from pydantic import ValidationError

from orchestrator.config.models import (
    AppSettings,
    Config,
    NfrCatalog,
    Policy,
    Pricing,
    StackCatalog,
)

PROPERTIES_FILE = Path("config/application.properties")
GOVERNANCE_FILES = {
    "policy": Path("policy/policy.yaml"),
    "stacks": Path("catalog/stacks.yaml"),
    "nfr": Path("catalog/nfr_catalog.yaml"),
}
PRICING_FILE = Path("config/pricing.yaml")

# properties key -> AppSettings field; matching environment variables override the file
PROPERTY_KEYS = {
    "anthropic.api_key": ("anthropic_api_key", "ANTHROPIC_API_KEY"),
    "approver.name": ("approver_name", "ORCHESTRATOR_APPROVER"),
    "model.reasoning": ("model_reasoning", "ORCHESTRATOR_MODEL_REASONING"),
    "model.coding": ("model_coding", "ORCHESTRATOR_MODEL_CODING"),
    "model.fallback": ("model_fallback", "ORCHESTRATOR_MODEL_FALLBACK"),
}


class ConfigError(Exception):
    """Raised when configuration is missing or invalid. The orchestrator refuses to start."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_properties(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith(("#", "!")):
            continue
        if "=" not in line:
            raise ConfigError(f"application.properties line {lineno}: expected key=value")
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        raise ConfigError(f"missing config file: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: expected a mapping at the top level")
    return data


def _load_app_settings(root: Path, env: dict[str, str]) -> AppSettings:
    props_path = root / PROPERTIES_FILE
    props = parse_properties(props_path.read_text(encoding="utf-8")) if props_path.is_file() else {}
    unknown = set(props) - set(PROPERTY_KEYS)
    if unknown:
        raise ConfigError(f"application.properties: unknown keys {sorted(unknown)}")
    fields: dict[str, str] = {}
    for key, (field, env_var) in PROPERTY_KEYS.items():
        value = env.get(env_var) or props.get(key)
        if value:
            fields[field] = value
    fields.setdefault("anthropic_api_key", "")
    return AppSettings(**fields)


def load_config(root: Path, env: dict[str, str] | None = None) -> Config:
    """Load every config file under `root`, validate, and return a frozen Config."""
    env = dict(os.environ) if env is None else env
    try:
        app = _load_app_settings(root, env)
        raw = {name: _load_yaml(root / rel) for name, rel in GOVERNANCE_FILES.items()}
        return Config(
            app=app,
            policy=Policy(**raw["policy"]),
            stacks=StackCatalog(**raw["stacks"]),
            nfr=NfrCatalog(**raw["nfr"]),
            pricing=Pricing(**_load_yaml(root / PRICING_FILE)),
            governance_hashes={
                name: sha256_file(root / rel) for name, rel in GOVERNANCE_FILES.items()
            },
        )
    except ValidationError as exc:
        raise ConfigError(_format_validation_error(exc)) from exc


def _format_validation_error(exc: ValidationError) -> str:
    lines = [f"invalid configuration ({exc.error_count()} problem(s)):"]
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or exc.title
        lines.append(f"  - {exc.title}.{loc}: {err['msg']}")
    return "\n".join(lines)

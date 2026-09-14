"""Loads config/*.yaml and .env into typed, cached config objects.

Model IDs and every tunable number live in config/, never in code — see
Section 2/3 of the build prompt (prompt.md).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"

load_dotenv(REPO_ROOT / ".env")


class ModelRoleConfig(BaseModel):
    provider: str
    model: str
    temperature: float
    max_tokens: int


class ModelsConfig(BaseModel):
    agent: ModelRoleConfig
    judge: ModelRoleConfig
    selector: ModelRoleConfig
    writer: ModelRoleConfig
    recommendation: ModelRoleConfig

    def for_role(self, role: str) -> ModelRoleConfig:
        return getattr(self, role)


class FailureInjectionConfig(BaseModel):
    lookup_order: dict[str, float]
    lookup_customer: dict[str, float]


class EnvConfig(BaseModel):
    action_budget: int
    tool_costs: dict[str, int]
    failure_injection: FailureInjectionConfig
    read_policy: dict[str, int]

    @property
    def read_policy_top_k(self) -> int:
        return self.read_policy["top_k"]


class GateConfig(BaseModel):
    mode: str
    tau: float
    risk_levels: dict[str, str]
    irreversible_actions: list[str]
    tau_sweep: list[float]


def _load_yaml(name: str) -> dict:
    path = CONFIG_DIR / name
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache
def get_models_config() -> ModelsConfig:
    return ModelsConfig.model_validate(_load_yaml("models.yaml"))


@lru_cache
def get_env_config() -> EnvConfig:
    return EnvConfig.model_validate(_load_yaml("env.yaml"))


@lru_cache
def get_gate_config() -> GateConfig:
    return GateConfig.model_validate(_load_yaml("gate.yaml"))

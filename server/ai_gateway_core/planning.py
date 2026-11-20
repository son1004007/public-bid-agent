"""Strict readiness and execution planning: registration is never execution consent."""
from dataclasses import dataclass
from enum import Enum
from typing import Collection


class Provider(str, Enum):
    CODEX = "CODEX"
    CLAUDE = "CLAUDE"


class ExecutionMode(str, Enum):
    NO_AI = "NO_AI"
    SINGLE_CODEX = "SINGLE_CODEX"
    SINGLE_CLAUDE = "SINGLE_CLAUDE"
    DUAL_INDEPENDENT = "DUAL_INDEPENDENT"


@dataclass(frozen=True)
class Profile:
    provider: Provider
    registered: bool = False
    enabled: bool = False
    authenticated: bool = False
    execution_contract_approved: bool = False
    runtime_isolated: bool = False
    data_export_approved: bool = False
    quota_available: bool = False

    @property
    def ready(self) -> bool:
        return all((self.registered, self.enabled, self.authenticated,
                    self.execution_contract_approved, self.runtime_isolated,
                    self.data_export_approved, self.quota_available))


@dataclass(frozen=True)
class ExecutionPlan:
    mode: ExecutionMode
    providers: tuple[Provider, ...]
    requires_explicit_run_request: bool = True


def select_plan(profiles: Collection[Profile]) -> ExecutionPlan:
    """Pick 0/1/2 READY providers, failing closed for duplicates or bad profiles."""
    seen: set[Provider] = set()
    eligible: set[Provider] = set()
    for profile in profiles:
        if type(profile) is not Profile or type(profile.provider) is not Provider:
            raise ValueError("INVALID_PROVIDER_PROFILE")
        if profile.provider in seen:
            raise ValueError("DUPLICATE_PROVIDER_PROFILE")
        seen.add(profile.provider)
        if profile.ready:
            eligible.add(profile.provider)
    providers = tuple(p for p in Provider if p in eligible)
    mode = {
        (): ExecutionMode.NO_AI,
        (Provider.CODEX,): ExecutionMode.SINGLE_CODEX,
        (Provider.CLAUDE,): ExecutionMode.SINGLE_CLAUDE,
        (Provider.CODEX, Provider.CLAUDE): ExecutionMode.DUAL_INDEPENDENT,
    }[providers]
    return ExecutionPlan(mode=mode, providers=providers)

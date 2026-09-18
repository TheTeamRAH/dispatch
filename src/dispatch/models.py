"""Normalized, persistence-safe discovery models."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum


class Outcome(StrEnum):
    SUCCESS = "success"
    UNSUPPORTED = "unsupported"
    CONNECTION_FAILED = "connection_failed"
    AUTHENTICATION_FAILED = "authentication_failed"
    HOST_UNTRUSTED = "host_untrusted"
    HOST_KEY_MISMATCH = "host_key_mismatch"
    DISCOVERY_FAILED = "discovery_failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class CurrentRebootState(StrEnum):
    REQUIRED = "required"
    NOT_REQUIRED = "not_required"
    UNKNOWN = "unknown"


class RebootForecast(StrEnum):
    LIKELY = "likely"
    NOT_INDICATED = "not_indicated"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SecurityState:
    state: str
    count: int | None = None
    explanation: str | None = None

    @classmethod
    def known(cls, count: int) -> SecurityState:
        if count < 0:
            raise ValueError("security count must be non-negative")
        return cls("known", count=count)

    @classmethod
    def unknown(cls, explanation: str) -> SecurityState:
        if not explanation:
            raise ValueError("unknown security state requires an explanation")
        return cls("unknown", explanation=explanation)


@dataclass(frozen=True)
class TargetSnapshot:
    id: str | None
    name: str
    ssh_destination: str
    provider: str = "rpm"

    def __post_init__(self) -> None:
        if self.id is not None and not self.id:
            raise ValueError("target id cannot be empty")
        if not self.name or not self.ssh_destination or any(c.isspace() or ord(c) < 32 for c in self.ssh_destination):
            raise ValueError("target destination must be one non-empty token")
        if self.provider != "rpm":
            raise ValueError("unsupported provider")


@dataclass(frozen=True)
class PackageUpdate:
    name: str
    architecture: str
    installed_evr: str
    candidate_evr: str
    repository: str | None
    security_advisory_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class TargetResult:
    target: TargetSnapshot
    discovered_at: str
    outcome: Outcome
    packages: tuple[PackageUpdate, ...] = ()
    security_state: SecurityState = field(default_factory=lambda: SecurityState.unknown("Discovery did not provide advisory metadata."))
    current_reboot: CurrentRebootState = CurrentRebootState.UNKNOWN
    reboot_forecast: RebootForecast = RebootForecast.UNKNOWN
    explanation: str | None = None

    def __post_init__(self) -> None:
        if self.outcome is not Outcome.SUCCESS and not self.explanation:
            raise ValueError("non-success outcomes require an explanation")
        if self.outcome is not Outcome.SUCCESS and self.packages:
            raise ValueError("only successful results may contain packages")

    def to_dict(self) -> dict:
        return json.loads(json.dumps(asdict(self)))


@dataclass(frozen=True)
class InspectionRun:
    run_id: str
    started_at: str
    completed_at: str
    results: tuple[TargetResult, ...]
    schema_version: int = 1

    def to_dict(self) -> dict:
        return json.loads(json.dumps(asdict(self)))

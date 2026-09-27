"""Declarative remote shell workflow models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ShellStep:
    """One named shell command in a workflow."""

    id: str
    name: str
    command: str
    extra: dict[str, Any] = field(default_factory=dict, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {**self.extra, "id": self.id, "name": self.name, "command": self.command}


@dataclass(frozen=True)
class WorkflowDefinition:
    """A persisted, target-independent remote Bash workflow."""

    id: str
    name: str
    workflow_type: str = "shell"
    session: str = "isolated"
    startup: tuple[ShellStep, ...] = ()
    steps: tuple[ShellStep, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        if not self.id or not self.name or self.workflow_type != "shell":
            raise ValueError("workflow requires a non-empty shell identity")
        if self.session not in {"isolated", "persistent"}:
            raise ValueError("unsupported workflow session")
        if not self.steps:
            raise ValueError("workflow requires at least one step")
        ids = [step.id for step in (*self.startup, *self.steps)]
        if any(not item for item in ids) or len(ids) != len(set(ids)):
            raise ValueError("workflow step ids must be unique and non-empty")
        if any(not step.name or not step.command for step in (*self.startup, *self.steps)):
            raise ValueError("workflow steps require names and commands")

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.extra,
            "version": 1,
            "id": self.id,
            "name": self.name,
            "type": self.workflow_type,
            "session": self.session,
            "startup": [step.to_dict() for step in self.startup],
            "steps": [step.to_dict() for step in self.steps],
        }


@dataclass(frozen=True)
class StepResult:
    """The bounded result of one startup or workflow step."""

    step_id: str
    name: str
    outcome: str
    started_at: str
    completed_at: str
    exit_status: int | None
    stdout: str
    stderr: str
    explanation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkflowTargetResult:
    """The results of running one workflow against one target."""

    workflow_id: str
    workflow_name: str
    session: str
    target: dict[str, Any]
    outcome: str
    steps: tuple[StepResult, ...]
    explanation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "steps": [step.to_dict() for step in self.steps]}

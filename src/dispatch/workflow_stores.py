"""Per-workflow TOML and JSON history persistence."""

from __future__ import annotations

import json
import os
import re
import tempfile
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .workflow_models import ShellStep, WorkflowDefinition

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SECRET_NAMES = {"password", "passphrase", "private_key", "private_key_data", "credential", "credentials"}


def workflow_path() -> Path:
    """Return the default per-workflow configuration directory."""
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "dispatch" / "workflows"


def _contains_secret(value: object) -> bool:
    if isinstance(value, dict):
        return any(str(key).lower() in _SECRET_NAMES or _contains_secret(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_secret(item) for item in value)
    return False


def _toml_value(value: object) -> str:
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, list) and all(isinstance(item, (str, int, float, bool)) for item in value):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    raise ValueError("unsupported TOML field value")


def _render(document: dict[str, Any]) -> str:
    lines: list[str] = []
    for key, value in document.items():
        if key not in {"startup", "steps"}:
            lines.append(f"{key} = {_toml_value(value)}")
    for section in ("startup", "steps"):
        for item in document.get(section, []):
            lines.extend(["", f"[[{section}]]"])
            for key, value in item.items():
                lines.append(f"{key} = {_toml_value(value)}")
    return "\n".join(lines) + "\n"


def _step(entry: object) -> ShellStep:
    if not isinstance(entry, dict) or any(not isinstance(entry.get(key), str) or not entry[key] for key in ("id", "name", "command")):
        raise ValueError("invalid workflow step")
    return ShellStep(entry["id"], entry["name"], entry["command"], {key: value for key, value in entry.items() if key not in {"id", "name", "command"}})


def _definition(document: dict[str, Any]) -> WorkflowDefinition:
    if document.get("version") != 1 or not all(isinstance(document.get(key), str) for key in ("id", "name", "type", "session")):
        raise ValueError("invalid workflow header")
    if not _ID.fullmatch(document["id"]):
        raise ValueError("workflow id is not filesystem-safe")
    if document["type"] != "shell" or document["session"] not in {"isolated", "persistent"}:
        raise ValueError("unsupported workflow type or session")
    startup = tuple(_step(item) for item in document.get("startup", []))
    steps = tuple(_step(item) for item in document.get("steps", []))
    extra = {key: value for key, value in document.items() if key not in {"version", "id", "name", "type", "session", "startup", "steps"}}
    return WorkflowDefinition(document["id"], document["name"], document["type"], document["session"], startup, steps, extra)


class WorkflowRegistry:
    """Load and atomically save one workflow document per TOML file."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or workflow_path()
        self.warning: str | None = None

    def load(self) -> list[WorkflowDefinition]:
        if not self.path.exists():
            return []
        workflows: list[WorkflowDefinition] = []
        seen: set[str] = set()
        warnings: list[str] = []
        for file in sorted(self.path.glob("*.toml")):
            try:
                document = tomllib.loads(file.read_text())
                if _contains_secret(document):
                    raise ValueError("workflow file must not contain credentials")
                workflow = _definition(document)
                if file.stem != workflow.id:
                    raise ValueError("workflow filename must match workflow id")
                if workflow.id in seen:
                    raise ValueError("workflow ids must be unique")
                seen.add(workflow.id)
                workflows.append(workflow)
            except (OSError, tomllib.TOMLDecodeError, TypeError, ValueError) as error:
                warnings.append(f"{file.name}: {error}")
        self.warning = "; ".join(warnings) if warnings else None
        if warnings:
            raise ValueError(self.warning)
        return workflows

    def save(self, workflow: WorkflowDefinition) -> None:
        self.path.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.path, 0o700)
        destination = self.path / f"{workflow.id}.toml"
        document = workflow.to_dict()
        if destination.exists():
            original = tomllib.loads(destination.read_text())
            if _contains_secret(original):
                raise ValueError("workflow file must not contain credentials")
            original.update({key: value for key, value in document.items() if key not in {"startup", "steps"}})
            original["startup"] = document["startup"]
            original["steps"] = document["steps"]
            document = original
        self._write(destination, document)

    def remove(self, workflow_id: str) -> None:
        if not _ID.fullmatch(workflow_id):
            raise ValueError("invalid workflow id")
        destination = self.path / f"{workflow_id}.toml"
        if not destination.exists():
            raise ValueError("workflow does not exist")
        destination.unlink()

    @staticmethod
    def _write(destination: Path, document: dict[str, Any]) -> None:
        descriptor, temporary = tempfile.mkstemp(dir=destination.parent)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w") as file:
                file.write(_render(document))
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


class WorkflowHistoryStore:
    """Persist bounded, secret-free workflow result dictionaries."""

    def __init__(self, path: Path, output_limit: int = 100_000) -> None:
        self.path = path
        self.output_limit = output_limit

    def append(self, run: dict[str, Any]) -> None:
        self.begin(run)

    def begin(self, run: dict[str, Any]) -> Path:
        self.path.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.path, 0o700)
        stamp = datetime.now(UTC).isoformat().replace("+00:00", "Z").replace(":", "-")
        destination = self.path / f"{stamp}.json"
        self._write(destination, run)
        return destination

    def finish(self, destination: Path, run: dict[str, Any]) -> None:
        self._write(destination, run)

    @staticmethod
    def _write(destination: Path, run: dict[str, Any]) -> None:
        descriptor, temporary = tempfile.mkstemp(dir=destination.parent)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w") as file:
                json.dump(run, file)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def list_runs(self) -> list[dict[str, Any]]:
        runs: list[dict[str, Any]] = []
        for record in sorted(self.path.glob("*.json"), reverse=True) if self.path.exists() else []:
            try:
                runs.append(json.loads(record.read_text()))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
        return runs

"""XDG-backed target and inspection-history persistence."""

from __future__ import annotations

import json
import os
import tempfile
import tomllib
from pathlib import Path

from .models import CurrentRebootState, InspectionRun, Outcome, PackageUpdate, RebootForecast, SecurityState, TargetResult, TargetSnapshot


def config_path() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "dispatch" / "targets.toml"


def history_path() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "dispatch" / "history"


class TargetRegistry:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or config_path()
        self._document: dict = {"version": 1, "targets": []}

    def load(self) -> list[TargetSnapshot]:
        if not self.path.exists():
            return []
        try:
            document = tomllib.loads(self.path.read_text())
        except (tomllib.TOMLDecodeError, OSError) as error:
            raise ValueError("invalid target registry") from error
        if document.get("version") != 1 or not isinstance(document.get("targets", []), list):
            raise ValueError("unsupported target registry")
        if self._contains_secret(document):
            raise ValueError("target registry must not contain credentials")
        targets = [self._target(entry) for entry in document.get("targets", [])]
        ids = [target.id for target in targets]
        if len(ids) != len(set(ids)):
            raise ValueError("target ids must be unique")
        self._document = document
        return targets

    def save(self, target: TargetSnapshot) -> None:
        targets = self.load()
        if target.id is None or any(item.id == target.id for item in targets):
            raise ValueError("target id must be unique")
        self._document.setdefault("targets", []).append({"id": target.id, "name": target.name, "ssh_destination": target.ssh_destination, "provider": target.provider})
        self._write()

    def edit(self, target: TargetSnapshot) -> None:
        if target.id is None:
            raise ValueError("saved target requires id")
        self.load()
        for entry in self._document["targets"]:
            if entry["id"] == target.id:
                entry.update(name=target.name, ssh_destination=target.ssh_destination, provider=target.provider)
                self._write()
                return
        raise ValueError("target does not exist")

    def remove(self, target_id: str) -> None:
        self.load()
        original = len(self._document["targets"])
        self._document["targets"] = [item for item in self._document["targets"] if item["id"] != target_id]
        if len(self._document["targets"]) == original:
            raise ValueError("target does not exist")
        self._write()

    @staticmethod
    def _target(entry: object) -> TargetSnapshot:
        if not isinstance(entry, dict) or any(not isinstance(entry.get(key), str) for key in ("id", "name", "ssh_destination")):
            raise ValueError("invalid target entry")
        return TargetSnapshot(entry["id"], entry["name"], entry["ssh_destination"], entry.get("provider", "rpm"))

    @staticmethod
    def _contains_secret(value: object) -> bool:
        secret_names = {"password", "passphrase", "private_key", "private_key_data", "credential", "credentials"}
        if isinstance(value, dict):
            return any(str(key).lower() in secret_names or TargetRegistry._contains_secret(item) for key, item in value.items())
        if isinstance(value, list):
            return any(TargetRegistry._contains_secret(item) for item in value)
        return False

    def _write(self) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        lines = [f"version = {self._document['version']}"]
        for key, value in self._document.items():
            if key not in {"version", "targets"}:
                lines.append(f'{key} = {json.dumps(value)}')
        for entry in self._document["targets"]:
            lines.extend(["", "[[targets]]"] + [f"{key} = {json.dumps(value)}" for key, value in entry.items()])
        self.path.write_text("\n".join(lines) + "\n")


class HistoryStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or history_path()
        self.warning: str | None = None

    def append(self, run: InspectionRun) -> None:
        self.path.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.path, 0o700)
        destination = self.path / f"{run.completed_at.replace(':', '-')}-{run.run_id}.json"
        descriptor, temporary = tempfile.mkstemp(dir=self.path)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w") as file:
                json.dump(run.to_dict(), file)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def list_runs(self) -> list[InspectionRun]:
        if not self.path.exists():
            return []
        runs = []
        for record in self.path.glob("*.json"):
            try:
                runs.append(self._decode(json.loads(record.read_text())))
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                self.warning = "Some malformed local history records were ignored."
        return sorted(runs, key=lambda run: run.completed_at, reverse=True)

    @staticmethod
    def _decode(data: dict) -> InspectionRun:
        if data["schema_version"] != 1:
            raise ValueError("unsupported history schema")
        results = []
        for item in data["results"]:
            target = TargetSnapshot(**item["target"])
            packages = tuple(PackageUpdate(**{**package, "security_advisory_ids": tuple(package["security_advisory_ids"])} ) for package in item["packages"])
            security = SecurityState(**item["security_state"])
            results.append(TargetResult(
                target, item["discovered_at"], Outcome(item["outcome"]), packages, security,
                CurrentRebootState(item["current_reboot"]), RebootForecast(item["reboot_forecast"]),
                item["explanation"], item.get("current_reboot_explanation", "Current reboot requirement could not be determined."),
                item.get("reboot_forecast_explanation", "Post-update reboot impact could not be determined."),
            ))
        return InspectionRun(data["run_id"], data["started_at"], data["completed_at"], tuple(results), data["schema_version"])

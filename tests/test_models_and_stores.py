from __future__ import annotations

import json
import os

import pytest

from dispatch.models import (
    CurrentRebootState,
    InspectionRun,
    Outcome,
    PackageUpdate,
    RebootForecast,
    SecurityState,
    TargetResult,
    TargetSnapshot,
)
from dispatch.stores import HistoryStore, TargetRegistry


def target() -> TargetSnapshot:
    return TargetSnapshot("server-1", "Server one", "admin@server-1", "rpm")


def result() -> TargetResult:
    return TargetResult(
        target=target(), discovered_at="2026-09-18T18:58:00Z", outcome=Outcome.SUCCESS,
        packages=(PackageUpdate("kernel", "x86_64", "0:1-1", "0:2-1", "baseos", ("RHSA-1",)),),
        security_state=SecurityState.known(1), current_reboot=CurrentRebootState.NOT_REQUIRED,
        reboot_forecast=RebootForecast.LIKELY,
    )


def test_model_serializes_normalized_success() -> None:
    encoded = result().to_dict()
    assert encoded["packages"][0]["security_advisory_ids"] == ["RHSA-1"]
    assert encoded["reboot_forecast"] == "likely"


def test_unknown_and_failures_require_explanations() -> None:
    with pytest.raises(ValueError):
        SecurityState.unknown("")
    with pytest.raises(ValueError):
        TargetResult(target(), "2026-09-18T18:58:00Z", Outcome.UNSUPPORTED)


def test_unknown_reboot_states_require_safe_explanations() -> None:
    with pytest.raises(ValueError):
        TargetResult(
            target(), "2026-09-18T18:58:00Z", Outcome.SUCCESS,
            current_reboot=CurrentRebootState.UNKNOWN, reboot_forecast=RebootForecast.NOT_INDICATED,
            current_reboot_explanation=None,
        )
    with pytest.raises(ValueError):
        TargetResult(
            target(), "2026-09-18T18:58:00Z", Outcome.SUCCESS,
            current_reboot=CurrentRebootState.NOT_REQUIRED, reboot_forecast=RebootForecast.UNKNOWN,
            reboot_forecast_explanation=None,
        )


def test_registry_round_trips_and_preserves_unknown_fields(tmp_path) -> None:
    path = tmp_path / "config" / "targets.toml"
    path.parent.mkdir()
    path.write_text('version = 1\nextra = "keep"\n\n[[targets]]\nid = "a"\nname = "A"\nssh_destination = "a@host"\nfuture = 1\n')
    registry = TargetRegistry(path)
    assert registry.load()[0].provider == "rpm"
    registry.save(target())
    content = path.read_text()
    assert 'extra = "keep"' in content and "future = 1" in content


def test_registry_rejects_duplicate_ids_without_rewriting(tmp_path) -> None:
    path = tmp_path / "targets.toml"
    content = 'version = 1\n\n[[targets]]\nid = "a"\nname = "A"\nssh_destination = "a@host"\n\n[[targets]]\nid = "a"\nname = "B"\nssh_destination = "b@host"\n'
    path.write_text(content)
    with pytest.raises(ValueError):
        TargetRegistry(path).load()
    assert path.read_text() == content


def test_registry_rejects_credential_fields_without_rewriting(tmp_path) -> None:
    path = tmp_path / "targets.toml"
    content = 'version = 1\n\n[[targets]]\nid = "a"\nname = "A"\nssh_destination = "a@host"\npassword = "not-allowed"\n'
    path.write_text(content)
    with pytest.raises(ValueError):
        TargetRegistry(path).load()
    assert path.read_text() == content


def test_registry_loads_valid_empty_registry(tmp_path) -> None:
    path = tmp_path / "targets.toml"
    path.write_text("version = 1\n")
    assert TargetRegistry(path).load() == []


def test_history_is_owner_only_and_ignores_malformed_records(tmp_path) -> None:
    store = HistoryStore(tmp_path / "state" / "history")
    run = InspectionRun("run-1", "2026-09-18T18:57:00Z", "2026-09-18T18:58:00Z", (result(),))
    store.append(run)
    record = next(store.path.iterdir())
    assert os.stat(record).st_mode & 0o777 == 0o600
    (store.path / "bad.json").write_text("not json")
    assert store.list_runs() == [run]
    assert store.warning is not None
    assert json.loads(record.read_text())["schema_version"] == 1

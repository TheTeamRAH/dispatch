from __future__ import annotations

import pytest
from textual.widgets import Static
from textual.widgets import Button, Input, SelectionList

from dispatch.models import (
    CurrentRebootState,
    Outcome,
    PackageUpdate,
    RebootForecast,
    SecurityState,
    TargetResult,
    TargetSnapshot,
)
from dispatch.transport import FailureKind, TransportFailure
from dispatch.tui import DispatchApp, PasswordPrompt, PreflightFailurePrompt, RemoveAllTargetsPrompt


def result() -> TargetResult:
    return TargetResult(
        target=TargetSnapshot(None, "operator@node", "operator@node"),
        discovered_at="2026-09-18T18:58:00Z",
        outcome=Outcome.SUCCESS,
        packages=(PackageUpdate("kernel", "x86_64", "1", "2", "baseos"),),
        security_state=SecurityState.known(0),
        current_reboot=CurrentRebootState.NOT_REQUIRED,
        reboot_forecast=RebootForecast.LIKELY,
    )


def displayed(app: DispatchApp) -> str:
    return str(app.query_one("#view", Static).render())


class History:
    def __init__(self) -> None:
        self.calls = 0

    def list_runs(self) -> list[object]:
        self.calls += 1
        return [type("Run", (), {"completed_at": "2026-09-18T18:58:00Z", "results": [result()]})()]


@pytest.mark.asyncio
async def test_initial_menu_is_idle_and_exposes_all_workflows() -> None:
    app = DispatchApp()

    async with app.run_test(size=(80, 24)) as pilot:
        assert app.discovery_started is False
        assert "Inspect one-off target" in displayed(app)
        assert "Inspect saved targets" in displayed(app)
        assert "Manage saved targets" in displayed(app)
        assert "View history" in displayed(app)
        await pilot.press("h")
        assert app.view == "history"


@pytest.mark.asyncio
async def test_history_view_reads_local_store_without_starting_discovery() -> None:
    history = History()
    app = DispatchApp(history_store=history)

    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("h")
        assert history.calls == 1
        assert "2026-09-18T18:58:00Z" in displayed(app)
        assert app.discovery_started is False


@pytest.mark.asyncio
async def test_summary_detail_toggle_and_resize_preserve_result() -> None:
    app = DispatchApp(results=[result()])

    async with app.run_test(size=(120, 40)) as pilot:
        assert "Pending updates: 1" in displayed(app)
        await pilot.press("d")
        assert app.show_details is True
        assert "kernel.x86_64" in displayed(app)
        await pilot.resize_terminal(40, 20)
        assert app.show_details is True
        assert "kernel.x86_64" in displayed(app)
        await pilot.resize_terminal(120, 40)
        assert app.results == [result()]


class Inspector:
    def __init__(self) -> None:
        self.targets = []

    async def inspect(self, targets, password_provider, failure_decider):
        self.targets = targets
        return type("Run", (), {"results": [result()]})()


class PromptingInspector(Inspector):
    async def inspect(self, targets, password_provider, failure_decider):
        self.targets = targets
        self.password = await password_provider(targets[0])
        return type("Run", (), {"results": [result()]})()


class BlockingInspector(Inspector):
    def __init__(self) -> None:
        self.started = __import__("asyncio").Event()
        self.release = __import__("asyncio").Event()

    async def inspect(self, targets, password_provider, failure_decider):
        self.targets = targets
        self.started.set()
        await self.release.wait()
        return type("Run", (), {"results": [result()]})()


class Registry:
    def __init__(self) -> None:
        self.targets = [TargetSnapshot("one", "One", "one@rocky"), TargetSnapshot("two", "Two", "two@rocky")]

    def load(self):
        return self.targets

    def save(self, target):
        self.targets.append(target)

    def edit(self, target):
        self.targets = [target if item.id == target.id else item for item in self.targets]

    def remove(self, target_id):
        self.targets = [item for item in self.targets if item.id != target_id]


@pytest.mark.asyncio
async def test_one_off_submission_explicitly_starts_inspection() -> None:
    inspector = Inspector()
    app = DispatchApp(inspection_service=inspector)

    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("o")
        destination = app.query_one("#ssh-destination", Input)
        await pilot.press(*"admin@rocky")
        assert destination.value == "admin@rocky"
        await pilot.press("enter")
        await pilot.pause()
        assert inspector.targets[0].ssh_destination == "admin@rocky"
        assert app.discovery_started is True
        assert app.view == "summary"


@pytest.mark.asyncio
async def test_saved_target_selection_starts_only_selected_targets() -> None:
    inspector = Inspector()
    app = DispatchApp(inspection_service=inspector, registry=Registry())

    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("s")
        selector = app.query_one("#saved-targets", SelectionList)
        selector.select("two")
        await pilot.click("#inspect-saved")
        await pilot.pause()
        assert [target.id for target in inspector.targets] == ["two"]


@pytest.mark.asyncio
async def test_saved_view_handles_empty_registry_without_a_selector() -> None:
    registry = Registry()
    registry.targets = []
    app = DispatchApp(registry=registry)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("s")
        assert "No saved targets" in displayed(app)
        assert list(app.query("#saved-targets")) == []


@pytest.mark.asyncio
async def test_manage_registry_changes_without_starting_discovery() -> None:
    registry = Registry()
    app = DispatchApp(registry=registry)

    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("m")
        target_id = app.query_one("#target-id", Input)
        await pilot.press(*"db")
        await pilot.press("tab")
        await pilot.press(*"Database")
        await pilot.press("tab")
        await pilot.press(*"admin@database")
        await pilot.click("#save-target")
        assert registry.targets[-1] == TargetSnapshot("db", "Database", "admin@database")
        assert app.discovery_started is False


@pytest.mark.asyncio
async def test_manage_lists_targets_and_requires_delete_to_remove_all() -> None:
    registry = Registry()
    app = DispatchApp(registry=registry)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("m")
        assert "one: One (one@rocky)" in displayed(app)
        await pilot.press("tab", "tab", "tab", "tab", "tab", "tab", "enter")
        await pilot.pause()
        assert isinstance(app.screen, RemoveAllTargetsPrompt)
        await pilot.press(*"DELETE", "enter")
        await pilot.pause()
        assert registry.targets == []


@pytest.mark.asyncio
async def test_password_prompt_masks_operator_input() -> None:
    app = DispatchApp()
    async with app.run_test(size=(80, 24)) as pilot:
        app.push_screen(PasswordPrompt(TargetSnapshot(None, "host", "admin@host")))
        await pilot.pause()
        assert app.screen.query_one(Input).password is True


@pytest.mark.asyncio
async def test_one_off_password_prompt_runs_from_inspection_worker() -> None:
    inspector = PromptingInspector()
    app = DispatchApp(inspection_service=inspector)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("o")
        await pilot.press(*"admin@rocky", "enter")
        await pilot.pause()
        assert isinstance(app.screen, PasswordPrompt)
        await pilot.press(*"temporary", "enter")
        await pilot.pause()
        assert inspector.password == "temporary"
        assert app.view == "summary"


@pytest.mark.asyncio
async def test_one_off_submission_immediately_shows_progress() -> None:
    inspector = BlockingInspector()
    app = DispatchApp(inspection_service=inspector)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("o")
        await pilot.press(*"admin@rocky", "enter")
        await inspector.started.wait()
        assert app.view == "progress"
        assert "Connecting" in displayed(app)
        inspector.release.set()


@pytest.mark.asyncio
async def test_preflight_failure_prompt_offers_explicit_decisions() -> None:
    app = DispatchApp()
    failure = TransportFailure(FailureKind.AUTHENTICATION, "Access denied.")
    async with app.run_test(size=(80, 24)) as pilot:
        app.push_screen(PreflightFailurePrompt(TargetSnapshot(None, "host", "admin@host"), failure))
        await pilot.pause()
        assert app.screen.query_one("#retry").label == "Retry"
        assert app.screen.query_one("#skip").label == "Skip"
        assert app.screen.query_one("#cancel").label == "Cancel batch"


@pytest.mark.parametrize("size", [(40, 20), (80, 24), (120, 40)])
def test_initial_menu_viewport_snapshot(snap_compare, size) -> None:
    assert snap_compare(DispatchApp(), terminal_size=size)

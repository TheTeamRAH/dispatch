"""Minimal responsive Textual presentation for Dispatch discovery results."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
import inspect
from typing import Protocol

from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.events import Resize
from textual.markup import escape
from textual.screen import ModalScreen
from textual.widgets import Button, Header, Input, Label, SelectionList, Static

from .models import CurrentRebootState, RebootForecast, TargetResult


class HistoryReader(Protocol):
    def list_runs(self) -> list[object]: ...


class PasswordPrompt(ModalScreen[str | None]):
    """Ephemeral, masked password collection for an already trusted host."""

    def __init__(self, target) -> None:
        super().__init__()
        self.target = target

    def compose(self) -> ComposeResult:
        with Container(id="dialog"):
            yield Label(f"Password for {self.target.name}")
            yield Input(password=True, id="password")

    def on_mount(self) -> None:
        self.query_one("#password", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def key_escape(self) -> None:
        self.dismiss(None)


class PreflightFailurePrompt(ModalScreen[str]):
    """Make batch retry/skip/cancel decisions visible and deliberate."""

    def __init__(self, target, failure) -> None:
        super().__init__()
        self.target = target
        self.failure = failure

    def compose(self) -> ComposeResult:
        with Container(id="dialog"):
            yield Label(f"{self.target.name}: {self.failure.explanation}")
            yield Button("Retry", id="retry")
            yield Button("Skip", id="skip")
            yield Button("Cancel batch", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id or "cancel")


class RemoveAllTargetsPrompt(ModalScreen[bool]):
    """Require an explicit typed acknowledgement before clearing the registry."""

    def compose(self) -> ComposeResult:
        with Container(id="dialog"):
            yield Label("Type DELETE to remove every saved target. Inspection history will remain.")
            yield Input(placeholder="DELETE", id="remove-all-confirm")

    def on_mount(self) -> None:
        self.query_one("#remove-all-confirm", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value == "DELETE")

    def key_escape(self) -> None:
        self.dismiss(False)


class DispatchApp(App[None]):
    """Idle menu and result views; workflows can supply normalized results."""

    CSS = """
    Screen { layout: vertical; background: #000000; color: #f0eaff; }
    Header { background: #000000; color: #f0eaff; }
    #workspace { height: 1fr; layout: vertical; padding: 1; }
    #pane-area { width: 1fr; height: 1fr; layout: horizontal; }
    #left-panes { width: 1fr; height: 100%; layout: vertical; margin-right: 1; }
    #navigation-pane, #content, #detail-pane, #status-pane {
        background: #121212;
        border: round #C45AFF;
        height: 100%;
        padding: 1;
    }
    #navigation-pane { width: 1fr; height: 3; margin: 0 0 1 0; padding: 0 1; }
    #content { width: 1fr; }
    #detail-pane { width: 24; }
    #detail { width: 1fr; }
    #navigation { width: 1fr; }
    #status-pane { display: none; width: 1fr; }
    .pane-main { border: round #C45AFF; }
    .status-success { color: #00FA9A; }
    .status-warning { color: #FFD700; }
    .status-error { color: #FF4500; }
    Input, SelectionList { border: round #A684E8; background: #000000; color: #f0eaff; }
    #content SelectionList { height: 2; }
    Input:focus, SelectionList:focus { border: round #C45AFF; }
    Button { background: #000000; color: #f0eaff; border: round #A684E8; }
    Button:focus { background: #000000; color: #FF69B4; border: round #C45AFF; }
    #left-panes { width: 38; }
    #content, #status-pane { height: 1fr; }
    #status-pane { display: block; margin-top: 1; }
    #detail-pane { width: 1fr; height: 1fr; }
    #navigation-pane, #content, #status-pane, #detail-pane {
        border-title-color: #A684E8;
        border-title-background: #121212;
        border-title-style: bold;
    }
    Screen.-compact #workspace { padding: 0; }
    Screen.-compact Header { display: none; }
    Screen.-compact #navigation-pane { height: 3; margin-bottom: 1; }
    Screen.-compact #pane-area { layout: vertical; }
    Screen.-compact #left-panes { width: 1fr; height: 1fr; margin: 0; }
    Screen.-compact #content { height: 1fr; }
    Screen.-compact #content SelectionList { height: 4; }
    Screen.-compact #status-pane, Screen.-compact #detail-pane { display: none; }
    PasswordPrompt, PreflightFailurePrompt, RemoveAllTargetsPrompt { align: center middle; background: #000000; }
    PasswordPrompt #dialog, PreflightFailurePrompt #dialog, RemoveAllTargetsPrompt #dialog { width: 70%; height: auto; padding: 1 2; background: #000000; border: round #C45AFF; }
    Screen.-narrow #dialog { width: 100%; }
    """
    BINDINGS = [
        ("o", "one_off", "One-off"),
        ("s", "saved", "Saved"),
        ("m", "manage", "Manage"),
        ("h", "history", "History"),
        ("d", "toggle_details", "Details"),
        ("escape", "menu", "Menu"),
    ]

    def __init__(self, results: Sequence[TargetResult] = (), history_store: HistoryReader | None = None, inspection_service=None, registry=None) -> None:
        super().__init__()
        self.results = list(results)
        self.view = "summary" if results else "menu"
        self.show_details = False
        self.discovery_started = False
        self.history_store = history_store
        self.history_runs: list[object] = []
        self.history_run = None
        self.inspection_worker = None
        self.inspection_service = inspection_service
        self.registry = registry
        self.saved_targets = []
        self.management_message = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="workspace"):
            navigation_pane = Static(self._navigation(), id="navigation-pane")
            navigation_pane.border_title = "Menu"
            yield navigation_pane
            with Container(id="pane-area"):
                with Container(id="left-panes"):
                    with VerticalScroll(id="content") as content_pane:
                        content_pane.border_title = "Current Action"
                        yield Static(self._content(), id="view")
                    status_pane = Static(self._status_content(), id="status-pane")
                    status_pane.border_title = "Return Status"
                    yield status_pane
                with VerticalScroll(id="detail-pane") as detail_pane:
                    detail_pane.border_title = "Detail"
                    yield Static(self._detail_content(), id="detail")

    def on_mount(self) -> None:
        self._apply_responsive_classes()
        self._refresh()

    async def action_one_off(self) -> None:
        await self._clear_controls()
        self.view = "one_off"
        self._refresh()
        destination = Input(placeholder="user@host or SSH alias", id="ssh-destination", classes="form-control")
        self.query_one("#content", VerticalScroll).mount(destination)
        self.set_focus(destination)

    async def action_saved(self) -> None:
        await self._clear_controls()
        self.view = "saved"
        self.saved_targets = self.registry.load() if self.registry is not None else []
        self._refresh()
        if not self.saved_targets:
            return
        choices = [(f"{target.name} ({target.ssh_destination})", target.id) for target in self.saved_targets]
        targets = SelectionList(*choices, id="saved-targets", classes="form-control")
        inspect_selected = Button("Inspect selected", id="inspect-saved", classes="form-control")
        self.query_one("#content", VerticalScroll).mount(targets, inspect_selected)
        self.set_focus(targets)

    async def action_manage(self) -> None:
        await self._clear_controls()
        self.view = "manage"
        self.saved_targets = self.registry.load() if self.registry is not None else []
        self._refresh()
        target_id = Input(placeholder="Target ID", id="target-id", classes="form-control")
        name = Input(placeholder="Display name", id="target-name", classes="form-control")
        destination = Input(placeholder="user@host or SSH alias", id="target-destination", classes="form-control")
        self.query_one("#content", VerticalScroll).mount(
            target_id, name, destination,
            Button("Save", id="save-target", classes="form-control"),
            Button("Edit", id="edit-target", classes="form-control"),
            Button("Remove", id="remove-target", classes="form-control"),
            Button("Remove all saved targets", id="remove-all-targets", classes="form-control"),
        )
        self.set_focus(target_id)

    async def action_history(self) -> None:
        await self._clear_controls()
        self.view = "history"
        self.history_runs = self.history_store.list_runs() if self.history_store is not None else []
        self._refresh()
        for index, run in enumerate(self.history_runs):
            await self.query_one("#content", VerticalScroll).mount(
                Button(f"View {run.completed_at}", id=f"history-run-{index}", classes="form-control")
            )

    async def action_menu(self) -> None:
        await self._clear_controls()
        self.view = "menu"
        self._refresh()

    def action_toggle_details(self) -> None:
        if self.results or self.history_run is not None:
            self.show_details = not self.show_details
            self._refresh()

    def on_resize(self, event: Resize) -> None:
        self._apply_responsive_classes()
        self._refresh()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if not event.value.strip():
            return
        from .models import TargetSnapshot

        if event.input.id == "ssh-destination":
            targets = [TargetSnapshot(None, event.value.strip(), event.value.strip())]
        else:
            return
        if self.inspection_service is None:
            return
        await self._start_inspection(targets)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-inspection":
            if self.inspection_worker is not None:
                self.inspection_worker.cancel()
            return
        if event.button.id and event.button.id.startswith("history-run-"):
            self.history_run = self.history_runs[int(event.button.id.removeprefix("history-run-"))]
            await self._clear_controls()
            self.view = "history_detail"
            self.show_details = False
            self._refresh()
            return
        if event.button.id == "remove-all-targets":
            self.run_worker(self._remove_all_targets(), exclusive=True)
            return
        if event.button.id in {"save-target", "edit-target", "remove-target"}:
            self._manage_target(event.button.id)
            return
        if event.button.id != "inspect-saved" or self.inspection_service is None:
            return
        selected = set(self.query_one("#saved-targets", SelectionList).selected)
        targets = [target for target in self.saved_targets if target.id in selected]
        if targets:
            await self._start_inspection(targets)

    async def _remove_all_targets(self) -> None:
        if self.registry is None:
            return
        if not await self.push_screen_wait(RemoveAllTargetsPrompt()):
            return
        for target in self.registry.load():
            self.registry.remove(target.id)
        self.saved_targets = []
        self.management_message = "Removed all saved targets. Inspection history remains."
        self._refresh()

    def _manage_target(self, action: str) -> None:
        if self.registry is None:
            self.management_message = "Target registry is unavailable."
            self._refresh()
            return
        target_id = self.query_one("#target-id", Input).value.strip()
        try:
            if action == "remove-target":
                self.registry.remove(target_id)
                self.management_message = f"Removed {target_id}."
            else:
                from .models import TargetSnapshot

                target = TargetSnapshot(target_id, self.query_one("#target-name", Input).value.strip(), self.query_one("#target-destination", Input).value.strip())
                if action == "save-target":
                    self.registry.save(target)
                    self.management_message = f"Saved {target.name}."
                else:
                    self.registry.edit(target)
                    self.management_message = f"Updated {target.name}."
            self.saved_targets = self.registry.load()
        except ValueError as error:
            self.management_message = str(error)
        self._refresh()

    async def _start_inspection(self, targets) -> None:
        self.discovery_started = True
        self.results = []
        await self._clear_controls()
        self.view = "progress"
        self._refresh()
        await self.query_one("#content", VerticalScroll).mount(
            Button("Cancel batch", id="cancel-inspection", classes="form-control")
        )
        self.inspection_worker = self.run_worker(self._inspect(targets), exclusive=True)

    async def _clear_controls(self) -> None:
        for control in self.query(".form-control"):
            await control.remove()

    async def _inspect(self, targets) -> None:
        method = self.inspection_service.inspect
        arguments = (targets, self._password_not_available, self._skip_failure)
        try:
            if "on_result" in inspect.signature(method).parameters:
                run = await method(*arguments, on_result=self._result_completed)
            else:
                run = await method(*arguments)
        except asyncio.CancelledError:
            self.view = "summary"
            self._refresh()
            raise
        else:
            self.results = list(run.results)
            self.view = "summary"
            self._refresh()
        finally:
            await self._clear_controls()
            self.inspection_worker = None

    async def _password_not_available(self, target) -> str | None:
        return await self.push_screen_wait(PasswordPrompt(target))

    async def _skip_failure(self, target, failure) -> str:
        return await self.push_screen_wait(PreflightFailurePrompt(target, failure))

    def _result_completed(self, result: TargetResult) -> None:
        self.results.append(result)
        if self.view == "progress":
            self._refresh()

    def _refresh(self) -> None:
        self.query_one("#view", Static).update(self._content())
        self.query_one("#navigation-pane", Static).update(self._navigation())
        self.query_one("#detail", Static).update(self._detail_content())
        self.query_one("#status-pane", Static).update(self._status_content())
        status_class = self._status_class()
        self.query_one("#view", Static).set_classes("")
        self.query_one("#detail", Static).set_classes(status_class)

    def _apply_responsive_classes(self) -> None:
        self.screen.set_class(self.size.width <= 50, "-narrow")
        self.screen.set_class(self._is_compact(), "-compact")

    def _is_compact(self) -> bool:
        return self.size.width <= 60 or self.size.height <= 30

    def _navigation(self) -> str:
        actions = (
            ("o", "one_off", "One-off"),
            ("s", "saved", "Saved"),
            ("m", "manage", "Manage"),
            ("h", "history", "History"),
        )
        return "  ".join(f"[#A684E8]{key}[/] {label}" for key, _, label in actions)

    def _detail_content(self) -> str:
        return self._main_content()

    def _status_content(self) -> str:
        results = self.history_run.results if self.view == "history_detail" and self.history_run is not None else self.results
        if results:
            result = results[-1]
            return f"RETURN STATUS\n\n{result.target.name}: {result.outcome.value}"
        if self.management_message:
            return f"RETURN STATUS\n\n{self.management_message}"
        return f"RETURN STATUS\n\n{self.view.replace('_', ' ').title()} ready."

    def _status_class(self) -> str:
        if self.view not in {"summary", "progress", "history_detail"}:
            return ""
        results = self.history_run.results if self.view == "history_detail" and self.history_run is not None else self.results
        if any(result.outcome.value != "success" for result in results):
            if all(result.outcome.value in {"skipped", "cancelled"} for result in results):
                return "status-warning"
            return "status-error"
        if self.view == "progress" or any(
            result.security_state.state == "unknown"
            or result.current_reboot is CurrentRebootState.UNKNOWN
            or result.reboot_forecast in {RebootForecast.LIKELY, RebootForecast.UNKNOWN}
            for result in results
        ):
            return "status-warning"
        if results:
            return "status-success"
        return ""

    def _content(self) -> str:
        if self._is_compact() and self.view in {"menu", "summary", "progress", "history_detail"}:
            return self._main_content()
        return self._posting_context()

    def _posting_context(self) -> str:
        labels = {
            "menu": "Choose a top-menu action.",
            "one_off": "Enter a target below.",
            "saved": "Select targets below.",
            "manage": "Manage targets below.",
            "history": "Select a persisted run below.",
            "history_detail": "Detailed history is on the right.",
            "progress": "Inspection progress is on the right.",
            "summary": "Detailed results are on the right.",
        }
        return labels[self.view]

    def _main_content(self) -> str:
        if self.view == "menu":
            return "Dispatch\n\nInspect one-off target [o]\nInspect saved targets [s]\nManage saved targets [m]\nView history [h]\n\nRead-only RPM update discovery."
        if self.view == "one_off":
            return "Inspect one-off target\n\nEnter an OpenSSH alias or user@host destination.\n\nPress Esc to return to the menu."
        if self.view == "saved":
            targets = "\n".join(f"{target.id}: {target.name} ({target.ssh_destination})" for target in self.saved_targets) or "No saved targets."
            return f"Inspect saved targets\n\n{targets}\n\nEnter one or more target IDs. Press Esc to return to the menu."
        if self.view == "manage":
            message = f"\n\n{self.management_message}" if self.management_message else ""
            targets = "\n".join(f"{target.id}: {target.name} ({target.ssh_destination})" for target in self.saved_targets) or "No saved targets."
            return f"Manage saved targets\n\nSaved targets:\n{targets}\n\nEnter ID, display name, and destination to save or edit. Enter only ID to remove.{message}\n\nPress Esc to return to the menu."
        if self.view == "history":
            if not self.history_runs:
                return "Inspection history\n\nNo local history loaded.\n\nPress Esc to return to the menu."
            lines = ["Inspection history", ""]
            for run in self.history_runs:
                lines.append(f"{run.completed_at}: {len(run.results)} target(s)")
            lines.append("\nPress Esc to return to the menu.")
            return "\n".join(lines)
        if self.view == "history_detail":
            return self._summary(self.history_run.results, "Inspection history")
        if self.view == "progress":
            return self._summary(self.results, "Inspection in progress") + "\n\nConnecting and querying the selected target(s). No remote changes will be made."
        return self._summary(self.results)

    def _summary(self, results=None, title="Discovery summary") -> str:
        results = self.results if results is None else results
        if not results:
            return "Discovery summary\n\nNo completed target results."
        lines = [title]
        host_accents = ("#A684E8", "#79C0FF", "#FFB86C", "#FF69B4")
        multi_host = len(results) > 1
        for index, result in enumerate(results):
            outcome_color = "#00FA9A" if result.outcome.value == "success" else "#FFD700" if result.outcome.value in {"skipped", "cancelled"} else "#FF4500"
            host_header = f"{escape(result.target.name)}: {result.outcome.value}"
            if multi_host:
                host_header = f"[bold {host_accents[index % len(host_accents)]}]{host_header}[/]"
            security_color = "#79C0FF" if result.security_state.state == "known" else "#FFD700"
            current_reboot_color = "#00FA9A" if result.current_reboot is CurrentRebootState.NOT_REQUIRED else "#FFD700"
            forecast_color = "#00FA9A" if result.reboot_forecast is RebootForecast.NOT_INDICATED else "#FFD700"
            lines.extend(
                [
                    f"\n{host_header}",
                    f"[{outcome_color}]Outcome: {result.outcome.value}[/]",
                    f"[#A684E8]Pending updates: {len(result.packages)}[/]",
                    f"[{security_color}]Security: {result.security_state.state}" + (
                        f" ({result.security_state.count})" if result.security_state.count is not None else ""
                    ) + "[/]",
                    f"[{current_reboot_color}]Current reboot: {result.current_reboot.value}[/]",
                    f"[{forecast_color}]Post-update reboot forecast: {result.reboot_forecast.value}[/]",
                ]
            )
            if result.explanation:
                lines.append(f"Result: {result.explanation}")
            if result.current_reboot is CurrentRebootState.UNKNOWN:
                lines.append(f"Current reboot detail: {result.current_reboot_explanation}")
            if result.reboot_forecast is RebootForecast.UNKNOWN:
                lines.append(f"Forecast detail: {result.reboot_forecast_explanation}")
            if self.show_details:
                lines.append("Package details:")
                package_color = host_accents[index % len(host_accents)] if multi_host else "#A684E8"
                lines.extend(f"[{package_color}]{escape(package.name)}.{escape(package.architecture)} {escape(package.installed_evr)} -> {escape(package.candidate_evr)}[/]" for package in result.packages)
        lines.append("\nPress d to toggle package details.")
        return "\n".join(lines)

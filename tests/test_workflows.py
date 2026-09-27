from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from dispatch.workflow_models import ShellStep, WorkflowDefinition
from dispatch.workflow_stores import WorkflowRegistry, WorkflowHistoryStore
from dispatch.workflow_service import ShellWorkflowExecutor, WorkflowService
from dispatch.transport import CompletedCommand
from dispatch.models import TargetSnapshot


def workflow() -> WorkflowDefinition:
    return WorkflowDefinition(
        id="deploy",
        name="Deploy",
        workflow_type="shell",
        session="persistent",
        startup=(ShellStep("aliases", "Load aliases", "shopt -s expand_aliases"),),
        steps=(ShellStep("run", "Run deploy", "deploy_app"),),
    )


def test_registry_uses_one_file_per_workflow_and_preserves_unknown_fields(tmp_path: Path) -> None:
    directory = tmp_path / "workflows"
    directory.mkdir()
    path = directory / "deploy.toml"
    path.write_text(
        'version = 1\nid = "deploy"\nname = "Deploy"\ntype = "shell"\nsession = "isolated"\nfuture = "keep"\n\n[[steps]]\nid = "one"\nname = "One"\ncommand = "true"\nextra = 3\n'
    )
    registry = WorkflowRegistry(directory)

    loaded = registry.load()
    assert loaded[0].id == "deploy"
    registry.save(workflow())

    assert path.read_text().find('future = "keep"') >= 0
    assert (directory / "deploy.toml").exists()
    assert len(list(directory.glob("*.toml"))) == 1


def test_registry_rejects_filename_id_mismatch_without_rewriting(tmp_path: Path) -> None:
    directory = tmp_path / "workflows"
    directory.mkdir()
    path = directory / "wrong.toml"
    content = 'version = 1\nid = "deploy"\nname = "Deploy"\ntype = "shell"\nsession = "isolated"\n\n[[steps]]\nid = "one"\nname = "One"\ncommand = "true"\n'
    path.write_text(content)

    with pytest.raises(ValueError, match="filename"):
        WorkflowRegistry(directory).load()
    assert path.read_text() == content


@pytest.mark.asyncio
async def test_persistent_executor_preserves_order_and_stops_after_failure() -> None:
    class Session:
        def __init__(self) -> None:
            self.commands: list[str] = []

        async def run(self, command: str) -> CompletedCommand:
            self.commands.append(command)
            if command == "deploy_app":
                return CompletedCommand(2, "out", "failed")
            return CompletedCommand(0, "", "")

        async def close(self) -> None:
            pass

    session = Session()
    definition = WorkflowDefinition(
        "deploy", "Deploy", "shell", "persistent",
        (ShellStep("setup", "Setup", "setup"),),
        (ShellStep("deploy", "Deploy", "deploy_app"), ShellStep("done", "Done", "done")),
    )
    result = await ShellWorkflowExecutor().execute(definition, TargetSnapshot("one", "One", "one@host"), session)

    assert session.commands == ["setup", "deploy_app"]
    assert [step.outcome for step in result.steps] == ["success", "failed", "skipped"]


@pytest.mark.asyncio
async def test_workflow_history_round_trips_with_bounded_output(tmp_path: Path) -> None:
    store = WorkflowHistoryStore(tmp_path / "history", output_limit=5)
    session = type("Session", (), {
        "run": lambda self, command: asyncio.sleep(0, result=CompletedCommand(0, "123456", "")),
        "close": lambda self: asyncio.sleep(0),
    })()
    definition = WorkflowDefinition("x", "X", "shell", "isolated", (), (ShellStep("s", "S", "true"),))
    result = await ShellWorkflowExecutor(output_limit=5).execute(definition, TargetSnapshot("one", "One", "one@host"), session)
    run = {"workflow": definition.to_dict(), "target_results": [result.to_dict()]}
    store.append(run)
    loaded = store.list_runs()
    assert loaded[0]["target_results"][0]["steps"][0]["stdout"] == "12345"


@pytest.mark.asyncio
async def test_workflow_service_persists_each_completed_run(tmp_path: Path) -> None:
    class Connection:
        connection = object()

    class Transport:
        async def connect(self, target, password_provider):
            return Connection()

        async def open_bash_session(self, connected):
            class Session:
                async def run(self, command):
                    return CompletedCommand(0, "ok", "")

                async def close(self):
                    pass

            return Session()

        async def run(self, channel, command):
            return CompletedCommand(0, "ok", "")

        async def close(self, connected):
            pass

    store = WorkflowHistoryStore(tmp_path / "history")
    service = WorkflowService(Transport(), store)
    target = TargetSnapshot("one", "One", "one@host")
    results = await service.run(workflow(), [target], lambda: None)

    assert len(results) == 1
    runs = store.list_runs()
    assert len(runs) == 1
    assert runs[0]["workflow"]["id"] == "deploy"
    assert runs[0]["target_results"][0]["outcome"] == "success"




@pytest.mark.asyncio
async def test_executor_reports_non_terminating_commands(tmp_path: Path) -> None:
    class Session:
        async def run(self, command):
            await asyncio.sleep(1)

        async def close(self):
            pass

    definition = WorkflowDefinition("hang", "Hang", "shell", "isolated", (), (ShellStep("step", "Step", "hang"),))
    result = await ShellWorkflowExecutor(command_timeout=0.01).execute(definition, TargetSnapshot("one", "One", "one@host"), Session())

    assert result.outcome == "failed"
    assert "timed out" in result.steps[0].explanation

@pytest.mark.asyncio
async def test_workflow_service_reports_connection_failures_to_ui(tmp_path: Path) -> None:
    class Failure:
        explanation = "SSH connection refused"

    class Transport:
        async def connect(self, target, password_provider):
            return Failure()

    reported = []
    store = WorkflowHistoryStore(tmp_path / "history")
    service = WorkflowService(Transport(), store)
    result = await service.run(
        workflow(),
        [TargetSnapshot("one", "One", "one@host")],
        lambda: None,
        on_result=reported.append,
    )

    assert result[0].outcome == "failed"
    assert reported[0].explanation == "SSH connection refused"
    assert store.list_runs()[0]["target_results"][0]["explanation"] == "SSH connection refused"

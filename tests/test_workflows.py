from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from dispatch.workflow_models import ShellStep, WorkflowDefinition
from dispatch.workflow_stores import WorkflowRegistry, WorkflowHistoryStore
from dispatch.workflow_service import ShellWorkflowExecutor
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
    assert json.loads(next((tmp_path / "history").glob("*.json")).read_text())

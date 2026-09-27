"""Execution of registered remote Bash workflows."""

from __future__ import annotations

import inspect
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Protocol

from .models import TargetSnapshot
from .transport import CompletedCommand
from .workflow_models import ShellStep, StepResult, WorkflowDefinition, WorkflowTargetResult

OUTPUT_LIMIT = 100_000


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class CommandSession(Protocol):
    async def run(self, command: str) -> CompletedCommand: ...

    async def close(self) -> None: ...


class ShellWorkflowExecutor:
    """Run ordered startup and shell commands for one target."""

    def __init__(self, output_limit: int = OUTPUT_LIMIT) -> None:
        self.output_limit = output_limit

    async def execute(self, workflow: WorkflowDefinition, target: TargetSnapshot, session: CommandSession) -> WorkflowTargetResult:
        results: list[StepResult] = []
        failed = False
        for step in (*workflow.startup, *workflow.steps):
            if failed:
                results.append(self._skipped(step))
                continue
            result = await self._run_step(step, session)
            results.append(result)
            failed = result.outcome != "success"
        outcome = "success" if not failed else "failed"
        return WorkflowTargetResult(workflow.id, workflow.name, workflow.session, asdict(target), outcome, tuple(results))

    async def _run_step(self, step: ShellStep, session: CommandSession) -> StepResult:
        started = _timestamp()
        try:
            completed = await session.run(step.command)
        except Exception as error:
            return StepResult(step.id, step.name, "failed", started, _timestamp(), None, "", "", f"Command execution failed: {error}")
        return StepResult(
            step.id, step.name, "success" if completed.exit_status == 0 else "failed",
            started, _timestamp(), completed.exit_status,
            completed.stdout[: self.output_limit], completed.stderr[: self.output_limit],
            None if completed.exit_status == 0 else f"Command exited with status {completed.exit_status}.",
        )

    @staticmethod
    def _skipped(step: ShellStep) -> StepResult:
        now = _timestamp()
        return StepResult(step.id, step.name, "skipped", now, now, None, "", "", "Skipped after an earlier step failed.")


class _IsolatedSession:
    def __init__(self, transport, channel) -> None:
        self.transport = transport
        self.channel = channel

    async def run(self, command: str) -> CompletedCommand:
        return await self.transport.run(self.channel, command)

    async def close(self) -> None:
        pass


class WorkflowService:
    """Coordinate one registered workflow across selected SSH targets."""

    def __init__(self, transport, history_store, executor: ShellWorkflowExecutor | None = None) -> None:
        self.transport = transport
        self.history_store = history_store
        self.executor = executor or ShellWorkflowExecutor()

    async def run(self, workflow: WorkflowDefinition, targets, password_provider, on_result=None) -> list[WorkflowTargetResult]:
        from .workflow import run_batch

        async def run_target(target: TargetSnapshot) -> WorkflowTargetResult:
            connected = await self.transport.connect(target, password_provider)
            if not hasattr(connected, "connection"):
                return WorkflowTargetResult(workflow.id, workflow.name, workflow.session, asdict(target), "failed", (), connected.explanation)
            session = await self.transport.open_bash_session(connected) if workflow.session == "persistent" else _IsolatedSession(self.transport, connected)
            try:
                result = await self.executor.execute(workflow, target, session)
                if on_result is not None:
                    callback = on_result(result)
                    if inspect.isawaitable(callback):
                        await callback
                return result
            finally:
                await session.close()
                await self.transport.close(connected)

        results = await run_batch(targets, run_target)
        self.history_store.append({"workflow": workflow.to_dict(), "target_results": [result.to_dict() for result in results]})
        return results

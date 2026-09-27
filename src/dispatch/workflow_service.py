"""Execution of registered remote Bash workflows."""

from __future__ import annotations

import asyncio
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
    async def run(self, command: str, on_output=None) -> CompletedCommand: ...

    async def close(self) -> None: ...


class ShellWorkflowExecutor:
    """Run ordered startup and shell commands for one target."""

    def __init__(self, output_limit: int = OUTPUT_LIMIT, command_timeout: float | None = None) -> None:
        self.output_limit = output_limit
        self.command_timeout = command_timeout

    async def execute(self, workflow: WorkflowDefinition, target: TargetSnapshot, session: CommandSession, on_step=None, on_output=None) -> WorkflowTargetResult:
        results: list[StepResult] = []
        failed = False
        for step in (*workflow.startup, *workflow.steps):
            if failed:
                skipped = self._skipped(step)
                results.append(skipped)
                if on_step is not None:
                    callback = on_step(target, step, skipped)
                    if inspect.isawaitable(callback):
                        await callback
                continue
            if on_step is not None:
                callback = on_step(target, step, None)
                if inspect.isawaitable(callback):
                    await callback
            result = await self._run_step(step, session, on_output, target)
            results.append(result)
            if on_step is not None:
                callback = on_step(target, step, result)
                if inspect.isawaitable(callback):
                    await callback
            failed = result.outcome != "success"
        outcome = "success" if not failed else "failed"
        return WorkflowTargetResult(workflow.id, workflow.name, workflow.session, asdict(target), outcome, tuple(results))

    async def _run_step(self, step: ShellStep, session: CommandSession, on_output=None, target=None) -> StepResult:
        started = _timestamp()
        try:
            callback = (lambda line: on_output(target, step, line)) if on_output is not None and target is not None else None
            if "on_output" in inspect.signature(session.run).parameters:
                pending = session.run(step.command, callback)
            else:
                pending = session.run(step.command)
            completed = await asyncio.wait_for(pending, timeout=self.command_timeout) if self.command_timeout is not None else await pending
        except asyncio.TimeoutError:
            return StepResult(step.id, step.name, "failed", started, _timestamp(), None, "", "", f"Command timed out after {self.command_timeout:g} seconds. The command may require interactive input or may not terminate.")
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

    async def run(self, command: str, on_output=None) -> CompletedCommand:
        return await self.transport.run(self.channel, command)

    async def close(self) -> None:
        pass


class WorkflowService:
    """Coordinate one registered workflow across selected SSH targets."""

    def __init__(self, transport, history_store, executor: ShellWorkflowExecutor | None = None) -> None:
        self.transport = transport
        self.history_store = history_store
        self.executor = executor or ShellWorkflowExecutor()

    async def run(self, workflow: WorkflowDefinition, targets, password_provider, on_result=None, on_progress=None, on_output=None) -> list[WorkflowTargetResult]:
        from .workflow import run_batch

        async def run_target(target: TargetSnapshot) -> WorkflowTargetResult:
            connected = await self.transport.connect(target, password_provider)
            if not hasattr(connected, "connection"):
                result = WorkflowTargetResult(workflow.id, workflow.name, workflow.session, asdict(target), "failed", (), connected.explanation)
                if on_result is not None:
                    callback = on_result(result)
                    if inspect.isawaitable(callback):
                        await callback
                return result
            session = await self.transport.open_bash_session(connected) if workflow.session == "persistent" else _IsolatedSession(self.transport, connected)
            try:
                result = await self.executor.execute(workflow, target, session, on_progress, on_output)
                if on_result is not None:
                    callback = on_result(result)
                    if inspect.isawaitable(callback):
                        await callback
                return result
            finally:
                await session.close()
                await self.transport.close(connected)

        results: list[WorkflowTargetResult] = []
        status = "running"
        run_record = {"status": status, "workflow": workflow.to_dict(), "target_results": []}
        history_handle = self.history_store.begin(run_record) if hasattr(self.history_store, "begin") else None
        try:
            results = await run_batch(targets, run_target)
            status = "completed"
        except asyncio.CancelledError:
            status = "cancelled"
            raise
        except Exception:
            status = "failed"
            raise
        finally:
            run_record = {"status": status, "workflow": workflow.to_dict(), "target_results": [result.to_dict() for result in results]}
            if history_handle is not None:
                self.history_store.finish(history_handle, run_record)
            else:
                self.history_store.append(run_record)
        return results

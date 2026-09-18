from __future__ import annotations

from dataclasses import dataclass

import pytest

from dispatch.inspection import InspectionService
from dispatch.models import Outcome, TargetSnapshot
from dispatch.transport import FailureKind, TransportFailure


@dataclass
class Channel:
    target: TargetSnapshot


class Transport:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.closed = []

    async def connect(self, target, password_provider):
        outcome = self.outcomes.pop(0)
        return outcome if isinstance(outcome, TransportFailure) else Channel(target)

    async def run(self, channel, command):
        from dispatch.rpm import CompletedCommand
        if "command -v" in command:
            return CompletedCommand(1, "")
        raise AssertionError(command)

    async def close(self, channel):
        self.closed.append(channel.target)


class History:
    def __init__(self):
        self.runs = []

    def append(self, run):
        self.runs.append(run)


class BlockingProvider:
    def __init__(self) -> None:
        self.started = __import__("asyncio").Event()

    async def discover(self, target, channel):
        self.started.set()
        await __import__("asyncio").Event().wait()


async def no_password(target):
    return None


@pytest.mark.asyncio
async def test_one_off_failure_is_persisted_and_never_runs_provider() -> None:
    target = TargetSnapshot(None, "host", "user@host")
    history = History()
    service = InspectionService(Transport([TransportFailure(FailureKind.CONNECTION, "offline")]), history)

    run = await service.inspect([target], no_password, lambda target, failure: "skip")

    assert run.results[0].outcome is Outcome.SKIPPED
    assert history.runs == [run]


@pytest.mark.asyncio
async def test_preflight_retry_then_runs_successful_targets_concurrently() -> None:
    first = TargetSnapshot("one", "One", "one@host")
    second = TargetSnapshot("two", "Two", "two@host")
    history = History()
    service = InspectionService(
        Transport([TransportFailure(FailureKind.AUTHENTICATION, "denied"), object(), object()]), history
    )
    decisions = []

    async def decide(target, failure):
        decisions.append(target.id)
        return "retry"

    run = await service.inspect([first, second], no_password, decide)

    assert decisions == ["one"]
    assert [result.outcome for result in run.results] == [Outcome.UNSUPPORTED, Outcome.UNSUPPORTED]
    assert history.runs == [run]


@pytest.mark.asyncio
async def test_cancel_records_unstarted_target_as_cancelled() -> None:
    first = TargetSnapshot("one", "One", "one@host")
    second = TargetSnapshot("two", "Two", "two@host")
    service = InspectionService(Transport([TransportFailure(FailureKind.CONNECTION, "offline")]), History())

    run = await service.inspect([first, second], no_password, lambda target, failure: "cancel")

    assert [result.outcome for result in run.results] == [Outcome.CONNECTION_FAILED, Outcome.CANCELLED]


@pytest.mark.asyncio
async def test_task_cancellation_closes_channels_and_persists_cancelled_results() -> None:
    import asyncio

    target = TargetSnapshot("one", "One", "one@host")
    transport = Transport([object()])
    history = History()
    provider = BlockingProvider()
    task = asyncio.create_task(InspectionService(transport, history, provider).inspect([target], no_password, lambda target, failure: "skip"))
    await provider.started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert history.runs[0].results[0].outcome is Outcome.CANCELLED
    assert transport.closed == [target]

"""Operator-invoked preflight, discovery, and durable inspection runs."""

from __future__ import annotations

import inspect
import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from .models import Outcome, TargetResult, TargetSnapshot
from .rpm import RpmProvider
from .transport import FailureKind, TransportFailure
from .workflow import run_batch


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class _CommandChannel:
    def __init__(self, transport, channel) -> None:
        self.transport = transport
        self.channel = channel

    async def run(self, command):
        return await self.transport.run(self.channel, command)


class InspectionService:
    """Coordinates serial authentication preflight and parallel RPM discovery."""

    def __init__(self, transport, history_store, provider=None) -> None:
        self.transport = transport
        self.history_store = history_store
        self.provider = provider or RpmProvider()

    async def inspect(self, targets, password_provider, failure_decider):
        from .models import InspectionRun

        started_at = _timestamp()
        results: list[TargetResult | None] = [None] * len(targets)
        connected: list[tuple[int, TargetSnapshot, object]] = []
        closed_channels: set[int] = set()
        cancelled = False
        for index, target in enumerate(targets):
            while True:
                connected_or_failure = await self.transport.connect(target, password_provider)
                if not isinstance(connected_or_failure, TransportFailure):
                    connected.append((index, target, connected_or_failure))
                    break
                decision = failure_decider(target, connected_or_failure)
                if inspect.isawaitable(decision):
                    decision = await decision
                if decision == "retry":
                    continue
                results[index] = self._failure(target, connected_or_failure, decision == "skip")
                if decision == "cancel":
                    cancelled = True
                break
            if cancelled:
                for remaining_index, remaining in enumerate(targets[index + 1 :], index + 1):
                    results[remaining_index] = self._cancelled(remaining)
                break
        if not cancelled:
            async def discover(entry):
                index, target, channel = entry
                try:
                    return index, await self.provider.discover(target, _CommandChannel(self.transport, channel))
                finally:
                    await self.transport.close(channel)
                    closed_channels.add(id(channel))

            try:
                for index, result in await run_batch(connected, discover):
                    results[index] = result
            except asyncio.CancelledError:
                for _, target, channel in connected:
                    if id(channel) not in closed_channels:
                        await self.transport.close(channel)
                for index, target in enumerate(targets):
                    if results[index] is None:
                        results[index] = self._cancelled(target)
                run = InspectionRun(str(uuid4()), started_at, _timestamp(), tuple(results))
                self.history_store.append(run)
                raise
        else:
            for _, _, channel in connected:
                await self.transport.close(channel)
        run = InspectionRun(str(uuid4()), started_at, _timestamp(), tuple(result for result in results if result is not None))
        self.history_store.append(run)
        return run

    @staticmethod
    def _failure(target, failure, skipped):
        if skipped:
            return TargetResult(target, _timestamp(), Outcome.SKIPPED, explanation=f"Skipped after {failure.explanation}")
        return TargetResult(target, _timestamp(), Outcome(failure.kind.value), explanation=failure.explanation)

    @staticmethod
    def _cancelled(target):
        return TargetResult(target, _timestamp(), Outcome.CANCELLED, explanation="Inspection batch was cancelled.")

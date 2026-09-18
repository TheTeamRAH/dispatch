from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from dispatch.models import CurrentRebootState, Outcome, RebootForecast, TargetSnapshot
from dispatch.rpm import CompletedCommand, RpmProvider
from dispatch.workflow import run_batch


FIXTURES = Path(__file__).parent / "fixtures"


class Channel:
    def __init__(self, replies):
        self.replies = replies
        self.commands = []

    async def run(self, command):
        self.commands.append(command)
        return self.replies.pop(0)


@pytest.mark.asyncio
async def test_dnf_updates_are_success_and_security_is_correlated() -> None:
    channel = Channel([
        CompletedCommand(0, "/usr/bin/dnf\n"),
        CompletedCommand(100, (FIXTURES / "check-update-updates.txt").read_text()),
        CompletedCommand(0, "kernel-core\t0:5.14.0-500.el9\tx86_64\nbash\t0:5.1.8-9.el9\tx86_64\n"),
        CompletedCommand(0, (FIXTURES / "updateinfo-security.txt").read_text()),
        CompletedCommand(1, ""),
    ])
    result = await RpmProvider().discover(TargetSnapshot(None, "host", "admin@host"), channel)
    assert result.outcome is Outcome.SUCCESS
    assert result.security_state.count == 1
    assert result.current_reboot is CurrentRebootState.REQUIRED
    assert result.reboot_forecast is RebootForecast.LIKELY
    assert result.packages[0].security_advisory_ids == ("RHSA-2026:1234",)
    assert channel.commands[1] == "LC_ALL=C dnf -q --color=never check-update"


@pytest.mark.asyncio
async def test_no_supported_tool_is_not_zero_updates() -> None:
    result = await RpmProvider().discover(TargetSnapshot(None, "host", "admin@host"), Channel([CompletedCommand(1, "")]))
    assert result.outcome is Outcome.UNSUPPORTED


@pytest.mark.asyncio
async def test_no_updates_ignores_locale_c_metadata_banner() -> None:
    channel = Channel([
        CompletedCommand(0, "/usr/bin/dnf\n"),
        CompletedCommand(0, (FIXTURES / "check-update-no-updates.txt").read_text()),
        CompletedCommand(0, ""), CompletedCommand(0, ""), CompletedCommand(0, ""),
    ])
    result = await RpmProvider().discover(TargetSnapshot(None, "host", "admin@host"), channel)
    assert result.outcome is Outcome.SUCCESS
    assert result.packages == ()
    assert result.security_state.count == 0


@pytest.mark.asyncio
async def test_unknown_security_does_not_fail_package_discovery() -> None:
    channel = Channel([
        CompletedCommand(0, "/usr/bin/yum\n"), CompletedCommand(0, ""),
        CompletedCommand(0, ""), CompletedCommand(127, ""), CompletedCommand(0, ""),
    ])
    result = await RpmProvider().discover(TargetSnapshot(None, "host", "admin@host"), channel)
    assert result.outcome is Outcome.SUCCESS
    assert result.security_state.state == "unknown"
    assert result.reboot_forecast is RebootForecast.NOT_INDICATED


@pytest.mark.asyncio
async def test_unmatched_security_advisory_is_unknown_not_zero() -> None:
    channel = Channel([
        CompletedCommand(0, "/usr/bin/dnf\n"),
        CompletedCommand(100, "bash.x86_64 5.1.8-10.el9 baseos\n"),
        CompletedCommand(0, "bash\t0:5.1.8-9.el9\tx86_64\n"),
        CompletedCommand(0, (FIXTURES / "updateinfo-unmatched.txt").read_text()),
        CompletedCommand(0, ""),
    ])
    result = await RpmProvider().discover(TargetSnapshot(None, "host", "admin@host"), channel)
    assert result.outcome is Outcome.SUCCESS
    assert result.security_state.state == "unknown"
    assert result.security_state.count is None


@pytest.mark.asyncio
async def test_batch_never_exceeds_ten_active_queries() -> None:
    active = maximum = 0

    async def discover(target):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.01)
        active -= 1
        return target

    targets = list(range(25))
    assert await run_batch(targets, discover) == targets
    assert maximum == 10

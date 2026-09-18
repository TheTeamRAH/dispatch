from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import asyncssh
import pytest

from dispatch.models import TargetSnapshot
from dispatch import transport as transport_module
from dispatch.transport import AuthenticatedChannel, FailureKind, SSHTransport, TransportFailure


def target() -> TargetSnapshot:
    return TargetSnapshot("node", "Node", "operator@node")


@pytest.mark.asyncio
async def test_connect_uses_openssh_config_known_hosts_and_keys_before_password(monkeypatch, tmp_path) -> None:
    connection = Mock()
    connect = AsyncMock(side_effect=[asyncssh.PermissionDenied("denied"), connection])
    monkeypatch.setattr(asyncssh, "connect", connect)
    password_provider = AsyncMock(return_value="ephemeral-secret")
    transport = SSHTransport(config_path=tmp_path / "config", known_hosts_path=tmp_path / "known_hosts")
    transport.config_path.touch()
    transport.known_hosts_path.touch()

    channel = await transport.connect(target(), password_provider)

    assert isinstance(channel, AuthenticatedChannel)
    assert channel.connection is connection
    assert password_provider.await_count == 1
    assert connect.await_args_list[0].args == ("node",)
    assert connect.await_args_list[0].kwargs == {
        "config": tmp_path / "config", "known_hosts": str(tmp_path / "known_hosts"), "username": "operator"
    }
    assert connect.await_args_list[1].args == ("node",)
    assert connect.await_args_list[1].kwargs == {
        "config": tmp_path / "config", "known_hosts": str(tmp_path / "known_hosts"), "password": "ephemeral-secret", "username": "operator"
    }


@pytest.mark.asyncio
async def test_connect_omits_missing_openssh_files(monkeypatch, tmp_path) -> None:
    connection = Mock()
    connect = AsyncMock(return_value=connection)
    monkeypatch.setattr(asyncssh, "connect", connect)
    transport = SSHTransport(config_path=tmp_path / "config", known_hosts_path=tmp_path / "known_hosts")

    await transport.connect(target(), AsyncMock())

    assert connect.await_args.kwargs == {"username": "operator"}


@pytest.mark.asyncio
async def test_connect_does_not_prompt_when_host_is_untrusted(monkeypatch) -> None:
    connect = AsyncMock(side_effect=asyncssh.HostKeyNotVerifiable("untrusted"))
    monkeypatch.setattr(asyncssh, "connect", connect)
    password_provider = AsyncMock()

    outcome = await SSHTransport().connect(target(), password_provider)

    assert outcome == TransportFailure(FailureKind.HOST_UNTRUSTED, "The SSH host is not trusted (identity: untrusted). Establish trust with your normal SSH workflow before retrying.")
    password_provider.assert_not_awaited()


@pytest.mark.asyncio
async def test_password_provider_error_becomes_a_safe_authentication_failure(monkeypatch) -> None:
    monkeypatch.setattr(asyncssh, "connect", AsyncMock(side_effect=asyncssh.PermissionDenied("denied")))
    password_provider = AsyncMock(side_effect=RuntimeError("secret detail"))

    outcome = await SSHTransport().connect(target(), password_provider)

    assert outcome == TransportFailure(FailureKind.AUTHENTICATION, "Password authentication could not be completed.")


@pytest.mark.asyncio
async def test_connection_failure_includes_safe_transport_reason(monkeypatch) -> None:
    monkeypatch.setattr(asyncssh, "connect", AsyncMock(side_effect=OSError("Network is unreachable")))

    outcome = await SSHTransport().connect(target(), AsyncMock())

    assert outcome == TransportFailure(FailureKind.CONNECTION, "Unable to connect to the SSH target: Network is unreachable")


@pytest.mark.asyncio
async def test_connect_timeout_becomes_connection_failure(monkeypatch) -> None:
    async def never_connect(*args, **kwargs):
        await __import__("asyncio").Event().wait()

    monkeypatch.setattr(transport_module, "CONNECT_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(asyncssh, "connect", never_connect)

    outcome = await SSHTransport().connect(target(), AsyncMock())

    assert outcome == TransportFailure(FailureKind.CONNECTION, "Unable to connect to the SSH target: connection timed out after 15 seconds")


@pytest.mark.asyncio
async def test_run_and_close_use_retained_connection() -> None:
    process = Mock(exit_status=100, stdout="updates", stderr="")
    connection = Mock(run=AsyncMock(return_value=process), close=Mock(), wait_closed=AsyncMock())
    transport = SSHTransport()
    channel = AuthenticatedChannel(target(), connection)

    completed = await transport.run(channel, "LC_ALL=C dnf -q --color=never check-update")
    await transport.close(channel)

    assert completed.exit_status == 100
    assert completed.stdout == "updates"
    connection.run.assert_awaited_once_with("LC_ALL=C dnf -q --color=never check-update", check=False)
    connection.close.assert_called_once_with()
    connection.wait_closed.assert_awaited_once_with()

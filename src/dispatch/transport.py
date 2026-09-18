"""AsyncSSH transport with OpenSSH-compatible local configuration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Awaitable, Callable

import asyncssh

from .models import TargetSnapshot

CONNECT_TIMEOUT_SECONDS = 15

PasswordProvider = Callable[[TargetSnapshot], Awaitable[str | None]]


class FailureKind(StrEnum):
    CONNECTION = "connection_failed"
    AUTHENTICATION = "authentication_failed"
    HOST_UNTRUSTED = "host_untrusted"
    HOST_KEY_MISMATCH = "host_key_mismatch"


@dataclass(frozen=True)
class TransportFailure:
    """A classified error which is safe to display to an operator."""

    kind: FailureKind
    explanation: str


@dataclass(frozen=True)
class AuthenticatedChannel:
    target: TargetSnapshot
    connection: Any


@dataclass(frozen=True)
class CompletedCommand:
    exit_status: int
    stdout: str
    stderr: str


class SSHTransport:
    """Establish and retain a verified SSH connection for one target."""

    def __init__(self, config_path: Path | None = None, known_hosts_path: Path | None = None) -> None:
        ssh_directory = Path.home() / ".ssh"
        self.config_path = config_path or ssh_directory / "config"
        self.known_hosts_path = known_hosts_path or ssh_directory / "known_hosts"

    async def connect(
        self, target: TargetSnapshot, password_provider: PasswordProvider
    ) -> AuthenticatedChannel | TransportFailure:
        options: dict[str, object] = {}
        if self.config_path.exists():
            options["config"] = self.config_path
        if self.known_hosts_path.exists():
            options["known_hosts"] = str(self.known_hosts_path)
        destination, username = self._destination_options(target.ssh_destination)
        if username is not None:
            options["username"] = username
        try:
            connection = await asyncio.wait_for(asyncssh.connect(destination, **options), timeout=CONNECT_TIMEOUT_SECONDS)
        except asyncssh.HostKeyNotVerifiable as error:
            return self._host_failure(error)
        except asyncssh.PermissionDenied:
            return await self._connect_with_password(target, destination, password_provider, options)
        except TimeoutError:
            return TransportFailure(FailureKind.CONNECTION, "Unable to connect to the SSH target: connection timed out after 15 seconds")
        except (asyncssh.Error, OSError) as error:
            return TransportFailure(FailureKind.CONNECTION, self._connection_failure(error))
        return AuthenticatedChannel(target, connection)

    async def _connect_with_password(
        self, target: TargetSnapshot, destination: str, password_provider: PasswordProvider, options: dict[str, object]
    ) -> AuthenticatedChannel | TransportFailure:
        try:
            password = await password_provider(target)
        except Exception:
            return TransportFailure(FailureKind.AUTHENTICATION, "Password authentication could not be completed.")
        if password is None:
            return TransportFailure(FailureKind.AUTHENTICATION, "Authentication was cancelled.")
        try:
            connection = await asyncio.wait_for(asyncssh.connect(destination, **options, password=password), timeout=CONNECT_TIMEOUT_SECONDS)
        except asyncssh.HostKeyNotVerifiable as error:
            return self._host_failure(error)
        except asyncssh.PermissionDenied:
            return TransportFailure(FailureKind.AUTHENTICATION, "SSH authentication was denied.")
        except TimeoutError:
            return TransportFailure(FailureKind.CONNECTION, "Unable to connect to the SSH target: connection timed out after 15 seconds")
        except (asyncssh.Error, OSError) as error:
            return TransportFailure(FailureKind.CONNECTION, self._connection_failure(error))
        finally:
            # Do not retain an ephemeral password beyond this connection attempt.
            password = None
        return AuthenticatedChannel(target, connection)

    @staticmethod
    def _host_failure(error: Exception) -> TransportFailure:
        if "changed" in str(error).lower() or "mismatch" in str(error).lower():
            return TransportFailure(FailureKind.HOST_KEY_MISMATCH, "The SSH host key does not match the trusted identity.")
        return TransportFailure(
            FailureKind.HOST_UNTRUSTED,
            f"The SSH host is not trusted (identity: {error}). Establish trust with your normal SSH workflow before retrying.",
        )

    @staticmethod
    def _destination_options(destination: str) -> tuple[str, str | None]:
        """Split the supported user@host syntax without involving a shell."""
        username, separator, host = destination.partition("@")
        if separator and username and host and "@" not in host:
            return host, username
        return destination, None

    @staticmethod
    def _connection_failure(error: Exception) -> str:
        reason = " ".join(str(error).split())[:200]
        return f"Unable to connect to the SSH target: {reason}" if reason else "Unable to connect to the SSH target."

    async def run(self, channel: AuthenticatedChannel, command: str) -> CompletedCommand:
        process = await channel.connection.run(command, check=False)
        return CompletedCommand(process.exit_status, process.stdout, process.stderr)

    async def close(self, channel: AuthenticatedChannel) -> None:
        channel.connection.close()
        await channel.connection.wait_closed()

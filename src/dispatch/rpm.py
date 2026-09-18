"""Read-only DNF/YUM discovery provider."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import re

from .models import CurrentRebootState, Outcome, PackageUpdate, RebootForecast, SecurityState, TargetResult, TargetSnapshot


@dataclass(frozen=True)
class CompletedCommand:
    exit_status: int
    stdout: str
    stderr: str = ""


class RpmProvider:
    async def discover(self, target: TargetSnapshot, channel) -> TargetResult:
        timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        detected = await channel.run("LC_ALL=C command -v dnf || command -v yum")
        tool = detected.stdout.strip().splitlines()[0].rsplit("/", 1)[-1] if detected.stdout.strip() else None
        if tool not in {"dnf", "yum"}:
            return self._result(target, timestamp, Outcome.UNSUPPORTED, "No supported dnf or yum package manager was found.")
        updates = await channel.run(f"LC_ALL=C {tool} -q --color=never check-update")
        if updates.exit_status not in {0, 100}:
            return self._result(target, timestamp, Outcome.DISCOVERY_FAILED, "Package update discovery failed.")
        try:
            candidates = self._updates(updates.stdout) if updates.exit_status == 100 else []
        except ValueError:
            return self._result(target, timestamp, Outcome.DISCOVERY_FAILED, "Package update output could not be parsed.")
        installed = await channel.run("LC_ALL=C rpm -qa --qf '%{NAME}\t%{EPOCHNUM}:%{VERSION}-%{RELEASE}\t%{ARCH}\n'")
        if installed.exit_status != 0:
            return self._result(target, timestamp, Outcome.DISCOVERY_FAILED, "Installed package versions could not be read.")
        versions = self._installed(installed.stdout)
        try:
            packages = [PackageUpdate(name, architecture, versions[(name, architecture)], candidate, repository) for name, architecture, candidate, repository in candidates]
        except KeyError:
            return self._result(target, timestamp, Outcome.DISCOVERY_FAILED, "An update could not be correlated to an installed package.")
        advisory = await channel.run(f"LC_ALL=C {tool} -q --color=never updateinfo list updates security")
        security, packages = self._security(advisory, packages)
        reboot = await channel.run(f"LC_ALL=C {tool} needs-restarting -r")
        current = CurrentRebootState.NOT_REQUIRED if reboot.exit_status == 0 else CurrentRebootState.REQUIRED if reboot.exit_status == 1 else CurrentRebootState.UNKNOWN
        forecast = RebootForecast.LIKELY if any(package.name == "kernel" or package.name.startswith("kernel-") for package in packages) else RebootForecast.NOT_INDICATED
        return TargetResult(
            target, timestamp, Outcome.SUCCESS, tuple(packages), security, current, forecast,
            current_reboot_explanation=("The package manager could not determine whether a reboot is currently required." if current is CurrentRebootState.UNKNOWN else None),
            reboot_forecast_explanation=None,
        )

    @staticmethod
    def _result(target, timestamp, outcome, explanation):
        return TargetResult(target, timestamp, outcome, explanation=explanation)

    @staticmethod
    def _updates(output: str) -> list[tuple[str, str, str, str | None]]:
        rows = []
        for line in output.splitlines():
            if not line.strip() or line.startswith("Last metadata expiration check:"):
                continue
            fields = line.split()
            if len(fields) != 3 or "." not in fields[0]:
                raise ValueError("invalid update row")
            name, architecture = fields[0].rsplit(".", 1)
            rows.append((name, architecture, fields[1], fields[2]))
        return rows

    @staticmethod
    def _installed(output: str) -> dict[tuple[str, str], str]:
        versions = {}
        for line in output.splitlines():
            fields = line.split("\t")
            if len(fields) == 3:
                versions[(fields[0], fields[2])] = fields[1]
        return versions

    @staticmethod
    def _security(command: CompletedCommand, packages: list[PackageUpdate]) -> tuple[SecurityState, list[PackageUpdate]]:
        if command.exit_status != 0:
            return SecurityState.unknown("Repository security advisory metadata is unavailable."), packages
        advisories: dict[tuple[str, str], list[str]] = {(item.name, item.architecture): [] for item in packages}
        rows = [line for line in command.stdout.splitlines() if line.strip()]
        try:
            for line in rows:
                fields = line.split()
                if len(fields) != 3 or "." not in fields[2]:
                    raise ValueError
                advisory, package_evr_arch = fields[0], fields[2]
                matches = [item for item in packages if package_evr_arch.startswith(f"{item.name}-") and package_evr_arch.endswith(f".{item.architecture}")]
                if not matches:
                    raise ValueError
                match = max(matches, key=lambda item: len(item.name))
                advisories[(match.name, match.architecture)].append(advisory)
        except ValueError:
            return SecurityState.unknown("Repository security advisory metadata could not be correlated to updates."), packages
        if packages and not rows:
            return SecurityState.unknown("Repository did not provide usable security advisory metadata."), packages
        updated = [PackageUpdate(item.name, item.architecture, item.installed_evr, item.candidate_evr, item.repository, tuple(advisories[(item.name, item.architecture)])) for item in packages]
        return SecurityState.known(sum(bool(ids) for ids in advisories.values())), updated

---
type: feature-specification
title: RPM update discovery dashboard
description: Define Dispatch's first read-only terminal workflow for inspecting pending RPM updates across SSH targets.
status: proposed
tags:
  - dispatch
  - tui
  - ssh
  - rpm
  - dnf
  - yum
  - tdd
sources:
  - id: user-conversation-2026-09-18
    title: Dispatch product-scoping conversation
    description: Requirements and decisions supplied by the product owner during this session.
  - id: agents-md
    title: Repository agent guidance
    path: AGENTS.md
  - id: readme-md
    title: Dispatch repository overview
    path: README.md
  - id: dnf-command-reference
    title: DNF command reference
    url: https://dnf.readthedocs.io/en/latest/command_ref.html
---

# RPM update discovery dashboard

## Context

Dispatch is a modular terminal user interface for dispatching infrastructure operations.[^readme-md] Its first useful capability is deliberately narrower: an operator must be able to inspect the pending RPM updates and reboot status of Rocky Linux targets over SSH, before Dispatch performs any infrastructure-changing operation.[^user-conversation-2026-09-18]

Today this information requires connecting to individual systems and running package-management commands manually. The first Dispatch release must provide an explicit, local operator workflow for one target or a set of saved targets, preserve useful results as history, and establish extension boundaries for later package providers and operation executors.

[^user-conversation-2026-09-18]: [Dispatch product-scoping conversation](#sources)
[^agents-md]: [Repository agent guidance](../../AGENTS.md)
[^readme-md]: [Dispatch repository overview](../../README.md)
[^dnf-command-reference]: [DNF command reference](https://dnf.readthedocs.io/en/latest/command_ref.html)

## Goal

Provide a safe, read-only TUI that, on demand, discovers available `dnf`/`yum` package updates for supplied or registered SSH targets and presents an accurate summary, detailed package data, security-advisory availability, and reboot information.

## Scope

### In scope

- A local terminal UI that is idle when opened: it must not create network connections, refresh targets, or change remote systems until the operator invokes an action.
- A menu containing, at minimum:
  - inspect a supplied one-off target;
  - inspect one or more registered targets;
  - register, edit, and remove saved targets; and
  - view saved inspection history.
- An editable, local target registry at the platform's XDG configuration location (normally `~/.config/dispatch/`), with no credentials or private keys stored by Dispatch.
- RPM update discovery for `dnf` and `yum` targets, initially targeting Rocky Linux.
- A summary for each inspected target containing the total pending-update count, security-update count or an explicit unknown state, current reboot-required state, post-update reboot forecast, discovery time, and any connection/query error.
- A toggleable detail view showing every pending package with installed version, candidate version, package source/repository where available, and security-advisory classification where available.
- Local persisted history of completed discovery attempts, including successful, failed, and deliberately skipped targets.
- Single-target and multi-target discovery.
- A connection-preflight phase for multi-target discovery, followed by concurrent read-only queries for successfully connected targets, with a fixed maximum of 10 active target queries in v1.
- A modular internal boundary for later transports, package-discovery providers, action executors, and workflows. Future examples include APT discovery, Ansible playbooks, local shell commands, image updates, guest shutdown, and Proxmox maintenance.

### Out of scope

- Installing, upgrading, removing, or rebooting any system.
- Running Ansible playbooks, Ansible ad-hoc commands, remote shell actions, or local shell actions.
- Docker/Compose, virtual-machine, or Proxmox discovery and operations.
- APT support, scheduling, background refresh, automatic startup actions, and user-configurable concurrency.
- Syncing, uploading, sharing, or centrally storing target definitions or history.
- Credential, SSH-key, or secret management.

## Product requirements

### Target input and registration

R1. Dispatch must allow an operator to inspect a one-off target without saving it.

R2. Dispatch must allow an operator to explicitly save a target, edit a saved target, and remove a saved target. A target must have a unique local identifier, a display name, and an SSH destination. The SSH destination may be an OpenSSH host alias or a `user@host` destination.

R3. Dispatch must load saved targets from a human-editable TOML registry at `$XDG_CONFIG_HOME/dispatch/targets.toml` (normally `~/.config/dispatch/targets.toml`). The application must create its own configuration directory and initial registry only when the operator explicitly saves a target or otherwise requests a persistent configuration change. The registry must begin with `version = 1`; each `[[targets]]` entry must contain `id`, `name`, and `ssh_destination`, and may contain `provider` (defaulting to `rpm`). Unknown fields must be preserved when Dispatch rewrites the file, so a future version can add declarative capabilities without destroying user configuration.

R4. Target configuration and history must not contain passwords, passphrases, private-key material, or copies of SSH-agent credentials.

### SSH connection and authentication

R5. Before prompting for a password, Dispatch must attempt normal OpenSSH-style key-based authentication using the user's existing SSH configuration, SSH agent, and available keys. Dispatch must not require users to configure keys through Dispatch.

R6. If normal authentication cannot access a target and the server otherwise passes host-identity verification, Dispatch must offer an in-TUI authentication prompt. Prompted secrets must be masked, used only for the active connection attempt, and discarded immediately after that attempt. They must never be persisted or emitted in UI output, history, or logs.

R7. Dispatch must use the user's normal SSH known-hosts trust data. A host-key mismatch must fail clearly and must never be bypassed automatically. An untrusted host must not be silently accepted or added to a trust store by Dispatch in v1; the UI must show the presented host identity/fingerprint and explain that the operator must establish trust through their normal SSH workflow before retrying.

R8. A multi-target inspection must authenticate and establish connectivity for each selected target before RPM discovery begins. Authentication prompts must be serial and identify the current target, so credentials for different systems cannot be confused.

R9. When any selected target fails connection or authentication preflight, Dispatch must offer retry, skip-and-continue, and cancel-the-batch choices. Skipped and failed targets must be recorded in the resulting history entry.

### RPM discovery

R10. Dispatch must ship a built-in, read-only RPM package-discovery provider that supports systems exposing either `dnf` or `yum`. It must prefer `dnf` when both are available and otherwise use `yum`; if neither command is available, it must return the unsupported outcome in R15.

R11. For a reachable supported target, the provider must determine whether updates are available and list every pending package's installed version and candidate version. A normal package-manager “updates available” exit status must be treated as successful discovery, not as an error. DNF documents exit code `100` for `check-update` when updates are available, versus `0` when none are available and `1` for an error.[^dnf-command-reference]

R12. The provider must obtain security-update information from repository advisory metadata where the target's package-manager tooling exposes it. The UI's security-update count means the number of distinct pending packages associated with one or more available security advisories, not the number of advisories. DNF's `updateinfo` command exposes advisory summary, list, and detail output, including security advisory information.[^dnf-command-reference] If security advisory metadata is unavailable or cannot be reliably correlated with pending updates, the UI must show security status as `Unknown` with a reason; it must not display zero.

R13. The provider must report whether the currently running target requires a reboot using an operating-system-supported reboot check where one is available. If the check is unavailable or inconclusive, the state must be `Unknown`, not `No`.

R14. The provider must separately report a post-update reboot forecast based on the pending-update set. Its allowed states are `Likely`, `Not indicated`, and `Unknown`; it must be clearly labelled as a forecast rather than an authoritative current reboot requirement. In v1, the provider may report `Likely` only when a pending RPM name is exactly `kernel` or starts with `kernel-`, must report `Unknown` when it cannot inspect the pending package set, and must otherwise report `Not indicated`. The detail view must identify the package(s) that caused a `Likely` result.

R15. A target that lacks a supported RPM package manager must be reported as unsupported with a clear message; it must not be reported as having zero pending updates.

### TUI and batch behaviour

R16. The initial screen must present actions and the latest available local history only. It must not automatically inspect a target.

R17. After a deliberate single-target inspection, the TUI must display that target's summary and allow the operator to toggle to package details.

R18. After a deliberate multi-target inspection, Dispatch must run the RPM discovery workflow in parallel for preflight-successful targets, with no more than 10 target workflows active at once. Commands within one target workflow may run sequentially. The summary view must update each target independently as its result completes.

R19. The multi-target summary must distinguish successful results, skipped targets, connection failures, authentication failures, unsupported targets, and package-discovery failures.

R20. The TUI must keep the read-only nature of this release clear: no discovery screen may present an upgrade, reboot, restart, shutdown, or shell-execution control.

### History and modularity

R21. Dispatch must persist the result of each completed inspection run locally under the user's XDG state directory (normally `~/.local/state/dispatch/`), including the time, selected targets, per-target connection/discovery outcome, normalized summary data, and package details when discovery succeeded. V1 must not automatically prune history. Deleting a saved target must not delete its existing history; history records must retain the target display name and SSH destination captured at run time.

R22. History must be viewable from the TUI without performing a new remote query.

R23. The core application must consume a normalized discovery-result model rather than RPM-command output directly. The model must represent update details, known/unknown security status, current reboot status, reboot forecast, unsupported-provider status, and actionable errors.

R24. The application must define separately testable component boundaries for at least SSH transport, package-discovery provider, target/configuration store, history store, and TUI workflow. Adding an APT provider or a future Ansible/shell executor must not require modifying RPM provider logic or the core result model.

### Responsive terminal interaction

R25. The TUI must determine the terminal viewport when it starts and respond to terminal-resize events throughout an active session. It must reflow its layout without requiring a restart or a new inspection run.

R26. The initial menu, target selection, authentication prompts, summaries, package-detail view, batch progress, and history view must remain usable in narrow phone-terminal and foldable-phone-terminal viewports as well as conventional desktop terminals. Narrow viewports must use a compact single-column or stacked presentation where needed; information may be moved behind an existing detail action or made scrollable, but it must not become unavailable.

R27. A resize during an active workflow must preserve the current workflow state: selected targets, typed but unsubmitted non-secret input, current focus, completed results, in-progress batch status, and the operator's place in a scrollable view. Masked secret input must remain masked and must not be copied into other UI state.

## Component contract

The following interface-level boundaries are required so a new implementation context does not have to infer the extension model:

| Component | Input | Required output / responsibility |
| --- | --- | --- |
| Target registry | Explicit save, edit, remove, and load requests | Validated target definitions without credentials; persistence only after an explicit change. |
| SSH transport | A target definition and an operator-mediated authentication/trust decision | An authenticated command channel or a typed connection/authentication/host-trust failure. It owns no package parsing or history writes. |
| Package-discovery provider | An authenticated command channel | One normalized discovery result. It owns RPM command invocation and parsing, but does not render UI or persist data. |
| History store | Completed run and normalized per-target results | Local durable records that exclude secrets and can be read without creating an SSH connection. |
| TUI workflow | Operator action plus component outcomes | The required prompts, summaries, details, batch progress, and history views. It must not parse raw package-manager output. |

The normalized discovery result must carry the target identity, timestamp, outcome category, package details, security status and explanation, current reboot status and explanation, reboot forecast and explanation, and any safe-to-display error message. Providers must use the same result shape for successful, unknown, unsupported, skipped, and failed outcomes.

The initial target registry has this required shape:

```toml
version = 1

[[targets]]
id = "docker-001"
name = "Docker host"
ssh_destination = "ansible@docker-001.rah.home"
provider = "rpm"
```

`id` is the stable local key used by Dispatch. `name` is the operator-facing label. `ssh_destination` is passed to the SSH transport and must be either an OpenSSH host alias or a `user@host` destination. Dispatch must validate duplicate or empty `id` values and reject them without altering the existing registry.

## User flows

### Inspect a supplied target

1. The operator opens Dispatch and selects the one-off inspection action.
2. They supply an OpenSSH alias or `user@host` destination.
3. Dispatch performs normal SSH authentication, prompting in the TUI only if needed.
4. Dispatch runs RPM discovery only after a connection succeeds.
5. The operator sees the summary, can toggle package details, and can later find the run in history. The target is not saved unless the operator explicitly chooses to register it.

### Inspect saved targets

1. The operator opens Dispatch and selects one or more registered targets.
2. Dispatch performs connection/authentication preflight target-by-target.
3. If a target cannot connect, the operator selects retry, skip, or cancel.
4. Dispatch queries all preflight-successful targets in parallel, with at most 10 active queries.
5. The summary updates as results finish and is written to local history when the run concludes.

### Interpret uncertain package metadata

1. The operator selects a target summary.
2. If advisory metadata is missing, Dispatch displays `Security: Unknown` and explains that the repository did not provide usable advisory data.
3. If a reboot check or forecast is inconclusive, Dispatch displays `Unknown` rather than falsely reassuring the operator that a reboot is unnecessary.

## Constraints and safety requirements

- This feature is read-only against remote targets. Implementation must not invoke package installation, reboot, or service/VM lifecycle commands.
- Passwords and other prompted authentication data are ephemeral in-memory values only.
- SSH host-key checks must fail closed on mismatches. Dispatch does not create first-use trust records in v1.
- The user owns target registration and configuration. Dispatch dictates the configuration format but must not embed infrastructure-specific targets, inventories, credentials, or automation definitions.
- The maximum parallel discovery limit is fixed at 10 for this release; exposing it as a setting is deferred.
- Dispatch must not assume a desktop-sized terminal or a fixed viewport. Terminal reflow is a UI concern only and must not interrupt an active SSH connection or RPM discovery workflow.
- The solution must be implemented in Python unless the user explicitly authorizes a different language, consistent with repository guidance.[^agents-md]

## Implementation notes

These are implementation constraints, not a commitment to a particular TUI or SSH library.

- Keep the initial component contracts narrow: a transport establishes an authenticated channel, a provider produces the normalized discovery result, stores persist local data, and the TUI invokes those components.
- Invoke package-manager and reboot-check commands in read-only forms only. Command parsing should be isolated behind the RPM provider so fixture tests can exercise supported output and error cases without SSH.
- The RPM provider must first determine whether `dnf` or `yum` is available, then use that tool's non-mutating update and advisory queries. It must classify command absence, unavailable repository metadata, parse failures, and unsupported commands as explicit normalized states rather than allowing raw command output to leak into the TUI.
- `dnf` takes precedence over `yum` when both commands are available. Implement the RPM provider's command parsing with captured fixtures; do not rely on the user's current locale or terminal colour settings for a stable result.
- Treat RPM package-manager exit codes and advisory availability as domain data. Do not collapse an “updates available” status, unknown advisory information, or unsupported package manager into a generic failure.
- The password prompt is a UI interaction mediated by the SSH transport and does not belong in target configuration or history. First-use host trust remains an external SSH setup step in this release.
- Future action registration may use a declarative user-owned configuration format and can introduce Ansible and shell executors. It is intentionally not designed or implemented by this feature.

## TDD and validation

Implementation must follow test-driven development: write each test before the production behaviour it verifies and run it once to demonstrate the expected failure, then implement the smallest behaviour that makes it pass.[^agents-md]

### Required automated tests

- Unit tests for target-registry and history persistence, including that secret fields are rejected or omitted from persisted data.
- Unit tests for the version-1 TOML registry, including round-tripping known entries, preserving unknown fields, rejecting duplicate/empty IDs, and retaining history after a saved target is deleted.
- Unit tests for the normalized result model, including known, unknown, unsupported, skipped, and failed states.
- Fixture-based unit tests for `dnf` and `yum` parsing, covering: no updates; updates available; package detail parsing; security metadata available; security metadata unavailable; current reboot required; reboot not required; unknown reboot state; and unsupported package manager.
- Tests proving package-manager “updates available” exit status is a successful discovery result.
- Tests proving the post-update reboot forecast is distinct from current reboot-required state and uses `Unknown` when unsupported or inconclusive.
- Tests for the parallel batch scheduler proving that no more than 10 discovery queries are active at a time.
- Tests for batch-preflight outcomes covering retry, skip, and cancel choices, including history records for skipped and failed targets.
- Tests for password-prompt handling proving input is masked in the UI model and excluded from configuration, history, diagnostic output, and exceptions.
- Tests for SSH trust decisions proving mismatched keys fail and an untrusted host is rejected without Dispatch writing a trust record.
- TUI-level tests for idle-on-open behaviour, explicit invocation of discovery, summary/detail toggling, and history viewing without a new connection.
- TUI-level tests that render every v1 screen in a narrow terminal viewport and verify all actions/data remain reachable through reflow, detail, or scrolling.
- TUI-level tests that resize each active v1 workflow from a conventional terminal to a narrow viewport and back, verifying no duplicate connection/query is created and the state required by R27 is retained.

### Manual validation

- Start Dispatch with no saved targets and verify no network activity occurs until an action is selected.
- Inspect a Rocky Linux target with pending updates and verify summary counts and package versions against direct read-only `dnf` or `yum` output.
- Inspect a target with unavailable security advisory metadata and verify that the display is `Unknown`, not zero.
- Inspect a target with reboot required and one where reboot status cannot be determined; verify distinct, honest states.
- Run a batch with at least two targets using different authentication paths and deliberately make one inaccessible; verify serial prompts, retry/skip/cancel choices, parallel discovery for reachable targets, and saved history.
- Attempt a connection to an untrusted host and a host with a changed key; verify Dispatch displays safe identity information, refuses the connection, and does not modify the user's trust data.
- Start Dispatch in both a conventional terminal and a narrow phone-terminal viewport, then resize during target selection, an authentication prompt, batch progress, package details, and history viewing; verify reflow and state preservation without restarting the session.
- Confirm configuration and history files contain no prompted password or other secret value.

## Acceptance criteria

The feature is complete when all of the following are true:

1. A user can inspect a supplied Rocky Linux SSH target without registering it and see pending update count, security status/count or `Unknown`, current reboot status, post-update reboot forecast, and toggleable package details.
2. A user can explicitly register a target in their local XDG Dispatch configuration, select one or more saved targets, and inspect them without automatic discovery at application startup.
3. Multi-target discovery completes queries for successful preflight targets in parallel while never exceeding 10 active queries.
4. Failed connections provide retry, skip, and cancel options, and final history accurately records every selected target's outcome.
5. Dispatch uses normal SSH configuration/keys first, supports an ephemeral masked in-TUI authentication prompt when needed, never persists credentials, and never modifies SSH trust records.
6. Security and reboot uncertainty is visibly represented as `Unknown`; no unavailable metadata is presented as a zero count or a negative reboot requirement.
7. No feature path performs a mutating remote operation.
8. The automated tests and manual validation above pass, including the required failing-test-first evidence for newly implemented behaviours.
9. Every v1 screen is usable in a narrow phone-terminal viewport and reflows correctly when the terminal is resized at launch or during an active session, without losing workflow state or starting a duplicate operation.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| `dnf` and `yum` output or advisory support differs by host version and repository configuration. | Isolate parsing in the RPM provider, use representative fixtures, and surface unavailable data as `Unknown`. |
| A convenient password prompt accidentally leaks a secret. | Keep credentials ephemeral, mask UI input, redact diagnostics, and test persistence and error paths explicitly. |
| Parallel discovery makes failures or credential prompts confusing. | Complete authentication preflight serially; parallelize only the read-only discovery phase and cap it at 10. |
| Early code becomes coupled to RPM commands and blocks future capabilities. | Require normalized models and independently testable transport, provider, store, and UI boundaries. |
| Operators mistake a reboot forecast for a current authoritative requirement. | Present current reboot status and post-update forecast as distinct labelled fields, use `Likely` only for pending kernel packages in v1, and use `Unknown` when evidence is insufficient. |
| A fixed-width desktop layout makes Dispatch unusable from a phone terminal or after a foldable device changes shape. | Render from the current viewport, reflow on resize, preserve workflow state, and cover narrow/resize cases in TUI tests. |

## Amendments

- The product owner added responsive terminal support on 2026-09-18: Dispatch must adapt to phone, conventional terminal, and foldable-phone viewports both at launch and after mid-session resize events.

## Sources

- Dispatch product-scoping conversation (product-owner requirements captured in this specification)
- [Repository agent guidance](../../AGENTS.md)
- [Dispatch repository overview](../../README.md)
- [DNF command reference](https://dnf.readthedocs.io/en/latest/command_ref.html)

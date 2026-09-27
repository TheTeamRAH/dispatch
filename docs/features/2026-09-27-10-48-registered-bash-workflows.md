---
type: feature-specification
title: Registered remote Bash workflows
description: Add declarative, user-registered remote Bash workflows with ordered commands and optional persistent shell sessions.
status: proposed
tags:
  - dispatch
  - workflows
  - shell
  - bash
  - ssh
  - tui
sources:
  - id: repository-guidance
    title: Dispatch repository working instructions
    path: ../../AGENTS.md
  - id: repository-readme
    title: Dispatch repository overview
    path: ../../README.md
  - id: rpm-discovery-spec
    title: RPM update discovery dashboard
    path: 2026-09-18-18-58-rpm-update-discovery.md
  - id: transport
    title: Dispatch SSH transport implementation
    path: ../../src/dispatch/transport.py
  - id: inspection
    title: Dispatch inspection orchestration
    path: ../../src/dispatch/inspection.py
  - id: user-conversation-2026-09-27
    title: Registered Bash workflow product discussion
    description: Product decisions supplied during the Dispatch workflow design discussion.
---

# Registered remote Bash workflows

## Context

Dispatch currently provides a modular SSH transport and a read-only RPM discovery workflow. The transport retains an authenticated SSH connection, while `SSHTransport.run()` executes a supplied command through a separate remote process. The existing target registry persists destinations, but the model accepts only the `rpm` provider. The repository's first feature deliberately left shell actions out of scope while requiring separately testable future executor and workflow boundaries.[^rpm-discovery-spec][^transport][^inspection]

Operators now need to register ordered shell commands and run them against selected saved SSH targets. Some workflows must be able to share Bash state between steps, including aliases, functions, exported variables, shell options, and the current working directory. A persisted workflow definition must therefore distinguish independent command execution from one persistent Bash process.

## Goal

Allow an operator to register, edit, remove, select, and deliberately execute remote Bash workflows from Dispatch. Persist workflow definitions as human-editable TOML, execute commands through the existing verified SSH transport, and record normalized per-step outcomes without coupling shell execution to RPM discovery.

## Scope

### In scope

- A local workflow registry at `$XDG_CONFIG_HOME/dispatch/workflows.toml`.
- Workflow definitions with a stable ID, display name, `type = "shell"`, session mode, and ordered steps.
- Ordered remote Bash command execution against one or more selected saved targets.
- `isolated` sessions, where each step is run as an independent command through the authenticated SSH connection.
- `persistent` sessions, where startup commands and all workflow steps run in one long-lived Bash process per target.
- Explicit startup commands for persistent sessions, including `shopt -s expand_aliases` and `source ~/.bash_aliases` when required by the operator.
- Reuse of existing SSH configuration, host-key verification, authentication prompts, target selection, bounded multi-target orchestration, cancellation, and connection cleanup.
- TUI registration, editing, removal, selection, execution confirmation, progress, and result views.
- Durable workflow history containing bounded command output, exit status, timestamps, and safe failure explanations.
- Component boundaries that allow future executor types without changing RPM provider parsing or normalized RPM discovery models.

### Out of scope

- Local shell execution on the Dispatch host.
- Shells other than Bash in this feature.
- Automatic sourcing of `.bashrc`, `.profile`, or other remote startup files.
- Workflow scheduling, background execution, triggers, retries, branching, loops, variables, templating, or dynamic command generation.
- Credential, secret, or SSH-key management.
- Automatic approval of host keys or bypass of normal SSH trust checks.
- Ansible, container, Proxmox, or other executor types.
- Refactoring RPM discovery into a shell workflow.
- A general plugin loader or remote workflow-sharing mechanism.

## Requirements

### Workflow definition and registry

R1. Dispatch must persist workflows in `$XDG_CONFIG_HOME/dispatch/workflows.toml`, using the normal XDG default when the environment variable is absent.

R2. The registry must begin with `version = 1`. Each workflow must contain a non-empty unique `id`, non-empty `name`, `type = "shell"`, `session = "isolated"` or `session = "persistent"`, and at least one ordered command step. Each step must contain a non-empty stable `id`, non-empty `name`, and non-empty `command` string.

R3. A persistent workflow may contain ordered startup commands. Startup commands use the same command representation as steps and execute before the first step for each target.

R4. Dispatch must preserve workflow order, step order, unknown top-level fields, unknown workflow fields, and unknown step fields when rewriting a valid registry. Invalid TOML, unsupported versions, duplicate or empty IDs, unsupported types/session modes, empty command values, and malformed entries must be rejected without altering the registry.

R5. Workflow configuration must never contain passwords, passphrases, private-key material, SSH-agent credentials, or other credential fields. The registry must use the same private-directory policy as the target registry.

R6. Registering, editing, or removing a workflow must not execute commands. The registry and its parent directory must be created only after an explicit persistent configuration change.

### Execution and Bash sessions

R7. A shell workflow must execute only after an explicit operator run action and confirmation showing the workflow, selected targets, session mode, startup commands, and ordered steps.

R8. Shell workflows must execute remotely through the existing authenticated, host-verified SSH transport. A workflow must not create a second authentication implementation or bypass target trust decisions.

R9. An isolated workflow must run each step through the existing command boundary. Shell state must not be promised or preserved between steps.

R10. A persistent workflow must open one long-lived `/bin/bash` process per target over the authenticated SSH connection. Startup commands and steps must execute sequentially in that process. The implementation must preserve shell state between commands, including aliases, functions, variables, exports, shell options, and the current directory.

R11. Persistent Bash sessions must not implicitly source `.bashrc`, `.profile`, or another startup file. Operators may explicitly source files through startup commands. The implementation must support alias-dependent workflows when the workflow explicitly enables alias expansion and sources the required alias definitions, for example `shopt -s expand_aliases` followed by `source ~/.bash_aliases`.

R12. Persistent-session command boundaries must be unambiguous. The implementation must associate each step with its own exit status, stdout, and stderr, even when command output contains arbitrary ordinary text. A step must not be considered successful merely because the Bash process remains alive.

R13. Steps must execute in declared order. By default, a non-zero step exit status must fail the target workflow and mark later unstarted steps as skipped. The first version may expose an explicit per-step `continue_on_failure` option only if it can be implemented and displayed consistently; otherwise the field is out of scope and all steps stop on failure.

R14. Each selected target must receive an independent workflow session and result. A failure on one target must not corrupt or silently change another target's session.

R15. The workflow executor must use bounded command/session timeouts, close the Bash process and SSH connection on success, failure, cancellation, and transport errors, and prevent new work from starting after cancellation.

### Results and history

R16. Every executed workflow run must produce a normalized run record containing workflow identity and name, session mode, start and completion timestamps, selected target snapshots, and one target result per selected target.

R17. Each target result must contain an overall outcome and ordered startup/step results. Each command result must contain the step identity and name, timestamps, exit status when available, bounded stdout, bounded stderr, and a safe-to-display explanation when it fails, is skipped, or is cancelled.

R18. History must not contain passwords, passphrases, private keys, or SSH-agent credentials. Output must be bounded so a command cannot create unbounded history records. The chosen output limit must be explicit in the implementation and covered by tests.

R19. Workflow history must be persisted separately from RPM inspection history so existing `InspectionRun` records and readers remain compatible. History must be readable without opening an SSH connection and malformed records must be ignored with a local warning rather than rewritten.

### TUI and modularity

R20. The TUI must provide workflow registration, editing, removal, selection, execution confirmation, progress, and results without changing the existing RPM discovery behaviour.

R21. The workflow coordinator must consume workflow definitions and target snapshots, select an executor by workflow type, coordinate target-level concurrency using the existing bounded batch mechanism, and persist results. It must not parse shell output as RPM data or contain Bash-specific parsing beyond session framing.

R22. The shell executor must depend on a command-session abstraction rather than directly coupling workflow logic to AsyncSSH. Existing RPM discovery must continue to depend only on its command-channel contract.

R23. The TUI must clearly distinguish isolated and persistent sessions and must show that persistent workflows run all commands in one remote Bash process. No workflow may run automatically at startup, after registration, or after configuration reload.

R24. Workflow interaction must remain usable in the existing required `40x20`, `80x24`, and `120x40` viewports. Resize events during registration, confirmation, execution, and result viewing must preserve entered non-secret values, selected targets, active progress, and displayed results.

## Proposed configuration

```toml
version = 1

[[workflows]]
id = "application-deploy"
name = "Application deploy"
type = "shell"
session = "persistent"

[[workflows.startup]]
name = "Enable aliases"
command = "shopt -s expand_aliases"

[[workflows.startup]]
name = "Load application aliases"
command = "source ~/.bash_aliases"

[[workflows.steps]]
id = "prepare"
name = "Prepare application"
command = "prepare_app"

[[workflows.steps]]
id = "deploy"
name = "Deploy application"
command = "deploy_app"
```

The configuration is declarative. It identifies commands to run but does not identify targets permanently; the operator selects saved targets at execution time. A future feature may support target selectors, but v1 should avoid silently binding a potentially mutating workflow to a target set.

## Component contract

| Component | Input | Responsibility |
| --- | --- | --- |
| Workflow registry | Explicit load, save, edit, remove | Validate and persist workflow definitions while preserving unknown fields and order. |
| Command session | Authenticated SSH channel plus Bash settings | Run isolated commands or frame commands through one persistent Bash process, returning complete command results. |
| Shell executor | Workflow definition, target, command session | Execute startup commands and ordered steps; apply failure, timeout, and cancellation semantics. |
| Workflow coordinator | Operator action, workflow, selected targets | Create target sessions, bound concurrency, report progress, close resources, and persist a run. |
| Workflow history store | Completed workflow run | Persist and load secret-free normalized workflow results. |
| TUI workflow | Operator input and component outcomes | Register, edit, remove, confirm, execute, display progress, and display results without parsing command output. |

## Risks and compatibility

- Persistent sessions require reliable command framing and must not confuse command output with framing markers. Tests must cover marker-like output, multiline output, non-zero exits, shell termination, and cancellation.
- Bash startup files are user-controlled and may be interactive, slow, or destructive. Explicit startup commands and visible confirmation reduce surprise but do not make arbitrary shell execution safe.
- Persisted command output may contain secrets emitted by user commands. The implementation must not claim to redact arbitrary command output; output limits and a clear persistence policy must be documented in the UI and specification implementation notes.
- Existing RPM inspection history and target configuration must remain readable. New workflow history and registry schemas must not change their version-1 meanings.
- A persistent Bash process may behave differently from an interactive login shell. The feature must document that startup files are opt-in and that workflows should explicitly establish the required environment.

## Validation plan

- Add registry tests for valid isolated and persistent workflows, startup commands, ordering, unknown-field preservation, malformed input, duplicate IDs, unsupported values, secret rejection, and atomic non-mutation on validation failure.
- Add command-session tests for isolated execution and persistent Bash execution, including aliases, `cd`, `export`, functions, shell options, multiline stdout/stderr, marker-like output, non-zero status, shell exit, timeout, and close behaviour.
- Add workflow executor tests for ordered steps, startup failures, step failures, skipped steps, per-target isolation, bounded output, cancellation, and cleanup on every terminal path.
- Add workflow history tests for round-trip serialization, bounded output, malformed-record handling, secret exclusion, and separation from RPM inspection history.
- Add Textual interaction and snapshot tests for registration, editing, confirmation, persistent-session warnings, execution progress, results, and all required viewports.
- Run `uv run pytest` and `git diff --check`.

## Acceptance criteria

- An operator can register a valid persistent Bash workflow through the TUI and see the equivalent workflow in `workflows.toml`.
- Registration and editing never execute a command.
- An operator can select saved SSH targets, review the workflow and persistent-session warning, and deliberately run it.
- Startup commands and ordered steps execute in one Bash process per target, so an explicitly sourced alias can be used by a later step.
- Isolated workflows do not promise state persistence between steps.
- Each target and step has a visible outcome, exit status where available, bounded stdout/stderr, and safe failure explanation.
- Cancellation and failure close Bash sessions and SSH connections and produce durable terminal results.
- Existing RPM discovery, target configuration, and RPM history tests continue to pass unchanged or with only explicitly justified shared-interface updates.
- The complete test suite and formatting checks pass.

## Implementation notes

The implementation should add workflow-specific models, registry, history, coordinator, and shell executor modules rather than expanding `TargetSnapshot` or making `RpmProvider` aware of shell workflows. A shared command-session protocol may be introduced where it reduces duplication, but the RPM result model and provider parsing contract should remain stable.

The persistent session should use a dedicated Bash process and explicit per-command framing. Framing must be generated by Dispatch and kept separate from user command text; target values, credentials, and output must never be interpolated into commands. The implementation should prefer a structured process API where available and should document any Bash invocation flags required to make startup behaviour deterministic.

## Open questions

None block this proposed v1 scope. The implementation must choose and document concrete output limits, timeout values, and the exact persistent-session framing protocol before implementation, subject to the requirements above.

## Amendments

None.

---
type: feature-specification
title: Consistent Bash workflow shell and run state
status: in_progress
description: Make registered Bash workflows load the intended profile in non-interactive execution and keep workflow progress, failure, and target counts accurate.
tags:
  - workflows
  - bash
  - ssh
  - tui
  - run-state
sources:
  - id: transport
    title: SSH transport and persistent Bash session
    path: ../../src/dispatch/transport.py
  - id: workflow-service
    title: Workflow execution service
    path: ../../src/dispatch/workflow_service.py
  - id: workflow-tui
    title: Workflow TUI execution state
    path: ../../src/dispatch/tui.py
  - id: workflow-tests
    title: Existing workflow tests
    path: ../../tests/test_workflows.py
  - id: tui-tests
    title: Existing TUI tests
    path: ../../tests/test_tui.py
  - id: managed-profile
    title: Configuration-managed Bash profile for compose hosts
    path: ../../../configuration_management/inventory/group_vars/bash_profile.yml
  - id: host-managed-profile
    title: Host-specific configuration-managed Bash profile
    path: ../../../configuration_management/inventory/group_vars/hermes/bash_profile.yml
---

# Consistent Bash workflow shell and run state

## Context

A registered workflow can execute startup commands followed by workflow commands in either an isolated or persistent session. The persistent transport deliberately starts Bash with `--noprofile --norc` and enables alias expansion, so the workflow currently depends on explicit startup commands to load shell state.

The observed workflow uses `source ~/.bash_profile` and `compose`, then invokes `pull-all`. For `docker-001.rah.home`, the common `bash_profile` group defines `pull-all`, but `compose` is currently an alias for `sudo -iu svc-compose`. An alias which starts a child login shell cannot change the parent shell's UID, HOME, aliases, working directory, or shell state. In a persistent workflow, it can also consume subsequent input in the child process. The target user's profile must be sourced after switching to that user, and non-interactive Bash must expand aliases. The fix must make the intended `pull-all` contract explicit and validate the profile rendered for the selected target; unrelated host groups must not be treated as evidence about docker-001.

The workflow UI also reports stale execution state: `_run_workflow` initializes a new active record but does not reset `workflow_results`; the service records a successful batch whenever `run_batch` returns, even when target results contain command failures; and the progress view is intentionally rendered while the worker is active. These paths need one consistent terminal outcome and one result set per run.

## Goal

Make a one-target registered workflow that fails in a command show the actual shell/profile failure, terminate as failed, and contain exactly one target result for that run. Make profile-dependent commands work through an explicit, non-interactive user-switch contract rather than relying on an interactive alias.

## Scope

In scope:

- Persistent workflow shell initialization and command execution semantics.
- The managed compose helper contract needed by workflow commands.
- Workflow service terminal status and persisted history for target-level failures.
- TUI per-run result reset, terminal view transition, and target completion count.
- Regression tests for profile loading, user identity continuity, alias availability, failed runs, and repeated one-target runs.

Out of scope:

- Changing SSH authentication, host-key policy, or target registry format.
- Changing unrelated inspection workflows.
- Automatically deploying to remote hosts or changing unrelated configuration-management behavior.
- Making arbitrary interactive shell constructs safe for automation; workflow startup commands remain operator-supplied shell text.

## Requirements

1. The persistent Bash session must have a documented, testable startup contract. Commands that need aliases or functions must load the target user's profile inside the target-user shell, with alias expansion enabled before aliases are sourced.
2. The compose helper used by workflows must preserve its no-argument interactive behavior while providing a command-bearing non-interactive path that executes the requested command as `svc-compose` and returns its exit status. A workflow step must not rely on an interactive child shell to switch the parent shell.
3. Profile loading must be performed consistently for every profile source that renders the helper, including common and host-specific configuration-management variables. Embedded YAML and Bash must be syntax-validated for each changed scope.
4. A command failure must make the target result failed, skip later steps for that target, and make the overall persisted workflow run failed when any target fails. A successful transport and completed coroutine are not sufficient to mark the run completed.
5. Each invocation of `_run_workflow` must start with an empty result collection and a fresh active record. Re-running a one-target workflow must not add prior targets to the current run or history record.
6. The progress UI must leave `workflow_progress` after the service reaches a normal or failed terminal result, and the terminal status/history entry must expose the final outcome rather than `running`.
7. Completion counters and displayed target totals must be derived from the current invocation's selected targets/results, not accumulated state.
8. Existing successful workflows, isolated-session validation, step ordering, skipped-step behavior, and persisted history compatibility must remain intact.

## Acceptance criteria

- A focused regression test demonstrates that a persistent session can source the target-user profile and run a profile-defined alias/function under the intended user without an interactive shell consuming later workflow input.
- A focused regression test demonstrates that a target with a non-zero command result produces a failed target result, skipped later steps, and a failed persisted workflow run.
- A focused TUI regression test runs the same one-target workflow twice and asserts that each invocation has one target result, no stale prior result, and a terminal results view.
- Existing tests plus the new focused tests pass in the repository's supported test environment.
- `git diff --check` passes.
- If configuration-management files are changed, every changed YAML file parses and every embedded Bash profile block passes `bash -n`; the relevant Ansible syntax check is run when Ansible is available.
- No commit, push, deployment, or feature closeout is performed as part of this work unless separately requested.

## Implementation notes

- Preserve the persistent-session framing marker and output streaming while making shell initialization explicit and observable in tests.
- Prefer a small shell function or explicit command wrapper over an alias that only launches `sudo -iu svc-compose`.
- Keep status derivation in the service authoritative for persisted history, and make the TUI consume the current invocation's results.
- Add tests before implementation and run them red, then implement the smallest root-cause fixes and run the focused and full suites.

## Risks

- Sourcing a profile can execute interactive-only statements or mutate the working directory. The workflow contract must document that the selected profile is automation-safe or use a dedicated non-interactive helper file.
- A user-switch wrapper can accidentally permit shell injection if it reconstructs command text incorrectly. Preserve the existing operator-controlled shell model and test exit-status propagation.
- Existing persisted records may contain `running` status from interrupted or old executions. This change should correct newly written records without silently rewriting historical files.

## Validation

Run the focused workflow and TUI tests first, then the complete test suite. Validate the rendered configuration-management profile and embedded Bash when that repository is included. Review the diff for scope, run `git diff --check`, and verify that no changes were made to external hosts.

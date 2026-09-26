---
type: feature-specification
title: Active workflow pane and progress feedback
description: Replace persistent command hints in the navigation pane with current-work activity and add honest progress feedback for running inspections.
status: proposed
tags:
  - dispatch
  - tui
  - textual
  - progress
  - responsive-design
sources:
  - id: repository-guidance
    title: Repository working instructions
    path: ../../AGENTS.md
  - id: dispatch-tui
    title: Dispatch Textual application
    path: ../../src/dispatch/tui.py
  - id: dispatch-tui-tests
    title: Dispatch TUI tests
    path: ../../tests/test_tui.py
  - id: textual-pane-discovery
    title: Textual pane layout lessons
    path: ../discovery/textual-pane-layouts.md
  - id: rpm-discovery-spec
    title: RPM update discovery dashboard
    path: 2026-09-18-18-58-rpm-update-discovery.md
---

# Active workflow pane and progress feedback

## Context

Dispatch's Posting layout currently keeps a persistent top pane titled `Menu` containing the four global action hints (`o One-off`, `s Saved`, `m Manage`, and `h History`). Earlier Textual Footer output also displayed contextual bindings, including disabled/crossed-out actions. Those command-guide elements are useful during initial exploration but are not useful as persistent content while a workflow is active. The product owner wants that pane to describe only what Dispatch is currently doing. The amended navigation will expose `a Action`, `i Inventory`, and `h History` instead; `Action` will contain action selection followed by host selection, while `Inventory` will contain list, edit, add, and delete operations.

The application already has an explicit `progress` view and a `Cancel batch` control, but progress is currently represented mainly by text. The inspection workflow can receive incremental target results through `_result_completed`, so the UI can provide meaningful activity feedback without changing the inspection service, SSH transport, normalized result model, or remote behavior.[^dispatch-tui]

The first RPM discovery specification requires deliberate, read-only inspection, per-target progress updates, cancellation, and preservation of active work across responsive layout changes.[^rpm-discovery-spec]

## Goal

Make the top activity pane an honest, current-work indicator rather than a persistent command guide, and add an accessible animated/progress presentation while an inspection is running without changing workflow semantics or implying progress that the service cannot measure.

## Scope

### In scope

- Replace the persistent action list in `#navigation-pane` with a current-activity presentation whose text is derived from the active view and workflow state.
- Define useful idle, form, history, result, and active-inspection states for that pane.
- Add a lightweight Textual animation, such as a cycling spinner glyph or equivalent, only while inspection work is active.
- Show determinate batch progress when the selected target count and completed target count are known, for example `Inspecting 2/5 targets`.
- Show an indeterminate spinner and explicit activity text when work is active but a total cannot be determined.
- Keep `Cancel batch` visible and keyboard reachable during active inspection.
- Preserve the current `40x20`, `80x24`, `120x40`, compact, modal, resize, and state-preservation behavior.
- Retain the four global workflows and their existing key bindings somewhere appropriate in idle/menu context; removing the command guide from the activity pane must not remove discoverability from the application.
- Add interaction and snapshot coverage for idle, form, history, completed-result, active-progress, cancellation, and resize states.

### Out of scope

- Changing SSH, RPM parsing, inspection scheduling, cancellation semantics, persistence, or normalized result models.
- Adding remote operations, installation, upgrade, reboot, shell execution, APT, Ansible, or Proxmox behavior.
- A full animation framework, graphical effects, mouse interaction, or user-configurable animation themes.
- Inventing target-level percentage progress when the inspection service exposes only target completion.
- Moving or redesigning every Posting pane beyond the activity-pane content and the minimum layout changes needed to preserve the existing geometry.

## Requirements

### Activity-pane behavior

R1. The pane currently identified as `#navigation-pane` must not render the persistent four-item action guide while a non-idle workflow is active. It must show only the current activity/context, such as entering a one-off target, selecting saved targets, loading history, showing results, or inspecting targets.

R2. The activity text must remain explicit and readable without colour or animation. A stopped animation must still leave a meaningful textual state.

R3. Idle/menu state must expose the amended `a` Action, `i` Inventory, and `h` History workflows through a visible, non-crossed-out command guide in an appropriate location. Action must select an operation before selecting hosts; Inventory must expose list, edit, add, and delete choices. The change must not remove the existing history workflow or inventory persistence semantics.

R4. Forms, action selection, host selection, inventory management, history, result, modal, and cancellation workflows must retain their existing controls, focus, values, and semantics.

### Running inspection feedback

R5. While `inspection_worker` is active, the activity pane must show an animated loading indicator and text identifying that read-only inspection is running.

R6. When the selected target total is known, active progress must include completed and total target counts. Completed target results must update the count as they arrive through the existing result callback.

R7. When no reliable total is available, the UI must use indeterminate activity feedback and must not display a fabricated percentage or completion count.

R8. The activity indicator must stop when inspection completes, is cancelled, or fails. The final pane state must describe the resulting summary or cancellation/failure rather than leaving a stale spinner running.

R9. `Cancel batch` must remain visible and reachable while the animation is active. Cancelling must retain the existing worker cancellation and history behavior.

R10. Animation updates must be presentation-only: they must not invoke inspection, registry, history, SSH, or RPM-provider operations and must not create duplicate workers.

### Responsive and accessibility behavior

R11. The activity pane must remain usable at `40x20`, `80x24`, and `120x40`. At compact sizes it may collapse to a single line or short wrapped status, but it must not obscure the main workflow or cancel control.

R12. Resizing during inspection must preserve the active worker, completed results, selected inputs, focus where applicable, and the current progress counts. Reflow must not restart or duplicate animation work.

R13. The animation must use terminal-safe characters and modest timing. Text labels must carry all operational meaning; animation and colour are supplementary signals.

## Implementation notes

- Keep activity state on `DispatchApp` and derive the rendered pane from `view`, `inspection_worker`, `results`, and known target-count state.
- Prefer a Textual timer or message-driven update owned by the app and stop it deterministically when the worker completes or is cancelled.
- Keep timer callbacks side-effect-free with respect to domain services; they may update only presentation state.
- Use the existing `_result_completed` callback to update completed-target progress rather than adding a second inspection callback contract.
- Preserve the existing `#navigation-pane` identity and titled-pane geometry unless tests demonstrate that a smaller activity presentation requires a documented structural adjustment.
- Keep the idle command guide in the main menu content or another clearly named normal-screen area and update tests to distinguish activity text from command discoverability.
- Add a reusable discovery lesson only if implementation reveals a non-obvious Textual timer, worker, or resize constraint not already covered by `docs/discovery/textual-pane-layouts.md`.

## Acceptance criteria

1. The persistent activity pane no longer displays crossed-out or irrelevant command bindings during active workflows.
2. Idle/menu, form, history, result, and modal states show concise current-context text without losing the four existing global workflow shortcuts.
3. An active multi-target inspection displays a terminal-safe animated indicator, explicit read-only activity text, and `completed/total` target progress when the total is known.
4. The indicator stops and the pane changes to a truthful final state after success, cancellation, or failure.
5. No animation or pane refresh starts duplicate inspection work or causes registry/history/remote side effects.
6. Cancel remains reachable and existing worker cancellation semantics are unchanged.
7. Resize transitions `120x40 -> 40x20 -> 120x40` preserve active work, form state, results, focus where applicable, and progress state.
8. Targeted interaction tests, snapshots for required viewports, and the complete `uv run pytest` suite pass.
9. The feature specification, root recent-feature table, and exhaustive feature index are updated consistently when implementation begins and when the feature completes.

## Validation

### Test-driven development

For each production behavior, add a focused interaction test first and run it to demonstrate the expected failure. Implement the smallest presentation change, rerun the focused test, then run the complete suite.

### Required tests

- Idle menu retains visible `a` Action, `i` Inventory, and `h` History discoverability without crossed-out entries.
- Action selection precedes host selection, and Inventory exposes list, edit, add, and delete choices without changing the underlying registry format.
- Each non-idle view renders current-context text in the activity pane and does not render the persistent action guide there.
- Active inspection starts the animation and exposes `Cancel batch`.
- Multi-target progress changes from `0/N` to `N/N` as result callbacks arrive.
- Unknown-total activity uses an indeterminate spinner without a fabricated percentage.
- Completion, cancellation, and failure stop the animation and render truthful final text.
- Timer/animation ticks do not call inspection, registry, history, or transport services.
- Resize during active progress preserves worker identity, results, counts, focus where applicable, and cancellation.
- Snapshots cover idle, active progress, completed result, cancellation/failure, `40x20`, `80x24`, and `120x40` states.

### Commands

```bash
uv sync --all-groups
uv run pytest tests/test_tui.py::<targeted-test>
uv run pytest tests/test_tui.py --snapshot-update
uv run pytest
```

Snapshots must be visually reviewed before accepting updated baselines; the final suite must run without `--snapshot-update`.

## Risks

| Risk | Mitigation |
| --- | --- |
| A timer leaks after work finishes and leaves stale animation. | Store one timer handle, stop it in every terminal worker path, and assert post-completion stability. |
| Animation causes unnecessary rerenders or hides controls at narrow sizes. | Use a modest interval, update one stable widget, and snapshot all required viewports. |
| Progress implies more precision than the service provides. | Report target-level counts only; use indeterminate feedback when totals are unavailable. |
| Removing the command guide makes the app undiscoverable. | Keep the guide in idle/menu content and test all four shortcuts. |
| Responsive reflow restarts active work. | Keep animation and activity state on the app, not in recreated widgets; test resize during progress. |

## Settled decisions

- Rename the persistent top pane from `Menu` to `Activity`. It must show only the current status and must not repeat the existing `a`, `i`, and `h` menu items already displayed in the top-level application menu/content.
- Start with a spinner-only presentation. Do not add a progress bar in this feature.
- Use the first status wording series, with terminal-safe spinner frames:
  - Idle: `Ready`
  - One-off form: `Entering one-off target`
  - Saved-target form: `Selecting saved targets`
  - Management form: `Managing saved targets`
  - History: `Loading local history`
  - Running: `⠋ Connecting to targets (read-only)` or `⠙ Inspecting targets (read-only)`
  - Complete: `✓ Inspection complete`
  - Cancelled: `! Inspection cancelled`
  - Failed: `× Inspection failed`
- Spinner frames are supplementary; the status text must remain meaningful when animation is not visible.

## Amendments

- Add documentation hygiene to this feature's closeout scope: repair the top-level README Markdown table so its header, separator, and rows are contiguous and render consistently; create `docs/README.md` and `docs/discovery/README.md` as OKF-compliant indexes; link both indexes from the repository structure and relevant documentation; and keep the feature index exhaustive.
- The documentation-index work is content-only and must not change Dispatch runtime behavior, workflow bindings, or the activity/progress design.
- Rename the current `o` One-off action binding to `a` Action. Action opens an action-first workflow: the operator selects the action to run, then selects the hosts on which to run it. The existing one-off target flow becomes part of the action workflow rather than remaining a top-level menu item.
- Rename the current `m` Manage binding to `i` Inventory. Inventory opens an inventory-management workflow with explicit list, edit, add, and delete choices for saved hosts/targets. The existing saved-target registry remains the inventory data source; this amendment changes the user-facing navigation and workflow entry point, not the persistence model.
- Keep `h` as History for this feature. Remove `s` as a top-level action once the amended navigation is implemented.
- Update the feature's interaction tests, snapshots, documentation indexes, and any current binding references to use `a` Action, `i` Inventory, and `h` History. Do not implement these navigation changes until the amended specification is reviewed and approved.

## Sources

- [Repository working instructions](../../AGENTS.md)
- [Dispatch Textual application](../../src/dispatch/tui.py)
- [Dispatch TUI tests](../../tests/test_tui.py)
- [Textual pane layout lessons](../discovery/textual-pane-layouts.md)
- [RPM update discovery dashboard](2026-09-18-18-58-rpm-update-discovery.md)

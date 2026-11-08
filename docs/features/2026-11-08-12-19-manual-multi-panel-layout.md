---
type: feature-specification
title: Manual multi-panel layout toggle
author: Hermes
status: in_progress
description: Make the Dispatch TUI use one full-size content panel by default and expose an explicit command for switching to the multi-panel layout.
tags:
  - tui
  - layout
  - responsive
  - keyboard
sources:
  - id: tui
    title: Dispatch Textual user interface
    path: ../../src/dispatch/tui.py
  - id: tui-tests
    title: Dispatch TUI tests
    path: ../../tests/test_tui.py
  - id: repository-guidance
    title: Repository development guidance
    path: ../../AGENTS.md
---

# Manual multi-panel layout toggle

## Context

Dispatch currently derives its layout from terminal dimensions. In particular, a short viewport such as a phone viewport with the on-screen keyboard visible receives the compact single-panel layout, while the same phone without the keyboard can receive the multi-panel layout. This makes the UI switch presentation modes because the available height changed, rather than because the operator chose a different view.

The single large content panel shown in the full-screen reference is the preferred presentation for normal use. The existing multi-panel presentation remains useful when an operator deliberately wants separate current-action, return-status, and detail panes.

The existing `d` binding toggles package details and must retain that meaning.

## Goal

Make the single large panel the stable default regardless of viewport height or keyboard visibility, and provide an explicit keyboard command to toggle the multi-panel presentation.

## Scope

In scope:

- Dispatch TUI layout state and Textual CSS/class application.
- A new documented keyboard binding for toggling single-panel versus multi-panel presentation.
- Regression tests proving that resizing, including height changes representative of an on-screen keyboard, does not implicitly change the selected layout.
- Regression tests proving that the explicit toggle changes pane visibility/geometry and can be toggled back.
- Updating the relevant TUI documentation and feature indexes.

Out of scope:

- Changing the content, wording, colours, borders, or behavior of the existing panes.
- Changing the `d` package-detail binding.
- Removing responsive handling needed for narrow widths or modal dialogs.
- Changes to workflow execution, inspection, SSH transport, persistence, or external systems.

## Requirements

1. A newly created `DispatchApp` must start in single-panel mode.
2. Single-panel mode must show the activity pane and one large main content pane, with the status and detail panes hidden. It must remain selected when the terminal is resized in width or height.
3. Multi-panel mode must be entered and exited only through an explicit keyboard action. Use the `m` key and label the binding `Multi-panel`.
4. Multi-panel mode must expose the existing separate current-action, return-status, and detail panes using the current wide layout behavior.
5. Pressing `m` must not change the current view, results, selected controls, typed input, focus, `show_details` state, or active inspection/workflow.
6. Pressing `d` must continue to toggle package details independently of the layout mode.
7. A resize event must reapply the selected layout without inferring layout mode from viewport height. Keyboard-induced height changes must therefore not switch modes.
8. Existing narrow-width handling and modal presentation must remain functional.
9. No commit, push, deployment, or feature closeout is performed as part of this work unless separately requested.

## Acceptance criteria

- Focused TUI tests assert the default single-panel mode at both a wide/full-height viewport and a short viewport.
- A focused TUI test presses `m`, verifies multi-panel visibility/geometry, resizes to a short viewport, and verifies multi-panel mode remains selected.
- The same test presses `m` again and verifies the single-panel layout is restored without losing view state or result content.
- A focused regression test verifies `d` still controls package details independently from `m`.
- Existing TUI and complete repository test suites pass.
- `git diff --check` passes.

## Implementation notes

- Replace the current height-based compact-layout decision with an explicit layout-mode state, defaulting to single-panel.
- Keep the existing pane structure and content generation where possible; make CSS classes reflect the explicit mode rather than viewport height.
- The toggle action should be safe before and during active work and should only update presentation.
- Add tests before implementation and run them red, then implement the smallest root-cause change and rerun focused and full suites.

## Risks

- Removing automatic compact selection could expose more content than fits on a short viewport; the main panel must remain scrollable and narrow-width handling must still avoid unusable horizontal layouts.
- A new binding could conflict with an existing command; verify all bindings before implementation and preserve `d`.
- Snapshot tests may encode the old automatic layout. Update only snapshots and assertions that directly describe the intentional new default or explicit multi-panel mode.

## Validation

Run the focused layout and TUI tests first, then the complete test suite. Review changed source, tests, documentation, and snapshots; run `git diff --check`; and verify the working tree contains no unrelated changes.

## Amendments

- Added `Multi-panel (m)` to the visible menu command list so the new layout binding is discoverable without relying on external documentation.

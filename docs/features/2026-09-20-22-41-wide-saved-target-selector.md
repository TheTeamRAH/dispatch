---
type: feature-specification
title: Wide saved-target selector visibility
description: Ensure saved targets are visibly selectable in the wide Posting layout.
status: in_progress
tags:
  - dispatch
  - tui
  - textual
  - responsive-design
sources:
  - id: user-conversation-2026-09-20
    title: Wide saved-target selector report
    description: Product-owner screenshot and requirements supplied during this session.
  - id: dispatch-tui
    title: Dispatch Textual application
    path: ../../src/dispatch/tui.py
  - id: dispatch-tui-tests
    title: Dispatch TUI tests
    path: ../../tests/test_tui.py
  - id: textual-layout-discovery
    title: Textual pane layout lessons
    path: ../discovery/textual-pane-layouts.md
---

# Wide saved-target selector visibility

## Context

Dispatch uses the Posting layout: Menu at the top, Current Action and Return Status stacked at left, and Detail at right.[^dispatch-tui] In the Saved-targets workflow, the selectable `SelectionList` is mounted in Current Action while saved-target context is also rendered in Detail.[^dispatch-tui] The product owner supplied a wide-layout screenshot showing target names in Detail but no visible options within Current Action. The selector has a two-cell height, which leaves no interior option row after its border.[^user-conversation-2026-09-20][^dispatch-tui]

[^user-conversation-2026-09-20]: [Wide saved-target selector report](#sources)
[^dispatch-tui]: [Dispatch Textual application](../../src/dispatch/tui.py)
[^dispatch-tui-tests]: [Dispatch TUI tests](../../tests/test_tui.py)
[^textual-layout-discovery]: [Textual pane layout lessons](../discovery/textual-pane-layouts.md)

## Goal

Make saved targets visibly selectable from Current Action in the wide Posting layout without changing saved-target data, inspection behavior, shortcuts, or compact layout behavior.

## Scope

### In scope

- Increase the wide-layout `SelectionList` height so it has visible option rows inside its border.
- Retain the compact selector height and its existing visible-option behavior.
- Preserve the `s` shortcut, target selection semantics, focus, `Inspect selected` button, and Detail-pane context.
- Add a targeted interaction/layout regression test at `120x40` that verifies the mounted saved-target selector has at least two visible interior option rows.
- Refresh affected TUI snapshots and validate the full test suite.

### Out of scope

- Changing target registry contents, target labels, selection semantics, inspection execution, or keyboard bindings.
- Changing pane geometry, colours, Menu content, Detail content, or Return Status content beyond the selector height needed to expose its options.
- Introducing a new layout, breakpoint, scrolling model, or dependency.

## Requirements

R1. At `120x40`, after `s` opens Saved targets with two saved targets, Current Action must display both option rows within the `SelectionList` border.

R2. The selector must reserve at least two interior option rows, in addition to its top and bottom border rows. Its rendered height must therefore be at least four terminal rows.

R3. The `Inspect selected` button remains visible and keyboard reachable after the selector.

R4. At compact sizes (`width <= 60` or `height <= 30`), retain the existing four-row selector rule and behavior.

R5. The Detail pane may continue to show saved-target context in wide layout, but it must not be the only visible location of target choices.

R6. The change is presentation-only. It must not invoke registry or inspection services beyond the existing `s` workflow behavior.

## Constraints

- Change only the minimum CSS and tests necessary to fix wide selector visibility.[^textual-layout-discovery]
- Preserve mounted widget state and focus during presentation changes.[^textual-layout-discovery]
- Use the existing Textual widgets and test tooling; do not add dependencies.

## Implementation Notes

- Update the non-compact `#content SelectionList` CSS rule in `src/dispatch/tui.py`; keep the compact override explicit and unchanged unless the smallest correct CSS change requires consolidation.
- Add the regression to `tests/test_tui.py` near the existing compact saved-target visibility test. Use `run_test(size=(120, 40))`, invoke `s`, obtain `#saved-targets`, and assert its geometry supports the required option rows and that `Inspect selected` remains visible.
- Update only snapshots affected by the visual height change after reviewing the rendered results.

## Risks

| Risk | Mitigation |
| --- | --- |
| A taller selector crowds the action button in a left pane. | Assert the button remains visible at `120x40` and review the saved-target snapshot. |
| A CSS change accidentally changes compact behavior. | Retain and run the compact saved-target visibility regression. |
| A presentation change alters inspection behavior. | Use the existing saved-target interaction tests and run the complete suite. |

## Validation

### Test-driven development

1. Add the targeted wide-selector regression and run it before CSS changes; it must fail because the current selector height is two rows.
2. Apply the minimum CSS change and rerun that targeted regression; it must pass.

### Commands

```bash
uv run pytest tests/test_tui.py::test_wide_saved_target_selector_shows_options
uv run pytest tests/test_tui.py::test_small_terminal_keeps_menu_guide_and_saved_target_options_visible
uv run pytest tests/test_tui.py --snapshot-update
uv run pytest
```

### Manual review

1. Start `uv run dispatch` in a `120x40` or larger terminal.
2. Press `s` with at least two saved targets.
3. Confirm both targets appear as selectable rows in Current Action, not only as Detail text.
4. Confirm `Inspect selected` remains visible, select a target, and start inspection using the existing control.
5. Resize to a compact viewport and confirm the selector still exposes its compact option rows.

## Acceptance Criteria

1. At `120x40`, Current Action visibly displays at least two saved-target option rows inside its selector border.
2. The wide selector is at least four terminal rows high and `Inspect selected` remains visible and reachable.
3. Compact Saved targets continues to show its existing visible options.
4. No registry or inspection semantics change.
5. Targeted regressions, refreshed snapshots, and `uv run pytest` pass.

## Sources

- [Wide saved-target selector report](#sources)
- [Dispatch Textual application](../../src/dispatch/tui.py)
- [Dispatch TUI tests](../../tests/test_tui.py)
- [Textual pane layout lessons](../discovery/textual-pane-layouts.md)

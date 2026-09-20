---
type: discovery
title: Textual pane layout lessons
description: Reusable constraints for responsive multi-pane Dispatch screens.
tags:
  - textual
  - tui
  - responsive-design
  - layout
sources:
  - id: dispatch-tui
    title: Dispatch Textual application
    path: ../../src/dispatch/tui.py
  - id: dispatch-tui-tests
    title: Dispatch TUI tests
    path: ../../tests/test_tui.py
---

# Textual pane layout lessons

- Budget fixed navigation and detail-pane widths against the `80x24` viewport before adding a flexible workspace pane. Oversized fixed sidebars cause wrapped workspace text and controls to fall below the visible terminal region.[^dispatch-tui][^dispatch-tui-tests]
- Preserve workflow widgets while changing presentation by updating stable container classes rather than remounting form controls. This retains entered values, selection, focus, and active worker state across layout changes.[^dispatch-tui]
- Keep status styling in the TUI layer. A successful query with unknown advisory or reboot metadata needs warning styling even though its normalized outcome remains `success`.[^dispatch-tui]

[^dispatch-tui]: [Dispatch Textual application](../../src/dispatch/tui.py)
[^dispatch-tui-tests]: [Dispatch TUI tests](../../tests/test_tui.py)

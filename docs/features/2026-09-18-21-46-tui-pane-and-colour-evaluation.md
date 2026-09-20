---
type: feature-specification
title: TUI pane and colour evaluation
description: Define switchable multi-pane Dispatch interface variants and a dark operational colour system for operator evaluation.
status: in_progress
tags:
  - dispatch
  - tui
  - responsive-design
  - visual-regression
  - textual
sources:
  - id: user-conversation-2026-09-18
    title: TUI pane and colour evaluation request
    description: Product-owner requirements and evaluation decisions supplied during this session.
  - id: existing-tui
    title: Dispatch Textual application
    path: ../../src/dispatch/tui.py
  - id: existing-tui-tests
    title: Dispatch TUI tests
    path: ../../tests/test_tui.py
  - id: rpm-update-discovery-spec
    title: RPM update discovery dashboard
    path: 2026-09-18-18-58-rpm-update-discovery.md
  - id: terminal-apps-gallery
    title: Terminal Apps gallery
    url: https://terminal-apps.dev/
  - id: textual-css-guide
    title: Textual CSS guide
    url: https://textual.textualize.io/guide/CSS/
  - id: textual-testing-guide
    title: Textual testing guide
    url: https://textual.textualize.io/guide/testing/
  - id: posting-repository
    title: Posting repository
    url: https://github.com/darrenburns/posting
  - id: posting-themes
    title: Posting built-in themes
    url: https://raw.githubusercontent.com/darrenburns/posting/main/src/posting/themes.py
---

# TUI pane and colour evaluation

## Context

Dispatch currently presents every workflow in one scrolling text surface, with controls dynamically mounted below it.[^existing-tui] The initial RPM-discovery feature requires the application to remain responsive at `40x20`, `80x24`, and `120x40` cells, preserve active workflow state across resize, and be covered by Textual interaction and visual snapshot tests.[^rpm-update-discovery-spec]

The product owner wants a more visually expressive, pane-oriented interface informed by the terminal-application examples in Terminal Apps.[^user-conversation-2026-09-18][^terminal-apps-gallery] They explicitly want to evaluate several layouts and narrow-terminal presentations in a running application before selecting a permanent design. They selected a dark operational palette.

[^user-conversation-2026-09-18]: [TUI pane and colour evaluation request](#sources)
[^existing-tui]: [Dispatch Textual application](../../src/dispatch/tui.py)
[^existing-tui-tests]: [Dispatch TUI tests](../../tests/test_tui.py)
[^rpm-update-discovery-spec]: [RPM update discovery dashboard](2026-09-18-18-58-rpm-update-discovery.md)
[^terminal-apps-gallery]: [Terminal Apps gallery](https://terminal-apps.dev/)
[^textual-css-guide]: [Textual CSS guide](https://textual.textualize.io/guide/CSS/)
[^textual-testing-guide]: [Textual testing guide](https://textual.textualize.io/guide/testing/)
[^posting]: [Posting repository](https://github.com/darrenburns/posting)
[^posting-themes]: [Posting built-in themes](https://raw.githubusercontent.com/darrenburns/posting/main/src/posting/themes.py)

## Goal

Provide a safe evaluation UI that retains every existing Dispatch workflow and introduces three visibly distinct multi-pane layouts, three selectable compact presentations, and consistent semantic colour. An operator can switch among the variants live and evaluate them without rerunning discovery or losing UI state.

## Scope

### In scope

- Replace the single `Static` presentation surface with persistent structural panes and view-specific content within them.
- Provide three selectable desktop layouts at `80x24` and `120x40`:
  - **Split workspace**: persistent navigation rail, primary workflow/results pane, and contextual detail pane when result or history data exists.
  - **Three-column operations board**: navigation rail, target/run list pane, and selected-target detail pane; no selected target displays an explicit empty state.
  - **Dashboard grid**: top-level status/metric region and independently bordered workflow, list, and detail regions; it must still expose the same data and controls.
- Provide three selectable compact presentations below 51 columns:
  - **Focused**: one pane at a time with visible Back/Esc navigation between navigation, list, and detail.
  - **Stacked**: panes appear in a vertically scrollable single column.
  - **Dual pane**: navigation plus one workspace pane; detail opens as the workspace pane.
- Provide the selected dark operational palette:
  - dark slate/near-black application background and elevated pane surfaces;
  - cyan/blue accent for focus, active navigation, and selected content;
  - green for successful or known healthy states;
  - amber for unknown, skipped, cancelled, or in-progress states;
  - red for connection, authentication, host-trust, unsupported-provider, and discovery failures;
  - muted neutral text for secondary instructions and absent/empty states.
- Apply status colour through semantic CSS classes or equivalent view-layer state, not through changes to domain result values.
- Keep clear text labels alongside all colour indications; colour must not be the only status signal.
- Keep the existing menu, one-off inspection, saved-target selection, target management, progress/cancellation, password, preflight-failure, remove-all confirmation, summary/detail, history, and history-detail workflows functional.[^existing-tui][^rpm-update-discovery-spec]
- Add an always-visible evaluation hint in the application chrome explaining `1`, `2`, and `3` select the layout variant, and `b` cycles compact presentation. The `b` key may update the selected compact presentation at any width but changes the visible layout only below 51 columns.
- Preserve `o`, `s`, `m`, `h`, `d`, and Escape's existing workflow semantics. Layout controls must not start SSH work, alter saved targets/history, or dismiss a modal.
- Preserve all current responsive state guarantees: form input, selection, focus, result data, active inspection work, cancellation, modal state, and scroll position remain intact when switching variants or resizing.[^rpm-update-discovery-spec]
- Update Textual interaction tests and visual snapshots to cover each evaluation variant and every existing practical workflow.

### Out of scope

- Selecting a final permanent pane design or removing evaluation variants. The product owner will make that decision after hands-on testing.
- Changing SSH, package-discovery, registry, history, model, workflow, or remote-command behavior.
- Adding user-persisted theme/layout preferences, a light theme, custom colour configuration, mouse-driven pane resizing, or a terminal colour capability configuration screen.
- Changing the existing minimum supported viewport or the underlying interaction key bindings listed above.

## Requirements

### Layout and interaction

R1. The application root must have discrete navigation, primary-workspace, and detail/list presentation regions rather than rendering all normal-screen content as one formatted string in one `Static` widget.

R2. Each desktop layout must make the current workflow action, applicable target/run context, and applicable selected-target/detail data reachable without requiring a mode not present in that layout. It may redistribute regions, but cannot remove information or controls.

R3. In result and history-detail views, the primary summary and package details must appear in separate visual regions when the selected desktop layout has room for them. `d` continues to toggle package details as required by the existing feature; hidden details must display an explicit affordance.

R4. Saved-target selection and history must show list context in a list-oriented pane in layouts that expose one. A selected saved target or run must receive the active/selected accent treatment as well as normal Textual focus behavior.

R5. Management and one-off forms must keep their existing inputs and controls. Their instructions and current saved-target context may be distributed across panes, but all controls remain keyboard reachable.

R6. During progress, completed target results update their relevant list/detail/status region as they arrive. The Cancel batch control remains prominent and reachable in every layout.

R7. The three layout variants are selected by `1`, `2`, and `3`, respectively, in the order defined under Scope. Pressing one selects that layout idempotently. Selection is session-only and defaults to Split workspace on application start.

R8. Pressing `b` cycles compact presentation in this order: Focused, Stacked, Dual pane, then Focused. The choice is session-only and defaults to Focused. The evaluation hint must name the active desktop layout and compact presentation.

R9. Layout changes and responsive reflow are presentation-only. They must not recreate or duplicate an inspection worker, invoke a registry/history method, submit input, trigger a button action, or connect to a target.

R10. At 50 columns or fewer, the active compact presentation supersedes the desktop variant. At 51 columns and above, the active desktop variant is restored. This boundary retains the prior narrow-screen contract.[^existing-tui]

R11. Modals retain their existing intentional isolation. They use the dark palette and accessible focus treatment but do not expose layout-selection controls or react to `1`, `2`, `3`, or `b` while open.

### Colour and visual hierarchy

R12. Use Textual CSS to define a named dark operational palette and apply it consistently to the application background, panes, borders, labels, inputs, buttons, selection, focus, footer/header or replacement chrome, and modals.[^textual-css-guide]

R13. Each pane must have a visible boundary or background contrast. The active pane and current navigation action must be more visually prominent than inactive panes without obscuring text readability.

R14. Apply semantic result styling from the existing `Outcome`, `SecurityState`, `CurrentRebootState`, and `RebootForecast` values. Successful outcomes and known non-problem states use green; unknown/skipped/cancelled/in-progress use amber; failure outcomes use red; active selection/focus uses cyan/blue. A state such as `reboot required` or `forecast likely` must retain its explicit text and may use amber rather than green.

R15. No text, border, input value, button label, status label, or selection indicator may depend on colour alone. The test suite need not perform a contrast-ratio calculation, but snapshots and manual review must confirm that every state remains identifiable by text and terminal-safe styling.

### Compatibility and safety

R16. This feature changes presentation only. It must preserve the completed RPM update discovery specification's idle-on-open behavior, read-only remote behavior, masked password handling, and history/registry semantics.[^rpm-update-discovery-spec]

R17. Existing interaction tests must remain valid unless their assertion intentionally targets replaced structural widgets or revised visual text. Revise such tests to assert the equivalent user-visible behavior, not internal markup.

R18. No desktop or compact variant may truncate an action or data required by the first feature. It may use scrolling, focused navigation, or an explicit empty state where terminal space is constrained.

## Implementation Notes

- Refactor `src/dispatch/tui.py` incrementally. Preserve workflow state on `DispatchApp`; render it into stable pane widgets rather than rebuilding inputs/controls during a layout switch.
- Use Textual containers and CSS classes to express pane geometry and active/semantic states. Do not introduce a second rendering toolkit or a runtime dependency.
- Keep layout selection and compact-presentation selection as explicit app state. Update CSS classes and pane visibility/reflow from that state and the existing `Resize` event.
- Controls presently mounted with `form-control` must remain associated with their owning view. Moving an existing mounted widget to a new container is acceptable only if its value, focus, and behavior survive layout changes.
- Status-to-style mapping belongs in the TUI layer and must not modify frozen models or persisted results.
- Replace snapshots only after visual review. Snapshot baselines are terminal-cell renderings; retain a representative assertion for status text so palette-only regressions do not hide semantic regressions.[^textual-testing-guide]
- Non-material implementation discretion: exact pane titles, border glyphs, spacing, metric labels, and the precise dark-slate/cyan/green/amber/red colour values may be chosen during implementation as long as they meet the defined hierarchy and semantic roles.

## Validation

### Test-driven development

For each production behavior, first add its targeted test and run it to demonstrate failure before the corresponding implementation. Then make the smallest implementation change and rerun the same command to demonstrate passing behavior.[^rpm-update-discovery-spec]

### Required automated tests

- Test the default Split workspace state and direct selection of layouts 1, 2, and 3.
- Test `b` cycles Focused, Stacked, and Dual pane in order, and assert the active-presentation hint changes.
- Test a desktop-to-narrow-to-desktop transition for every layout variant, ensuring the selected layout and compact presentation are restored/retained correctly.
- Test each compact presentation at `40x20` and assert its expected visible pane behavior or navigation path.
- Test layout switching during one-off form input, saved-target selection, management input, history detail with package details toggled, each modal, and active progress. Verify existing state, focus where applicable, and active inspection-call count are preserved.
- Test semantic status rendering associates success, unknown/cancelled, failure, and active selection with their distinct TUI classes or attributes while retaining their textual labels.
- Retain tests proving layout keys do not initiate inspection or cause storage mutation.
- Update existing interaction tests for changed widget structure while continuing to test all existing workflows.
- Create and visually review snapshots for all three desktop layouts at `80x24` and `120x40`, all three compact presentations at `40x20`, and the existing practical modal/form/result/history/progress states. Do not omit a state solely because it is visually similar under a different variant.

### Commands

```bash
uv sync --all-groups
uv run pytest tests/test_tui.py::<targeted-test>
uv run pytest --snapshot-update
uv run pytest
uv run dispatch
```

Run the targeted test before and after implementation. Run `uv run pytest --snapshot-update` only after visual review, then run `uv run pytest` without snapshot updates to validate committed baselines.

### Manual evaluation procedure

1. Start `uv run dispatch` at `120x40` or a larger terminal.
2. Press `1`, `2`, and `3` to view Split workspace, Three-column operations board, and Dashboard grid; evaluate navigation, result scanability, and detail placement.
3. Resize to `40x20`, then press `b` to compare Focused, Stacked, and Dual pane compact presentations.
4. Use `o`, `s`, `m`, `h`, and `d` in each relevant variant; confirm all workflows and details remain reachable.
5. Enter non-secret form data, select saved targets, open a modal, and switch variants/resize; confirm the UI state remains intact.
6. Run an inspection and switch variants while progress is visible; confirm no duplicate target query starts and cancellation remains usable.
7. Inspect success, unknown, cancelled, and failure sample states; confirm their textual status and dark-palette semantic styling remain legible.

## Acceptance Criteria

1. Dispatch offers the three named desktop pane variants, selected live with `1`, `2`, and `3`, and starts in Split workspace.
2. At the narrow breakpoint, Dispatch offers the three named compact presentations, cycles them with `b`, and retains the chosen presentation and desktop variant across resize.
3. All existing Dispatch workflows, controls, data, and safety behavior remain usable and unchanged in meaning in every applicable variant.
4. Pane reflow and selection changes preserve form values, selections, focus, modals, completed results, and active work without duplicate inspection or persistence activity.
5. The dark operational palette consistently distinguishes active selection, success, uncertainty/in-progress, and failure while all status meaning remains explicit in text.
6. Automated interaction and snapshot tests cover the new selector behavior, semantic styling, existing workflows, narrow layouts, and resize behavior; `uv run pytest` passes.
7. The product owner can perform the manual evaluation procedure and select a final layout direction in a subsequent request without code changes or hidden setup.

## Risks

| Risk | Mitigation |
| --- | --- |
| Pane variants duplicate view logic and regress a workflow. | Keep one workflow state model and render it through layout containers; cover every existing practical view in interaction tests and snapshots. |
| Widget reparenting or rebuild loses entered data/focus. | Keep controls stable where possible and explicitly test variant switching/resize with populated forms and active selections. |
| Dense panes become unusable at narrow widths. | Make compact presentation an explicit evaluation dimension and retain scrolling/focused navigation at `40x20`. |
| Colour hides important semantics on different terminals. | Pair all colour with explicit labels, use terminal-safe Textual styles, and manually review representative state snapshots. |
| Evaluation controls interfere with workflow shortcuts. | Reserve only unclaimed `1`, `2`, `3`, and `b`; test they have no workflow or persistence side effects. |

## Amendments

- The product owner found that the Dashboard grid selected by `3` did not present equivalent completed-result and package-detail content to layouts 1 and 2. Dashboard must visibly render the normal summary/workflow pane, selected-target outcome and package-detail pane, and Operations Board status region. With a result loaded and `d` enabled, it must visibly show discovered package name and architecture in the detail region.
- The product owner requested that `b` visibly preview Focused, Stacked, and Dual compact presentations at every terminal width, including `80x24` and `120x40`; resizing must not be required to evaluate them. Before the first `b` press, desktop layouts retain their normal presentation above the narrow breakpoint. Once `b` is pressed, the active compact presentation takes visible precedence over the selected desktop layout at every width, retains the existing cycle order, and must preserve existing layout/workflow state guarantees.
- The product owner found that an active compact preview made `1`, `2`, and `3` appear unreliable because it continued to override their desktop layouts. Selecting any desktop layout with `1`, `2`, or `3` must exit compact-preview mode before applying that layout. The selected compact mode remains available for the next `b` press; at the narrow breakpoint, the responsive compact presentation remains active as before.
- The product owner requested a fourth evaluation layout inspired by Posting's top-navigation and multi-pane visual hierarchy.[^posting] Key `4` must select the **Posting split** layout: a thin full-width menu pane at the top of the workspace; beneath it, two vertically stacked panes on the left; and a larger right-hand detail pane filling the remaining workspace height. The top pane must expose Dispatch navigation and the active layout/compact hint. The upper-left pane must expose the normal workflow/summary content and retain mounted workflow controls. The lower-left pane must expose Operations Board status/context. The right pane must expose selected-target outcome and package details, including package name and architecture after `d`. Like keys `1`, `2`, and `3`, `4` must exit compact-preview mode before selecting the desktop layout. The layout must remain usable at `80x24` and participate in the existing narrow/compact presentation behavior, state-preservation tests, and visual snapshots.
- The product owner requested a Posting-inspired colour scheme for the evaluation UI. Replace the current dark-slate/cyan palette with Posting's Galaxy palette: near-black background `#0F0F1F`, deep-indigo surface `#1E1E3F`, indigo panel/border `#2D2B55`, purple primary `#C45AFF`, lavender secondary `#A684E8`, pink active accent `#FF69B4`, gold warning `#FFD700`, orange-red failure `#FF4500`, and mint-green success `#00FA9A`.[^posting-themes] Apply these colours consistently to application chrome, panes, controls, selection/focus, and modals. Existing explicit text labels and status classes remain mandatory; do not use colour as the sole status signal.
- The product owner requested black filled backgrounds with pastel purple/violet outlines only for every section. Superseding the surface portion of the prior Galaxy-palette amendment, the application background, header/footer, panes, inputs, buttons, and modal dialog fills must be black. Each visible section boundary must use a pastel violet outline, with no coloured section fill. Success, warning, and failure remain explicit in text and may use foreground styling, but must not replace a section's violet outline or use a coloured background.
- The product owner selected Posting split as the preferred visual base and requested corrections to its information hierarchy. Its full-width top navigation pane must render a non-blank horizontal menu, with Dispatch actions and active layout/compact hint arranged left-to-right rather than as a vertical stack. Beneath it, the left column must divide evenly into an upper current-action/context pane and a lower short return/status pane. The right pane must fill the remaining workspace height and render the full detailed workflow/result content, including package detail after `d`; it is no longer limited to the short target summary. Existing mounted controls remain in the upper-left current-action pane.
- The product owner found that a warning status caused all text to become yellow and that colour persisted after navigation. Semantic foreground styling must apply only to detailed result content while the active view is summary, progress, or history detail. It must be removed when the user navigates to another workflow. Navigation, current-action/context, status, forms, and menu text retain the default foreground colour; semantic meaning continues to be explicit in text.
- The product owner reported that Posting split did not visually meet its intended geometry: the top navigation pane was blank, the rendered menu appeared in the upper-left pane, and the lower-left pane was smaller than the upper-left pane. The top navigation widget must stretch to and render within the full-width top pane. The two left panes must use equal-height tracks and fill them; the lower-left return/status pane must not collapse to its content height.
- Snapshot review confirmed that the top navigation parent filled its grid track while its child menu widget collapsed vertically, leaving the visible pane blank. The menu widget must fill both the width and height of its parent pane, and automated layout tests must assert non-trivial rendered menu-widget height in addition to parent geometry.
- Investigation identified that Posting split declared only its grid column count. Its Textual grid must explicitly declare both dimensions as two columns and three rows so the spanning top menu, two left rows, and right-side spanning detail pane receive deterministic placement.[^textual-css-guide]
- The explicit grid dimensions still did not produce the intended runtime placement. Replace Posting split's auto-flow grid composition with nested structural containers: a dedicated top-level navigation child and a separate lower body containing a vertical left-column container and right-side detail container. The top menu must not share an auto-placement context with detail content.
- The product owner requested a slight grey-black fill for every pane, while retaining the black application background and pastel-violet outlines. Posting split must give its Menu, Current Action, Return Status, and Detail panes a subtle grey-black fill distinct from the application background. Each of those panes must expose a lavender border title that interrupts its top outline in the established terminal-panel style; titles are `Menu`, `Current Action`, `Return Status`, and `Detail`, respectively. These structural titles replace no required workflow/status text and remain present only while Posting split is selected.
- The product owner requested complementary colour hierarchy within result content. Summary metrics must use readable foreground colours against the grey-black panes: success is mint; package/update count is lavender; security information is sky blue; reboot-required, likely-reboot, unknown, skipped, cancelled, and in-progress states are gold; and errors remain orange-red. Labels and values remain textual, so colour is never their sole meaning.
- When a detailed result contains more than one host, each host must receive a distinct repeating pastel accent selected from lavender, sky blue, peach, and pink. That accent must visibly identify the host header and every package-detail line belonging to it, so adjacent host result sections are distinguishable at a glance. Single-host detail remains semantically coloured without an unnecessary host accent palette.
- The product owner requested that every action in Posting split's top menu render as an individual light-grey-background chip. Each chip contains its shortcut and label, retains readable foreground text, and remains separated from adjacent menu chips. The existing active-action indicator must remain visible; the chips do not change action bindings or menu text.
- The product owner selected Posting split as Dispatch's sole layout. Remove Split workspace, Three-column operations board, Dashboard grid, all `1` / `2` / `3` / `4` layout-selection bindings, layout-selection state/actions, and their evaluation tests/snapshots. Dispatch starts directly in Posting split and no longer exposes an active-layout hint.
- The product owner requested removal of the non-working compact-layout evaluator. Remove `b`, compact presentation state/actions/classes, desktop compact previews, and their tests/snapshots. At narrow widths, retain accessibility by stacking the same named Posting panes vertically in a scrollable flow; this is a single responsive Posting split presentation, not a selectable compact variant.
- The product owner requested a more efficient small-screen Posting presentation after reviewing a `104x27` terminal capture where the lower pane was clipped. At a terminal width of 60 cells or fewer, or height of 30 rows or fewer, show only the top Menu pane and one full-height Main pane. Hide Return Status and Detail rather than stacking/cropping them. The Main pane renders the complete active workflow, including forms/lists and full result/history detail; it must retain the same controls, data, focus, and keyboard actions. This automatic responsive presentation is not a selectable layout.
- The product owner reported that the first compact implementation left Menu blank and made saved-target options unavailable. The compact Menu pane must reserve enough interior rows for its one-line action chips after border and padding. Compact saved-target selection must reserve visible option rows in its `SelectionList`; do not duplicate the saved-target text list above that selector. For compact one-off, saved-target, management, and history workflows, render concise action context above their mounted controls; render full content only for the menu, completed-result, progress, and history-detail views.
- The compact Menu pane remained blank in the operator's terminal despite a nested menu widget rendering in headless tests. Remove the nested menu widget and render action chips directly in the titled Menu pane, so no child scroll/layout behavior can hide the menu text.
- The direct Menu pane still had no drawable row in compact mode because the common one-cell vertical pane padding consumed its two post-border rows. Preserve the Menu pane's horizontal padding but set its vertical padding to zero.
- The product owner prefers the concise binding-guide style currently rendered by Textual's bottom `Footer` over the top Menu pane's filled action chips. Remove `Footer` from the application entirely, including its CSS and import. The titled top Menu pane becomes the sole normal-screen command guide and must render the four existing action bindings (`o` One-off, `s` Saved, `m` Manage, `h` History) in the footer-style shortcut-and-label presentation: accent-coloured shortcut text, readable default-colour label text, black/grey-black pane background, and no filled chips or active-action marker. Preserve the existing action bindings and Escape semantics. Keep the Menu pane at the top and retain its visible violet border/title. Reduce its height to the minimum that displays its single command-guide row within its border at all responsive sizes, returning the freed vertical space to the result/workflow pane. Update TUI interaction assertions and snapshots at desktop, compact, and result states. Validate with the targeted Menu/layout tests, `uv run pytest tests/test_tui.py --snapshot-update`, and `uv run pytest`.

## Sources

- [TUI pane and colour evaluation request](#sources)
- [Dispatch Textual application](../../src/dispatch/tui.py)
- [Dispatch TUI tests](../../tests/test_tui.py)
- [RPM update discovery dashboard](2026-09-18-18-58-rpm-update-discovery.md)
- [Terminal Apps gallery](https://terminal-apps.dev/)
- [Textual CSS guide](https://textual.textualize.io/guide/CSS/)
- [Textual testing guide](https://textual.textualize.io/guide/testing/)
- [Posting repository](https://github.com/darrenburns/posting)
- [Posting built-in themes](https://raw.githubusercontent.com/darrenburns/posting/main/src/posting/themes.py)

---
type: feature
title: RPM discovery section-header handling
description: Prevent DNF section headers from being misclassified as package update rows during RPM update discovery.
tags:
  - rpm
  - dnf
  - discovery
  - bug-fix
sources:
  - id: rpm-provider
    title: Dispatch RPM discovery provider
    path: ../../src/dispatch/rpm.py
  - id: rpm-tests
    title: Dispatch RPM provider tests
    path: ../../tests/test_rpm.py
  - id: reported-reproduction
    title: Direct DNF reproduction of the Obsoleting Packages header
    description: The affected host returned exit status 100 and emitted an Obsoleting Packages section header.
status: proposed
---

# RPM discovery section-header handling

## Context

Dispatch invokes `LC_ALL=C dnf -q --color=never check-update` or the equivalent YUM command. Exit status `100` means updates are available, after which the provider parses the command output as package rows. The parser currently rejects DNF section headers such as `Obsoleting Packages` because they do not have the three fields expected of a package row. The resulting target status is `discovery_failed` even though the package manager completed the update check successfully.

## Goal

Allow valid DNF/YUM update output containing section headers to proceed through package discovery without weakening validation of malformed package rows.

## Scope

- Update the RPM update-output parser to ignore known non-row section headers emitted by DNF/YUM.
- Add a regression test reproducing the `Obsoleting Packages` failure.
- Preserve existing behavior for update rows, no-update output, unsupported package managers, non-success command statuses, malformed rows, security correlation, and reboot detection.
- Update the related discovery documentation if the implementation establishes a reusable parser lesson.

Out of scope:

- Changing remote command execution or SSH behavior.
- Changing DNF/YUM command arguments.
- Making package-manager errors more verbose in this fix.
- Supporting arbitrary localized output beyond the existing `LC_ALL=C` contract.

## Requirements

1. A DNF/YUM output section header that is not a package row must not cause `Outcome.DISCOVERY_FAILED` when the command exits with status `100`.
2. Valid package rows after or before the section header must still be returned as `PackageUpdate` values.
3. Malformed content that is not a recognized header must continue to raise the existing parse failure.
4. The regression test must assert successful discovery and the expected parsed package set.
5. Existing tests must remain green.

## Acceptance criteria

- [ ] A fixture or inline regression input containing `Obsoleting Packages` produces `Outcome.SUCCESS`.
- [ ] The expected update row is parsed with its name, architecture, candidate EVR, and repository.
- [ ] An unrecognized malformed line still produces `Outcome.DISCOVERY_FAILED`.
- [ ] `uv run pytest -q` passes.
- [ ] `git diff --check` passes.
- [ ] The changed files and test evidence are suitable for a reviewable pull request.

## Implementation notes

Use the existing parser boundary in `src/dispatch/rpm.py` and the established `tests/test_rpm.py` patterns. Follow test-driven development: add and run the smallest failing regression test before changing production code. Keep the parser strict for unknown malformed content; do not skip every non-package line indiscriminately.

## Risks

- DNF may emit additional stable section labels that need explicit handling.
- Overly broad header matching could hide a real parser regression.
- Fixture changes could accidentally alter security-advisory or reboot assertions.

## Validation

Run the focused RPM tests during implementation:

```bash
uv run pytest tests/test_rpm.py -q
```

Then run the complete suite and diff hygiene checks:

```bash
uv run pytest -q
git diff --check
```

## Amendments

None.

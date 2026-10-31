---
type: discovery
title: RPM discovery parser lessons
description: Reusable constraints for parsing DNF and YUM update output in Dispatch.
tags:
  - rpm
  - dnf
  - yum
  - parsing
sources:
  - id: rpm-provider
    title: Dispatch RPM discovery provider
    path: ../../src/dispatch/rpm.py
  - id: rpm-tests
    title: Dispatch RPM provider tests
    path: ../../tests/test_rpm.py
---

# RPM discovery parser lessons

- Treat DNF/YUM update output as a mixed stream: parse package rows strictly, but explicitly ignore stable section headers such as `Obsoleting Packages`.[^rpm-provider]
- Do not skip every non-package line indiscriminately. Unknown malformed content must remain a discovery failure so repository or format changes are visible.[^rpm-provider][^rpm-tests]
- Keep the package-manager locale fixed with `LC_ALL=C` before relying on stable human-readable headers.[^rpm-provider]

[^rpm-provider]: [Dispatch RPM discovery provider](../../src/dispatch/rpm.py)
[^rpm-tests]: [Dispatch RPM provider tests](../../tests/test_rpm.py)

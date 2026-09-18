---
type: discovery
title: AsyncSSH transport integration lessons
description: Reusable implementation constraints for Dispatch SSH connections and command execution.
tags:
  - asyncssh
  - ssh
  - transport
sources:
  - id: dispatch-transport
    title: Dispatch AsyncSSH transport implementation
    path: ../../src/dispatch/transport.py
  - id: asyncssh-api
    title: AsyncSSH API documentation
    url: https://asyncssh.readthedocs.io/en/latest/api.html
---

# AsyncSSH transport integration lessons

- Parse the supported `user@host` destination into a hostname and `username` option before calling `asyncssh.connect()`; passing the complete string as the host makes it a literal hostname.[^dispatch-transport]
- Supply SSH config and known-hosts paths only when they exist. In this environment, pass `known_hosts` as a string rather than a `Path` object.[^dispatch-transport]
- Use `connection.run(command, check=False)` for the provider command boundary. It yields completed text stdout/stderr and an exit status; `create_process()` exposes stream readers requiring separate consumption.[^dispatch-transport][^asyncssh-api]
- Bound every connection attempt. Dispatch uses a fixed 15-second preflight timeout and maps expiry to a retryable connection failure.[^dispatch-transport]

[^dispatch-transport]: [Dispatch AsyncSSH transport implementation](../../src/dispatch/transport.py)
[^asyncssh-api]: [AsyncSSH API documentation](https://asyncssh.readthedocs.io/en/latest/api.html)

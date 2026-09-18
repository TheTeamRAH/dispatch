# dispatch

A modular terminal user interface for dispatching infrastructure operations.

## Repo Structure

```text
.
├── AGENTS.md          # Repository working instructions
├── docs/
│   ├── discovery/     # Reusable implementation lessons
│   └── features/      # Feature specifications and their index
├── pyproject.toml     # uv-managed Python project metadata
├── src/dispatch/      # Dispatch application package
├── tests/             # Unit and Textual interaction tests
├── uv.lock            # Resolved project dependencies
└── README.md          # Project overview and contributor entry point
```

## Getting Started

Synchronize dependencies with `uv sync --all-groups`, run tests with `uv run pytest`, and start the TUI with `uv run dispatch`. Start by reading [AGENTS.md](AGENTS.md) before defining or implementing a feature.

## Recent Features

| Date | Purpose | Spec | Author |
| --- | --- | --- | --- |

| 2026-09-18-18-58 | RPM update discovery dashboard | [Spec](docs/features/2026-09-18-18-58-rpm-update-discovery.md) | OpenCode |

See [the complete feature index](docs/features/README.md).

## Contributing

This is an AI-first development repository. Point your agent or model at [AGENTS.md](AGENTS.md) before contributing.

- Draft a self-contained feature specification and have the user review it before creating a branch or implementing work.
- Follow the required documentation layout, timestamp filename rules, and OKF v0.2 frontmatter requirements.
- Consult `docs/discovery` before related work and record reusable lessons without duplication.
- Keep communication concise, source factual claims, and ask focused questions when material requirements are unclear.

# Repository Purpose

This repository is for a modular terminal user interface for dispatching infrastructure operations.

## Communication and Research

- Give brief, direct answers that address the request.
- Source factual statements. When research is needed, use multiple independent, relevant sources, cross-check their claims, and link the sources used. Prefer primary sources where practical.
- Be explicit when information is unknown, when more research is needed, or when user input is required. Ask clarifying questions whenever a material requirement is unclear.

## Repository Documentation

Use and maintain this structure:

```text
docs/
├── architecture/  # Architecture documentation, organized by area or technology.
├── features/      # Self-contained feature specifications.
├── decisions/     # Architecture decision records (ADRs).
├── discovery/     # Reusable lessons learned, organized by area or technology.
└── debugging/     # Debugging investigations and outcomes.
```

The `docs/` structure in this section defines the required documentation,
development, and learning system. It is not a complete inventory of project
source files or directories. Keep the detailed project structure in the root
README's `Repo Structure` section and do not reproduce it in `AGENTS.md`.

Every Markdown documentation artifact under `docs/` must conform to Open Knowledge Format (OKF) v0.2: [OKF specification](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md). Create normal documentation files as OKF concept documents: begin with YAML frontmatter containing at least a descriptive `type`. Also include `title`, `description`, `tags`, and provenance `sources` where applicable. Attribute source-specific claims with Markdown footnotes keyed to `sources` entries. Preserve unknown OKF frontmatter keys when updating a document. Use `index.md` and `log.md` only in their defined OKF roles and formats.

For timestamped documents, obtain the timestamp when creating the file. Do not calculate it manually:

```bash
date +"%Y-%m-%d-%H-%M"
```

Use the resulting prefix in this format: `YYYY-MM-DD-HH-MM-<purpose>.md`, where `<purpose>` is concise and lowercase-hyphenated.

- `docs/architecture`: Document architecture by area or technology. Do not use the timestamp filename convention.
- `docs/features`: Create feature specifications here. Use the timestamp filename convention.
- `docs/decisions`: Create ADRs here using the timestamp filename convention. Use Nygard style: `Title`, `Context`, `Decision`, `Status`, and `Consequences`. See Michael Nygard, [Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions).
- `docs/discovery`: Record reusable lessons by area or technology; do not use the timestamp filename convention. Consult this directory before related work. Keep it current and non-duplicative. When a mistake teaches a reusable lesson, document it here so it is not repeated.
- `docs/debugging`: Record investigations and outcomes using the timestamp filename convention. Consult `docs/discovery` before starting an investigation. If the outcome yields a reusable lesson, add or update the relevant discovery document after checking for existing coverage.

## Development Flow

1. Do not use Compound Engineering skills other than a review skill.
2. Do not run `git add` or `git commit` unless the user explicitly asks.
3. Before implementation, create a complete, self-contained feature specification in `docs/features`. Include context, goal, scope, requirements, acceptance criteria, constraints, implementation notes, risks, validation, and source links. Give a new context window, using only the specification and its cited repository sources, every fact, decision, constraint, dependency, relevant path, interface expectation, validation command or procedure, and source needed to implement, validate, and determine completion without prior conversation or unstated assumptions.
4. While drafting, resolve missing information, conflicting requirements, and choices that could materially change scope, externally visible behavior, architecture, risk, validation, or acceptance. Use authoritative repository evidence when available; otherwise ask the user focused clarifying questions. Do not invent material requirements or silently select among materially different interpretations. Clearly label non-material implementation discretion.
5. After drafting and before human review, review the specification from the perspective of an agent with only the specification and its cited repository sources. Confirm it says what to change and not change, why, the expected behavior, settled decisions, executable validation, and completion conditions. Remove unresolved placeholders, ambiguous references, hidden conversational context, unsupported assumptions, missing edge cases, incomplete acceptance criteria, and unusable validation steps. Revise to close every gap. If a material gap requires user input, ask and keep the specification in a draft or proposed state. Present it as ready for human review only when no material assumptions or required information remain unresolved.
6. Ask the user to review the specification. Do not implement until they ask to continue.
7. When the user asks to continue, create a new branch before implementation. Name it `<category>/<purpose>`, where category is `feature`, `fix`, or `explore` and purpose is succinct and lowercase-hyphenated. Immediately after branch creation, update the root `README.md` `Recent Features` table and `docs/features/README.md`, the exhaustive feature index. Keep both tables newest first and use the root README's `Date`, `Purpose`, `Spec`, and `Author` column format for each. Every `Date` cell must use the complete `YYYY-MM-DD-HH-MM` prefix from its linked feature specification filename, never a date-only value. Keep only the ten most recent features in the root README table.
8. When creating code, use test-driven development: write and run a test first, and confirm it fails because the implementation does not exist; then create the implementation and rerun the tests to confirm they pass. Prefer Python unless the user specifies another language. Use Bash only for simple work, mindful that it has no native testing capabilities; use an appropriately testable language for substantive code.
9. Implement and validate the approved specification on that branch.
10. After implementation and validation succeed, review all changed content. Review changed code for safe, worthwhile improvements to clarity, maintainability, duplication, and consistency; make and validate those improvements. Document newly created repository content in its appropriate location. If content was renamed, update relevant existing documentation and references. Assess whether the work produced a reusable lesson and, when it did, add or update the appropriate documentation, normally `docs/discovery`, without duplication. Check the root `README.md` `Repo Structure` section and update it when necessary. Maintain relevant repository documentation as a current source of knowledge.
11. If work stops before completion, perform the applicable quality, documentation, and reusable-learning review. Preserve the active feature specification's truthful lifecycle state and do not declare the feature complete.
12. If the user asks for a small change outside the current specification while its work is underway, record it in a new `## Amendments` section of that active feature specification before or alongside making the change. Before completion or a stopped-work handoff, ensure all such user requests are recorded there, including requests not implemented because work stopped. Keep the exact heading `Amendments`. Do not automatically amend a specification already marked `completed`. The sole exception is correcting a prematurely `completed` specification when it is the current work. If it is unclear whether a specification is active, completed, or prematurely marked complete, consult the user before changing it.
13. Before marking the active specification `completed` or declaring the feature complete, merge the current `main` branch into the feature branch. Resolve conflicts caused by parallel work, rerun affected validation, and preserve ordering and completeness in shared documentation indexes, including root README and feature-index tables.
14. After the completion review and branch synchronization succeed, run every applicable mandatory declared closeout stage under `Feature Closeout Workflow`. Mark the active feature specification's frontmatter status as `completed` only after implementation, validation, review, branch synchronization, and all applicable mandatory declared closeout stages reach a repository-permitted successful outcome.

## Project-Specific Instructions

This repository-owned section is the home for project or user-supplied purpose,
architecture and layout conventions, implementation rules, safety requirements,
validation procedures, release policy, and other project-specific guidance.
Preserve and consolidate compatible content here. Keep generic policy in the
other prescribed sections; project-specific instructions take precedence over
compatible generic defaults only. Do not invent guidance from technology,
layout, or repository convention. Ask the user before changing conflicting
semantics.

### Feature Closeout Workflow

No project-specific closeout stages are currently declared.

This inert default means no project-specific stage applies. A repository may replace it with explicit release preparation, pull-request, publication, deployment, or other closeout stages when needed. Each declared stage must define a unique human-readable name and execution order; trigger and prerequisite; mandatory or optional status; executor; authority and mutation scope; required inputs and minimum context; separate authorizations; evidence returned to `feature-completion`; passed, failed, unavailable, skipped, and not-applicable semantics; retry and fallback policy; and safe resume condition. A required but unavailable stage must be declared unavailable and blocking rather than omitted.

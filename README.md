# Financial Workflow Simulator

[![CI](https://github.com/Dellinghausen/financial-workflow-simulator/actions/workflows/ci.yml/badge.svg)](https://github.com/Dellinghausen/financial-workflow-simulator/actions/workflows/ci.yml)

A portfolio-grade, fully fictional backend that demonstrates how reliable financial
workflows can be designed, tested, and operated. The project focuses on correctness,
idempotency, explicit state transitions, auditability, and safe read-only access.

> [!IMPORTANT]
> This is an independent educational project. It does not contain or reproduce code,
> data, names, business rules, or system designs from any current or former employer.
> It never processes real money.

## Planned MVP

- Payment creation and asynchronous processing
- Idempotent commands and duplicate webhook handling
- A deterministic fictional provider with simulated failures and retries
- Explicit payment and settlement state machines
- A simplified double-entry ledger
- Reconciliation and settlement workflows
- Structured logs and an append-only audit trail
- An allowlisted, read-only MCP server
- PostgreSQL, Docker Compose, pytest, and GitHub Actions

## Architecture

The system is a modular monolith deployed as separate API, worker, provider simulator,
and MCP processes. PostgreSQL is both the system of record and the initial transactional
job queue. This keeps local operation approachable while still demonstrating transaction
boundaries, locking, retries, and at-least-once delivery semantics.

```text
Client -> FastAPI -> Application services -> Domain model
                   |                       |
                   +-> PostgreSQL <--------+
                          ^      |
                          |      +-> Worker -> Fictional provider
                          |
                    Read-only MCP
```

See [docs/architecture.md](docs/architecture.md) for scope, boundaries, and trade-offs.

## Current status

The repository foundation is complete. The health endpoint and engineering quality gates
are in place; payment workflows will be added in small, reviewable increments.

## Local development

Python 3.13 is required.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
pytest
ruff check .
mypy
financial-api
```

Open <http://localhost:8000/docs> for the generated API documentation.

Docker Compose support will be added with the PostgreSQL foundation in the next milestone.

## Development principles

- Store money as integer minor units, never binary floating-point values.
- Treat duplicates and retries as normal operating conditions.
- Keep business transitions explicit and independently testable.
- Make invalid states difficult to represent and impossible to persist silently.
- Prefer deterministic simulations over flaky randomness.
- Expose only purpose-built, read-only MCP tools; never expose arbitrary SQL.
- Record business audit events without logging secrets or sensitive payloads.

## Roadmap

The incremental roadmap and publication criteria are tracked in
[docs/roadmap.md](docs/roadmap.md).

## Security

Please read [SECURITY.md](SECURITY.md). Do not use this project for real financial data or
credentials.

## License

Licensed under the MIT License. See [LICENSE](LICENSE).

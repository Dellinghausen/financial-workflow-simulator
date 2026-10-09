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

The repository foundation and local PostgreSQL environment are complete. Liveness and
database-backed readiness probes are available; payment workflows will be added in small,
reviewable increments.

## Local development

The recommended path requires Docker with Compose support:

```bash
cp .env.example .env
docker compose up --build
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

The one-shot `migrate` service applies Alembic migrations after PostgreSQL becomes healthy;
the API starts only after migrations succeed. The API is ready only after it can execute a
query against PostgreSQL. Open <http://localhost:8000/docs> for the generated API
documentation.

For development without containers, Python 3.13 is required:

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

The non-containerized API expects PostgreSQL on `localhost:5432` unless `DATABASE_URL` is
overridden.

Create a payment with a client-generated idempotency key:

```bash
curl --request POST http://localhost:8000/payments \
  --header 'Content-Type: application/json' \
  --header 'Idempotency-Key: interview-demo-001' \
  --data '{"amount_minor": 1250, "currency": "USD"}'
```

Repeating the same key and body returns the same payment and sets
`Idempotent-Replayed: true`. Reusing the key with a different amount or currency returns
`409 Conflict`.

Payment creation also enqueues `PROCESS_PAYMENT` in the same database transaction. The
dedicated worker claims jobs with row-level locking, moves the payment to `PROCESSING`, and
acknowledges the job. Failed handlers are retried with bounded exponential backoff.

Schema changes are managed exclusively through Alembic:

```bash
alembic upgrade head
alembic downgrade -1
```

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

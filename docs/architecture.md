# Architecture

## Goals

The MVP demonstrates senior backend engineering concerns in a compact system: reliable
state changes, transactional consistency, idempotency, retries, accounting invariants,
reconciliation, auditability, and safe operational access.

## Scope boundaries

The system supports one fictional payment rail and ISO 4217 currency codes without foreign
exchange. It does not include refunds, disputes, chargebacks, real authentication, a user
interface, cloud deployment, or integration with a real payment provider.

## Components

| Component | Responsibility |
| --- | --- |
| API | Validate commands, enforce idempotency, and expose resource queries |
| Domain | Own entities, invariants, value objects, and state transitions |
| Application | Coordinate use cases and transaction boundaries |
| Infrastructure | Implement persistence, migrations, logging, and adapters |
| Worker | Claim transactional jobs and execute retryable workflows |
| Provider simulator | Return deterministic outcomes and emit signed webhooks |
| MCP server | Expose allowlisted read-only operational queries |

## Payment state machine

```text
PENDING -> PROCESSING -> SUCCEEDED
                      -> FAILED
```

Temporary provider failures retain the `PROCESSING` state while attempts remain. `SUCCEEDED`
and `FAILED` are terminal in the MVP. Settlement has an independent lifecycle so payment
processing and fund movement are not conflated.

| Current state | Command | Result |
| --- | --- | --- |
| `PENDING` | Start processing | `PROCESSING` |
| `PROCESSING` | Confirm success | `SUCCEEDED` |
| `PROCESSING` | Confirm permanent failure | `FAILED` |

All other transitions are rejected. Each accepted transition advances an optimistic-locking
version and requires a monotonic UTC timestamp. Domain methods receive identity and time as
inputs so tests remain deterministic and infrastructure concerns do not leak into the model.

Amounts are immutable value objects stored as positive integer minor units. The MVP
explicitly supports BRL, EUR, GBP, and USD; adding a currency is a deliberate domain change,
not an unchecked string accepted at an API boundary.

## Delivery and consistency model

Background work and provider events use at-least-once delivery. Correctness comes from
idempotency keys, unique constraints, explicit locks, and transactions rather than an
unrealistic exactly-once claim.

Payment creation reserves the idempotency key with PostgreSQL `INSERT ... ON CONFLICT` in
the same transaction that inserts the payment. A canonical request fingerprint distinguishes
safe replays from conflicting key reuse. Concurrent requests therefore coordinate at the
database uniqueness constraint instead of relying on process-local locks.

The first queue implementation uses PostgreSQL and `FOR UPDATE SKIP LOCKED`. A dedicated
message broker would improve throughput and workload isolation at larger scale, but would
add operational cost without improving the lessons demonstrated by this MVP.

## Security model

The provider signs webhook payloads with HMAC. Secrets are supplied at runtime and never
persisted in source control. MCP tools map to specific query services and use a database role
without write privileges. Arbitrary SQL and mutation tools are deliberately excluded.

## Data ownership

The application owns all tables. Audit records and ledger transactions are append-only from
the application's perspective. External provider payloads are minimized and treated as
untrusted input.

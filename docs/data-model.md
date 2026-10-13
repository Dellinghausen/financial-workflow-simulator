# Data Model

The first database milestone will introduce the following tables.

| Table | Purpose |
| --- | --- |
| `payments` | Payment aggregate, amount, currency, and current state |
| `idempotency_keys` | Request fingerprint and cached command result |
| `payment_attempts` | Provider attempts, errors, and retry schedule |
| `provider_events` | Received webhook metadata and deduplication key |
| `jobs` | Transactional background work queue |
| `ledger_accounts` | Small, explicit chart of accounts |
| `ledger_transactions` | Business event represented in the ledger |
| `ledger_entries` | Debit and credit lines stored in minor units |
| `reconciliation_runs` | Reconciliation execution and summary |
| `reconciliation_items` | Matches and discrepancies |
| `settlement_batches` | Settlement lifecycle and aggregate totals |
| `settlement_items` | Successful payments included in a batch |
| `audit_events` | Immutable business audit trail |

Public identifiers use UUIDs. Monetary amounts use positive integer minor units. Timestamps
are stored in UTC. Database constraints will enforce uniqueness, valid amounts, referential
integrity, and balanced ledger transactions.

## Implemented schema

The initial migration creates `payments` with named constraints for positive amounts,
supported currencies, valid states, non-negative versions, and monotonic timestamps. A
composite index on `(status, created_at)` supports predictable operational scans. Status and
currency use constrained strings instead of PostgreSQL enums so future additions do not
require non-transactional enum alterations.

The second migration creates `idempotency_keys`. Its primary key is supplied by the API
client, while a SHA-256 request fingerprint detects incompatible reuse. A unique payment ID
and a deferred foreign key allow the reservation and payment to be inserted atomically even
under concurrent requests. The implementation guarantees one payment identity per key; a
replay returns the payment's current representation.

The `jobs` table is the transactional queue. It stores typed JSON payloads, availability,
attempt count, lease ownership, bounded error details, and lifecycle timestamps. The claim
index covers `(status, available_at, created_at)`. A job is inserted alongside each new
payment, so a committed payment can never be missing its initial processing work.

The `provider_events` table durably records the fictional provider's event ID, target
payment, terminal outcome, payload hash, minimized JSON payload, and receive/process times.
Its primary key provides duplicate suppression. Event insertion and the locked payment
transition share one transaction, so neither can commit without the other.

The ledger migration seeds the `PROVIDER_RECEIVABLE` asset account and
`MERCHANT_PAYABLE` liability account. `ledger_transactions` owns a unique business
reference and currency; `ledger_entries` stores positive debit or credit amounts against a
known account. Deferred PostgreSQL constraint triggers require at least two entries and
equal debit and credit totals at commit time. A successful payment creates its transaction
and two entries atomically with the provider event.

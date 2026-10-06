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

Other tables remain intentionally deferred until their owning workflow is implemented. This
keeps migrations reviewable and prevents speculative columns from becoming accidental API.

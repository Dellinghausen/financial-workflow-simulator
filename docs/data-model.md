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

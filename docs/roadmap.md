# Roadmap

Each milestone should produce a small English-language commit with focused tests.

- [x] Repository foundation and engineering standards
- [x] Docker Compose and PostgreSQL health checks
- [x] Core payment domain and state-machine unit tests
- [x] Database schema and migrations
- [x] Payment creation API and idempotency
- [x] Transactional job queue and worker
- [x] Fictional provider adapter and controlled failures
- [ ] Signed webhook ingestion and duplicate handling
- [ ] Double-entry ledger
- [ ] Reconciliation workflow
- [ ] Settlement workflow
- [ ] Structured logs and audit trail
- [ ] Read-only MCP server
- [ ] Integration and end-to-end tests
- [ ] CI security checks and documentation polish
- [ ] Portfolio publication review

## Publication criteria

- A single documented command starts the complete environment.
- A clean database can be migrated without manual intervention.
- Tests cover state transitions, idempotency, duplicate events, and ledger invariants.
- CI runs formatting, linting, static typing, tests, and dependency security checks.
- No secret or employer-derived material is present.
- Webhooks are authenticated and protected against basic replay.
- MCP cannot mutate data or execute arbitrary SQL.
- Logs avoid secrets and unnecessary payloads.
- Architecture documentation explains important alternatives and trade-offs.
- The README provides a short, reproducible interview demonstration.

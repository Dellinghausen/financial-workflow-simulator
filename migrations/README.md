# Database migrations

Alembic owns all schema changes. Apply migrations with:

```bash
alembic upgrade head
```

Create revisions only after reviewing the generated SQL and supplying a safe downgrade.
Production migration strategy is outside the MVP; Docker Compose runs the one-shot `migrate`
service before the API starts.


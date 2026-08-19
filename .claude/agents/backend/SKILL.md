---
name: backend
description: Implement and review CraftControl Python backend changes. Use for `apps/backend/` and backend tests.
---

# Backend

Keep dependency direction HTTP → use cases → ports/adapters. Routes never access repositories directly; production dependencies are assembled only in `composition.py`. Use constructor injection and `if dependency is None`, never `dependency or Default()`. Add Protocols only at meaningful boundaries. Use injected fakes and real temporary SQLite databases in tests. Preserve XUID privacy, idempotent player history, event-driven refreshes, and coordinated backup/restore invariants. Run `bin/check-backend` and `bin/check`.

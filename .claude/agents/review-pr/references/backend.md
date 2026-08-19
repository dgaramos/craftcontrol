# Backend review

- Preserve HTTP → casos de uso → ports/adapters. Routes não alcançam
  repositórios/adapters; supervisores chamam portas de aplicação.
- Injete dependências por construtor e monte produção na composição. Use
  `Protocol` somente em fronteiras substituíveis reais; use `is None` para
  defaults injetáveis.
- Preserve XUID interno, perfis permanentes, idempotência de ingestão e a
  separação entre histórico de jogadores e retenção operacional.
- Migrações SQLite preservam dados. Não introduza lock/transação que prejudique
  runtime ou SSE.
- Mutações usam allowlist, capabilities e CSRF; não exponha console arbitrário,
  segredos ou identificadores de sessão.

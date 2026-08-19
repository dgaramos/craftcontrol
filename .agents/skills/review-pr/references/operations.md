# Operations review

- O painel continua útil sem exporter, Prometheus, Grafana ou telemetry pack;
  eventos derivados preservam evidência e não se tornam autoridade.
- Instalação do pack usa instalador compartilhado, dados persistentes, backup,
  associação atômica e decisão explícita de reinício.
- Backups suspendem saves apenas durante a cópia e retomam em `finally`.
  Restore é offline, confirmado, cria recuperação e nunca restaura `.env`.
- Não aceite deploy por Compose puro nem mudança que sobrescreva `.env`, SQLite
  ou mundo, ou que monte estado do checkout de desenvolvimento.

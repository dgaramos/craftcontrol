---
name: execute-issue
description: Executa uma issue do CraftControl do início ao merge, orquestrando start-issue, implement e ship-issue.
---

# execute-issue

Executa uma issue completa do início ao merge. Orquestra as três skills em sequência:

1. `/start-issue` — verificação, contexto, mapeamento de código, branch
2. `/implement` — implementação, testes, quality gate
3. `/ship-issue` — commit, PR, CI, CodeRabbit, Gitea

## Entrada

Número da issue (ex: `42`).

## Uso

```
/execute-issue 42
```

Equivale a rodar `/start-issue 42` → `/implement` → `/ship-issue` sem interrupção.

Use as skills individuais quando quiser controle por fase — por exemplo, `/start-issue` + pausa para explorar o código manualmente + `/implement` quando estiver pronto.

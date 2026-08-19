---
name: implement
description: Implementa a solução para uma issue do CraftControl seguindo os padrões do projeto.
---

# implement

Segunda fase da execução de uma issue: implementação, testes e quality gate.

Assume que `/start-issue` já foi executado — branch criada, contexto lido, arquivos mapeados.

## Protocolo

### 1. Identificar a camada afetada

Antes de qualquer implementação, determine o escopo da mudança:

| Se a issue tocar em... | Carregar skill |
|---|---|
| `apps/backend/` ou `tests/` | `/backend` |
| `apps/frontend/static/js/` ou `apps/frontend/tests/` | `/frontend` |
| Ambos | `/backend` e `/frontend` |

Carregue a skill correspondente e siga os padrões que ela define. O checklist dela substitui as seções genéricas abaixo.

### 2. Implementar

**Regras gerais — valem para qualquer camada:**

- [ ] Faça a menor mudança segura que resolve a issue
- [ ] Não adicione abstrações, refactors ou features além do escopo
- [ ] Prefira editar arquivos existentes; crie arquivo novo apenas quando a responsabilidade for genuinamente distinta e a modularização for justificada

### 4. Escrever ou atualizar testes

- [ ] Testes escritos junto da implementação — nunca depois
- [ ] Teste comportamento observável, não implementação interna
- [ ] Testes determinísticos — sem sleeps, sem dependência de ordem de execução

Padrões específicos de teste estão em `/backend` e `/frontend` — consulte a skill da camada afetada.

### 5. Quality gate

Não trate a ausência de Node/npm no host como bloqueio. `bin/check-frontend`
usa automaticamente `node:22-alpine` via Docker quando necessário; execute o
gate antes de reportar uma dependência ausente.

```bash
# Backend (sempre rodar se tocar Python):
PYTHONPATH=apps/backend:. pytest tests/ -q

# Frontend (rodar se tocar JS):
cd apps/frontend && npm test

# Gate completo:
bin/check
```

- [ ] Todos os testes passam
- [ ] Nenhum warning novo introduzido
- [ ] Gate completo passa sem erros

**Não avance para `/ship-issue` se o gate falhar.** Corrija primeiro.

### 6. Self-review

Antes de chamar `/ship-issue`, rodar `/review-pr` no diff local (incluindo arquivos novos):

```bash
git diff main
git diff --staged
git ls-files --others --exclude-standard
```

- [ ] Nenhum bloqueador identificado
- [ ] Findings importantes endereçados

## Saída

Implementação completa, testes passando, gate verde, self-review limpo. Pronto para `/ship-issue`.

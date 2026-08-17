---
name: start-issue
description: Prepara o contexto e cria a branch para executar uma issue do CraftControl.
---

# start-issue

Primeira fase da execução de uma issue: verificação, leitura de contexto, mapeamento de código e criação de branch.

## Entrada

Número da issue (ex: `42`).

## Protocolo

### 1. Verificar a issue

```bash
gh issue view <número>
```

Confirme que a issue tem todos os metadados obrigatórios:

- [ ] Project
- [ ] Milestone
- [ ] Label
- [ ] Assignee

Se faltar algum, adicione antes de continuar.

Se acceptance criteria forem vagos ou o escopo for ambíguo, pergunte ao autor — não interprete por conta própria.

### 2. Ler o contexto obrigatório

Leia nesta ordem:

- [ ] `CLAUDE.md` — constraints e regras do projeto
- [ ] `AGENTS.md` — arquitetura, padrões e decisões de design
- [ ] `CONTRIBUTING.md` — workflow de PR, convenções de commit e checklist
- [ ] `docs/architecture.md` — se a mudança tocar em serviços, ports ou adapters
- [ ] `CLAUDE.md` e `AGENTS.md` dentro de `tools/<tool>` — se a issue tocar em alguma tool

### 3. Mapear o código afetado

- [ ] Identifique os arquivos mencionados explicitamente na issue
- [ ] Se a issue não mencionar arquivos, use `grep`/`find` para localizar onde o comportamento descrito está implementado
- [ ] Leia cada arquivo afetado **completo** antes de decidir onde a mudança vai
- [ ] Entenda a responsabilidade de cada arquivo — não edite o que não leu

### 4. Criar branch a partir de main

```bash
git checkout main && git pull
git checkout -b <número>-<type>/<short-description>
```

Formato obrigatório: `{issue-number}-{type}/{short-description}`.  
`type`: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`.

- [ ] Branch criada a partir de main atualizado
- [ ] Nome segue o formato obrigatório

## Saída

Branch criada, contexto lido, arquivos afetados identificados e lidos. Pronto para `/implement`.

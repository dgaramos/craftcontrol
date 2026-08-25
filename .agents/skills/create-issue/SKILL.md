---
name: create-issue
description: Conduz um workshop rápido para criar uma issue bem formada no CraftControl com todos os metadados obrigatórios.
---

# create-issue

Cria uma issue no CraftControl com contexto, tarefa, critérios de aceite e todos os metadados obrigatórios. Antes de escrever, conduz um workshop rápido com duas perspectivas para garantir que a issue seja acionável.

## Entrada

Descrição livre do problema ou da melhoria desejada.

## Protocolo

### 1. Workshop — duas perspectivas antes de escrever

**PM Hat** — valor e escopo:

- Qual problema isso resolve? Quem é afetado?
- É um must-have, should-have ou nice-to-have?
- O que está dentro do escopo? O que está explicitamente fora?
- Como saberemos que está pronto?

**Dev Hat** — viabilidade e edge cases:

- Quais arquivos/módulos são afetados?
- Há dependências de outras issues? (`blocked-by: #n`)
- Quais cenários de falha precisam ser cobertos?
- Tem impacto em testes, migrações ou contratos de API?

Se a descrição inicial já responde essas perguntas, pule direto para o passo 2. Se não, pergunte antes de escrever.

### 2. Inferir tipo e escopo

| Campo | Opções |
|---|---|
| **Tipo** | `feat`, `fix`, `refactor`, `test`, `docs`, `ci`, `chore` |
| **Escopo** | `backend`, `frontend`, `runtime`, `cli`, `auth`, `players`, `telemetry`, `analytics`, `docker_ops`, `composition`, `tests`, `repo` |

### 3. Escolher metadados

Use `$manage-project` e `$manage-milestone` se precisar consultar o estado atual dos boards.

**Projeto:**

| Número | Nome | Quando usar |
|---|---|---|
| 1 | Tests Improvement | Cobertura, fakes, fixtures, quality gate |
| 2 | Backend Architecture Improvement | Serviços, ports, adapters, DI, repositórios |
| 3 | Frontend Architecture Improvement | Features JS, composition, estado, templates |
| 4 | Security & Account Management | Auth, sessões, RBAC, convites |
| 5 | Observability & Diagnostics | Telemetria, painel de diagnóstico |
| 6 | Analytics & Data | Analytics, export, rankings |
| 7 | Community Release | Hardening, release automation, onboarding |
| 8 | Documentation Improvement | README, guias, SECURITY.md, FAQ |

**Milestone:**

| Número | Nome | Escopo |
|---|---|---|
| 1 | Reliable Foundation | Confiabilidade, segurança, auth, invariantes de núcleo |
| 3 | Clean Architecture | Refactor modular, ports/adapters, use cases |
| 4 | Complete Panel | Features de UI, bilíngue, mobile-first |
| 2 | Community Ready | Instalação, diagnóstico, contribuição, release |

**Label:** pelo menos uma — `enhancement`, `bug`, `test`, `documentation`.

**Assignee:** `dgaramos` por padrão.

### 4. Redigir a issue

Estrutura obrigatória:

```markdown
## Contexto

<Por que isso importa? Qual problema existe? Cite arquivo:linha se relevante.>

## O que fazer

<Lista objetiva do que deve ser implementado. Só o quê — não o como.>

## Resultado esperado

<Como fica o código/comportamento após a mudança.>

## Acceptance criteria

- [ ] <Given [contexto] When [ação] Then [resultado esperado]>
- [ ] Quality gate passa (`bin/check`)
```

Critérios de aceite no formato Given/When/Then — verificáveis objetivamente. Não use "melhorar" ou "refatorar" sem critério concreto.

### 5. Criar pelo publisher do App

Para Cody DR, dispare `publish-cody-issue.yml`; para Claudio DR, dispare
`publish-claudio-issue.yml`. Nunca use `gh issue create` ou `gh project` para
publicar metadados atribuídos ao reviewer: esses comandos usam a identidade
local autenticada.

```bash
gh workflow run publish-cody-issue.yml --ref main \
  -f "title=type(scope): imperative description" \
  -f "body=$(cat <<'EOF'
## Contexto
...

## O que fazer
...

## Resultado esperado
...

## Acceptance criteria
- [ ] Given ... When ... Then ...
- [ ] Quality gate passa
EOF
)" \
  -f "labels=<label>" \
  -f "assignees=dgaramos" \
  -f "milestone_number=<número>" \
  -f "project_owner=dgaramos" \
  -f "project_number=<número>" \
  -f "project_status=<status>"
```

# Validar autenticação e disponibilidade do publisher antes de criar a issue:
gh auth status
gh workflow list
```

### 6. Confirmar

```bash
gh issue view <número> --json number,title,author,labels,milestone,projectItems,assignees
```

Verifique: autor do App esperado e todos os 4 metadados presentes (Project,
Milestone, Label, Assignee). Verifique também o status do item no Project.

## Regras

- Título: `type(scope): descrição` — sem ponto final, imperativo.
- Nunca criar issue sem milestone — ela ficará perdida no backlog.
- Nunca criar issue sem project — ela não aparecerá no board.
- Se a issue depende de outra, adicione `blocked-by: #número` no body.
- Acceptance criteria devem ser verificáveis de forma objetiva.

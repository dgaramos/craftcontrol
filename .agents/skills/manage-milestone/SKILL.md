---
name: manage-milestone
description: Gerencia milestones do CraftControl — lista progresso, atribui issues, consulta o que está aberto por milestone.
---

# manage-milestone

Gerencia milestones do repositório CraftControl via `gh api` e `gh issue`.

## Milestones disponíveis

| Número | Nome | Escopo |
|---|---|---|
| 1 | Reliable Foundation | Confiabilidade, segurança, auth, invariantes de núcleo |
| 2 | Community Ready | Instalação, diagnóstico, contribuição, release |
| 3 | Clean Architecture | Refactor modular, ports/adapters, use cases |
| 4 | Complete Panel | Features de UI, bilíngue, mobile-first |

## Comandos

### Listar milestones com progresso

```bash
gh api "repos/dgaramos/craftcontrol/milestones" \
  --jq '.[] | "\(.number)\t\(.title)\t\(.open_issues) open / \(.closed_issues) closed"'
```

### Listar issues abertas de um milestone

```bash
gh issue list --milestone "<nome-do-milestone>" --state open
```

Exemplo:
```bash
gh issue list --milestone "Clean Architecture" --state open
```

### Atribuir issue a um milestone

```bash
gh issue edit <número> --milestone "<nome-do-milestone>"
```

Exemplo:
```bash
gh issue edit 108 --milestone "Reliable Foundation"
```

### Remover milestone de uma issue

```bash
gh issue edit <número> --remove-milestone
```

### Ver progresso detalhado de um milestone

```bash
gh api "repos/dgaramos/craftcontrol/milestones/<número>" \
  --jq '{title: .title, open: .open_issues, closed: .closed_issues, due: .due_on}'
```

### Listar issues sem milestone (backlog solto)

```bash
gh issue list --state open --limit 1000 --json number,title,milestone \
  --jq '.[] | select(.milestone == null) | "\(.number)\t\(.title)"'
```

### Auditar issues sem project ou milestone

```bash
gh issue list --state open --json number,title,milestone,projectItems \
  --jq '.[] | select(.milestone == null or (.projectItems | length == 0)) | "\(.number)\t\(.title)"'
```

## Quando usar

- Ao criar uma issue — escolher o milestone correto antes de commitar
- Ao organizar o backlog — identificar issues soltas sem milestone
- Ao planejar uma sprint — ver o que está aberto por milestone
- Ao fazer review de roadmap — checar progresso de cada fase

## Critério de escolha de milestone

| A issue é sobre... | Milestone |
|---|---|
| Segurança, auth, confiabilidade, invariantes | Reliable Foundation |
| Refactor de arquitetura, DI, ports/adapters | Clean Architecture |
| UI, features de painel, bilinguismo, mobile | Complete Panel |
| Onboarding, instalação, diagnóstico, release | Community Ready |

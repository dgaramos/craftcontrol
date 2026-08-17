---
name: manage-project
description: Gerencia GitHub Project boards do CraftControl — lista projetos, adiciona issues, consulta itens e verifica se uma issue está atribuída a um board.
---

# manage-project

Gerencia os GitHub Project boards do CraftControl via `gh project`.

## Projetos disponíveis

| Número | Nome |
|---|---|
| 1 | Tests Improvement |
| 2 | Backend Architecture Improvement |
| 3 | Frontend Architecture Improvement |
| 4 | Security & Account Management |
| 5 | Observability & Diagnostics |
| 6 | Analytics & Data |
| 7 | Community Release |
| 8 | Documentation Improvement |

## Comandos

### Listar projetos e progresso

```bash
gh project list --owner dgaramos
```

### Adicionar issue a um project

```bash
gh project item-add <número-do-project> --owner dgaramos --url <url-da-issue>
```

Exemplo — adicionar issue #108 ao projeto 2 (Backend Architecture Improvement):
```bash
gh project item-add 2 --owner dgaramos --url https://github.com/dgaramos/craftcontrol/issues/108
```

### Listar itens de um project

```bash
gh project item-list <número-do-project> --owner dgaramos --limit 50
```

### Verificar se uma issue está em algum project

```bash
gh issue view <número> --json projectItems --jq '.projectItems[].project.title'
```

### Mover item entre colunas (status)

```bash
# Ver os campos disponíveis no project
gh project field-list <número-do-project> --owner dgaramos

# Atualizar status de um item (requer o ID do item)
gh project item-edit --project-id <project-id> --id <item-id> --field-id <field-id> --single-select-option-id <option-id>
```

### Remover issue de um project

```bash
# Listar itens para encontrar o item-id
gh project item-list <número-do-project> --owner dgaramos --format json | \
  jq '.items[] | select(.content.number == <número-da-issue>) | .id'

# Remover
gh project item-delete <número-do-project> --owner dgaramos --id <item-id>
```

## Fluxo padrão ao criar uma issue

1. Criar a issue com `gh issue create`
2. Adicionar ao project correto com `gh project item-add`
3. Confirmar com `gh issue view <número> --json projectItems`

## Quando usar

- Ao criar uma issue nova — garantir que está no board certo
- Ao auditar issues sem project (`gh issue list --json projectItems` e filtrar vazios)
- Ao mover trabalho entre boards por mudança de escopo

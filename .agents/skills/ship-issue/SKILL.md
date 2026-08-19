---
name: ship-issue
description: Commita, publica a branch e abre o PR de uma issue do CraftControl. Quando chamada por execute-issue ou por um pedido explícito de entrega até PR, faz push e cria o PR sem pedir confirmações intermediárias; CI, CodeRabbit e merge ficam com o usuário.
---

# ship-issue

Terceira fase da execução de uma issue: commit, push e PR aberto.

Assume que `$implement` já foi executado — implementação completa e gate verde.

**Escopo deste agente:** commit → push → PR aberto. Ponto final.
Não monitora CI, não aguarda CodeRabbit, não faz merge.

Quando esta skill for chamada por `$execute-issue`, ou quando o usuário pedir
explicitamente para levar a issue até o PR, o pedido já autoriza commit, push
e criação do PR. Não pergunte se deve publicar a branch nem se deve abrir o
PR. Caso seja chamada isoladamente sem essa autorização, confirme antes de
publicar qualquer alteração externa.

## Protocolo

### 1. Commit

Formato: `type(scope): descrição imperativa`

```bash
git add <arquivos específicos — nunca git add -A sem revisar>
git commit -m "$(cat <<'EOF'
type(scope): descrição

EOF
)"
```

- [ ] Nenhum arquivo sensível incluído (`.env`, `manager.db`, dados de mundo, segredos)
- [ ] Formato Conventional Commit verificado: `git show -s --format=%s HEAD`

### 2. Push

```bash
git push -u origin <branch>
git push gitea <branch>
```

- [ ] Branch no GitHub e no Gitea

### 3. Preparar descrição e metadados

Antes de criar o PR, releia a issue, seus critérios de aceite e o diff final.
Use esses fatos — não um texto genérico — para redigir a descrição. Leia também
o template `.github/pull_request_template.md` e preserve todas as seções.

- **What changes:** uma a três frases em inglês que expliquem o problema, a
  decisão tomada e o resultado observável. Inclua bullets concisos quando a
  mudança tiver mais de uma frente relevante.
- **Change type:** marque apenas o tipo aplicável.
- **Checklist:** marque somente itens comprovados pelo diff e pelo gate. Diga
  explicitamente se o README não precisou mudar e por quê, quando aplicável.
- **Additional context:** inclua `Closes #<número>`, risco de compatibilidade,
  migração, rollout ou limitações que importem ao revisor. Não preencha com
  placeholders, nem descreva o diff linha a linha.

Capture os metadados da issue e use os mesmos no PR. Labels, milestone,
assignees e Projects não são opcionais:

```bash
gh issue view <número> \
  --json title,assignees,labels,milestone,projectItems,body
```

Se a issue não tiver os quatro campos, corrija-a de acordo com a skill
`$manage-project`/`$manage-milestone` antes de abrir o PR; não crie um PR
incompleto. Se o token não tiver o escopo `project`, execute `gh auth refresh
-s project` e pare somente se essa autorização não puder ser concedida.

### 4. Abrir PR

**Título obrigatório:** `type(scope): descrição (#número-da-issue)`.

Passe cada label, assignee e Project recebido da issue. Use `--project` para
cada Project (não apenas para adicionar a issue ao board); o PR deve aparecer
no mesmo board. Exemplo para uma issue com dois labels:

```bash
gh pr create \
  --title "type(scope): descrição (#número)" \
  --body "$(cat <<'EOF'
## What changes

<Descrição específica, baseada na issue e no diff.>

## Change type

- [x] `fix` — bug fix

## Checklist

- [x] `bin/check` passes locally
- [x] Tests added or updated for changed behavior
- [ ] `README.md` updated when public behavior, API, or contract changed
- [x] No secrets, XUIDs, `.env`, or world data committed
- [x] Conventional Commit verified: `git show -s --format=%s HEAD`

## Additional context

Closes #<número>
EOF
)" \
  --assignee "<assignee da issue>" \
  --milestone "<milestone da issue>" \
  --label "<primeiro label da issue>" \
  --label "<segundo label da issue, se houver>" \
  --project "<Project da issue>"
```

Não use o exemplo literalmente: gere os valores reais a partir da issue e
revise o corpo antes de executar. Use `--base main` e `--head <branch>` para
eliminar prompts interativos.

### 5. Verificar e corrigir o PR

Valide o PR recém-criado, incluindo os Projects. O PR só está pronto quando os
quatro metadados refletem a issue:

```bash
gh pr view <url-do-pr> \
  --json url,body,assignees,labels,milestone,projectItems \
  | jq '{url, assignees: [.assignees[].login], labels: [.labels[].name],
         milestone: .milestone.title, projects: [.projectItems[].title]}'
```

Se algum item estiver ausente, corrija antes de reportar a entrega:

```bash
gh pr edit <url-do-pr> --add-assignee "<login>" --add-label "<label>" \
  --milestone "<milestone>" --add-project "<Project>"
```

Metadados obrigatórios:

- [ ] Todos os assignees da issue copiados
- [ ] Todos os labels da issue copiados
- [ ] Milestone da issue copiado
- [ ] Todos os Projects da issue copiados
- [ ] Corpo específico, sem placeholders, e com `Closes #<número>`

### 6. Reportar e parar

Após o PR aberto, reporte ao usuário:
- URL do PR
- Jobs de CI disparados (`gh pr checks`)
- Labels, milestone, assignees e Projects confirmados
- Resumo do comportamento entregue e dos testes, não só uma lista de arquivos
- Qualquer observação relevante sobre o diff

**Pare aqui.** CI, review comments e merge são responsabilidade do usuário.

---

## Modo revisão (acionado manualmente)

Quando o usuário trouxer findings de review (de qualquer fonte — CI, CodeRabbit, reviewer humano, etc.), retome o agente com os comentários e execute:

### R1. Triagem

Para cada finding recebido:
- Verificar se ainda é válido no código atual
- Classificar: **bloqueador** (corrigir agora) / **melhoria** (corrigir se simples) / **nitpick** (registrar, não bloquear)

### R2. Aplicar correções

Para cada item bloqueador ou melhoria simples:
- Corrigir no código
- `bin/check` local antes de commitar
- Commit separado por conjunto lógico de fixes

```bash
git add <arquivos>
git commit -m "fix(scope): endereçar findings de review"
git push origin <branch>
git push gitea <branch>
```

### R3. Reportar e parar novamente

Reporte ao usuário:
- O que foi corrigido e o que foi deixado (com justificativa)
- Se CI precisa rodar novamente

**Pare aqui.** Não faça merge sem confirmação explícita do usuário.

## Regras de ouro

- Nunca push direto para `main`.
- Nunca mergear sem confirmação explícita do usuário.
- Nunca commitar segredos — revisar `git diff --staged` antes de commitar.
- Nunca ficar em loop monitorando CI ou aguardando reviews — age quando acionado.

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

Co-authored-by: Cody DR <dgaramos+cody@gmail.com>
EOF
)"
```

- [ ] Nenhum arquivo sensível incluído (`.env`, `manager.db`, dados de mundo, segredos)
- [ ] Formato Conventional Commit verificado: `git show -s --format=%s HEAD`
- [ ] Todo commit criado pelo Cody DR inclui `Co-authored-by: Cody DR <dgaramos+cody@gmail.com>`

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

CraftControl currently supports exactly one personal Project per issue and PR.
Stop if the linked issue has zero or more than one Project; do not silently
drop metadata.

```bash
gh issue view <número> \
  --json title,assignees,labels,milestone,projectItems,body
```

Se a issue não tiver os quatro campos, não crie um PR incompleto. Corrija a
configuração ou use o publisher do App adequado; não faça `gh auth refresh` nem
use credenciais pessoais para completar Project, milestone, labels ou assignees.

### 4. Abrir PR

**Título obrigatório:** `type(scope): descrição (#número-da-issue)`.

Crie o PR com `gh pr create`, mas não passe metadata de reviewer nesse comando.
Depois, dispare `publish-cody-pr-metadata.yml` (ou o publisher Claudio DR
equivalente) com os valores herdados da issue; o workflow do App aplica e
verifica labels, assignees, milestone, Project e status. Nunca use `gh pr edit`
para esse fim, pois ele atribui a mutação à conta local.

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
  --base main --head <branch>
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

Se algum item estiver ausente, corrija pelo workflow do App antes de reportar a entrega:

```bash
gh workflow run publish-cody-pr-metadata.yml --ref main \
  -f "pr_number=<número>" -f "base_branch=main" \
  -f 'labels_json=["<label>"]' -f 'assignees_json=["<assignee>"]' \
  -f "milestone_number=<número>" -f "project_owner=dgaramos" \
  -f "project_number=<número>" -f "project_status=<status>"
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
git commit -m "$(cat <<'EOF'
fix(scope): endereçar findings de review

Co-authored-by: Cody DR <dgaramos+cody@gmail.com>
EOF
)"
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

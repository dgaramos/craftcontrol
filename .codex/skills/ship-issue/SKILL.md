---
name: ship-issue
description: Commita, abre PR e acompanha CI e CodeRabbit até o merge de uma issue do CraftControl.
---

# ship-issue

Terceira fase da execução de uma issue: commit, PR, CI, CodeRabbit e sync Gitea.

Assume que `/implement` já foi executado — implementação completa e gate verde.

## Protocolo

### 1. Commit

Formato: `type(scope): descrição imperativa`

```bash
git add <arquivos específicos — nunca git add -A sem revisar>
git commit -m "$(cat <<'EOF'
type(scope): descrição

Co-Authored-By: 
EOF
)"
```

- [ ] Nenhum arquivo sensível incluído (`.env`, `manager.db`, dados de mundo, segredos)
- [ ] Formato Conventional Commit verificado: `git show -s --format=%s HEAD`

### 2. Push

```bash
git push -u origin <branch>
```

Peça confirmação explícita ao usuário imediatamente antes de executar esse push.

- [ ] Branch no remote

### 3. Abrir PR

**Título obrigatório:** `type(scope): descrição (#número-da-issue)`

Leia `.github/pull_request_template.md` e preencha todas as seções.

```bash
gh pr create \
  --title "type(scope): descrição (#número)" \
  --body "$(cat <<'EOF'
## O que muda

<porquê da mudança>

## Tipo de mudança

- [ ] feat / fix / refactor / test / docs / ci / chore

## Checklist

- [x] `bin/check` passa localmente
- [x] Testes novos ou atualizados para o comportamento alterado
- [ ] `README.md` atualizado se comportamento público mudou
- [x] Nenhum segredo commitado
- [x] Conventional Commit verificado

## Contexto adicional

Closes #<número>
EOF
)" \
  --assignee dgaramos \
  --milestone "<milestone da issue>" \
  --label "<label da issue>"
```

Metadados obrigatórios:

- [ ] `--assignee dgaramos`
- [ ] `--milestone` preenchido com o milestone da issue
- [ ] `--label` preenchido com a label da issue

### 4. Aguardar CI

```bash
gh run watch --exit-status
```

- [ ] CI verde em todos os jobs
- [ ] Se falhar: `gh run view <id> --job <job-id> --log`, corrigir, novo commit, push

### 5. Endereçar CodeRabbit

Ao receber findings, usar `/review-pr` para triagem antes de aplicar:

- [ ] Ler todos os findings postados pelo CodeRabbit
- [ ] Para cada finding: verificar se ainda é válido no código atual
- [ ] Aplicar todos os bloqueadores e importantes — nenhum finding aberto
- [ ] Novo commit + push para cada correção

### 6. Merge e sync Gitea

Após aprovação e CI verde, peça confirmação explícita antes de mergear o PR pelo GitHub. Depois confirme o merge antes de sincronizar:

```bash
gh pr merge <número> --merge

# Confirmar que o merge foi concluído antes de continuar:
gh pr view <número> --json state,mergedAt --jq -e 'select(.state == "MERGED" and .mergedAt != null)' || { echo "merge não confirmado; interrompendo antes do sync Gitea" >&2; exit 1; }

git checkout main && git pull
# Só executar após nova confirmação explícita do usuário:
git push gitea main
```

- [ ] PR mergeado (state === MERGED confirmado)
- [ ] Gitea sincronizado

## Regras de ouro

- Nunca push direto para `main`.
- Nunca mergear com CI vermelho.
- Nunca mergear com findings abertos do CodeRabbit.
- Nunca commitar segredos — revisar `git diff --staged` antes de commitar.


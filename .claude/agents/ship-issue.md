---
name: ship-issue
description: Commita, abre PR e para — CI, CodeRabbit e merge ficam com o usuário.
---

# ship-issue

Terceira fase da execução de uma issue: commit, push e PR aberto.

Assume que `/implement` já foi executado — implementação completa e gate verde.

**Escopo deste agente:** commit → push → PR aberto. Ponto final.
Não monitora CI, não aguarda CodeRabbit, não faz merge.

## Protocolo

### 1. Commit

Formato: `type(scope): descrição imperativa`

```bash
git add <arquivos específicos — nunca git add -A sem revisar>
git commit -m "$(cat <<'EOF'
type(scope): descrição

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
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

### 4. Reportar e parar

Após o PR aberto, reporte ao usuário:
- URL do PR
- Jobs de CI disparados (`gh pr checks`)
- Qualquer observação relevante sobre o diff

**Pare aqui.** CI, CodeRabbit e merge são responsabilidade do usuário.

## Regras de ouro

- Nunca push direto para `main`.
- Nunca mergear — isso cabe ao usuário após CI e CodeRabbit.
- Nunca commitar segredos — revisar `git diff --staged` antes de commitar.

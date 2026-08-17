---
name: handle-pr-findings
description: Lê findings de review de um PR aberto, conversa sobre escopo, aplica um commit por finding, comenta nas threads e gera issues para o que ficou de fora.
---

# handle-pr-findings

Agente acionado manualmente após o PR estar aberto e com findings de review (de qualquer fonte: CodeRabbit, reviewer humano, CI, etc.).

## Protocolo

### 1. Ler contexto

```bash
gh pr view <número> --json title,body,headRefName,baseRefName
gh pr comments <número>
gh api repos/{owner}/{repo}/pulls/<número>/reviews
gh api repos/{owner}/{repo}/pulls/<número>/comments
```

Leia também a issue original para ter o escopo exato do que foi pedido.

### 2. Conversar sobre cada finding

Para cada finding recebido, **antes de agir**, apresente ao usuário:

- O que o finding pede
- Sua avaliação: está dentro do escopo desta issue?
- Recomendação: corrigir agora / gerar issue separada / rejeitar (com justificativa)

Aguarde confirmação do usuário para cada decisão antes de aplicar qualquer mudança.

### 3. Aplicar correções (um commit por finding)

Para cada finding aprovado pelo usuário:

```bash
# corrigir o código
bin/check  # gate local antes de commitar
git add <arquivos específicos>
git commit -m "$(cat <<'EOF'
fix(scope): descrição do que foi corrigido

EOF
)"
Peça confirmação explícita ao usuário antes de publicar a correção.

git push origin <branch>
git push gitea <branch>
```

Um finding = um commit separado. Nunca agrupe findings em um único commit.

### 4. Comentar nas threads

Após cada commit, responda na thread do finding no GitHub:

```bash
gh api repos/{owner}/{repo}/pulls/<número>/comments/<comment-id>/replies \
  -f body="Corrigido no commit <sha>: <descrição breve do que foi feito>."
```

Se o finding foi rejeitado ou adiado:

```bash
gh api repos/{owner}/{repo}/pulls/<número>/comments/<comment-id>/replies \
  -f body="<Explicação do motivo — fora de escopo, não se aplica, etc.>"
```

Resolva o comment se a plataforma permitir e fizer sentido.

### 5. Gerar issues para o que ficou de fora

Para cada finding que foi considerado válido mas fora do escopo desta issue, chame o agente `create-issue` com o contexto necessário para gerar uma issue bem formada.

### 6. Reportar e parar

Reporte ao usuário:
- O que foi corrigido (finding → commit SHA)
- O que foi rejeitado (com justificativa)
- Issues criadas para findings fora de escopo

**Pare aqui.** Não faça merge sem confirmação explícita do usuário.

## Regras de ouro

- Nunca agir sem conversar primeiro — cada finding passa pela aprovação do usuário.
- Um finding = um commit. Sem pacotes.
- Nunca mergear.
- Nunca commitar segredos.


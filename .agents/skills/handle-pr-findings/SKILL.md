---
name: handle-pr-findings
description: "Trata findings acionáveis de review em um PR aberto do CraftControl: corrige, testa, cria um commit por finding, faz push, atualiza o PR, responde e resolve threads sem confirmações intermediárias. Use quando o usuário enviar findings de CI, CodeRabbit ou reviewer e quiser o PR atualizado."
---

# handle-pr-findings

Agente acionado após o PR estar aberto e com findings de review (CodeRabbit,
revisor humano ou CI). O pedido para lidar com os findings autoriza as etapas
normais: corrigir, testar, commitar, publicar a branch, atualizar o PR,
responder e resolver as threads aplicáveis. Não peça confirmação entre essas
etapas.

## Protocolo

### 1. Ler contexto

```bash
gh pr view <número> --json title,body,headRefName,baseRefName
gh pr comments <número>
gh api repos/{owner}/{repo}/pulls/<número>/reviews
gh api repos/{owner}/{repo}/pulls/<número>/comments
```

Leia também a issue original para ter o escopo exato do que foi pedido.

### 2. Triar autonomamente

Para cada finding, avalie-o contra a issue, o diff atual e a arquitetura:

- **Corrigir agora:** é válido e cabe no escopo do PR.
- **Adiar:** é válido, mas altera escopo, produto, persistência, API ou exige
  decisão de projeto separada. Crie uma issue bem formada com `$create-issue`,
  incluindo vínculo ao PR/finding.
- **Rejeitar:** não se aplica ao código atual, já está coberto ou introduziria
  regressão. Registre uma justificativa objetiva na thread.

Não pergunte ao usuário para aprovar a triagem normal. Pare apenas se o
finding for ambíguo, potencialmente destrutivo, envolver uma decisão de produto
não inferível, ou se faltar autorização/credencial para atualizar o GitHub.

### 3. Aplicar correções (um commit por finding)

Para cada finding classificado como **corrigir agora**:

```bash
# corrigir o código
bin/check  # gate local antes de commitar
git add <arquivos específicos>
git commit -m "$(cat <<'EOF'
fix(scope): descrição do que foi corrigido

Co-authored-by: Cody DR <dgaramos+cody@gmail.com>
EOF
)"

git push origin <branch>
git push gitea <branch>
```

Um finding = um commit separado. Nunca agrupe findings em um único commit.

### 4. Atualizar o PR e as threads

Após cada commit, prepare a resposta e a resolução da thread. Quando a operação
do App do revisor estiver configurada e disponível, publique primeiro pelo
publisher correspondente e verifique autoria e thread. Para Cody DR, dispare
`publish-cody-review.yml`; para Claudio DR, `publish-claudio-review.yml`, com
`replies_json` e, quando aplicável, `resolve_thread_ids_json`.

```bash
gh workflow run publish-cody-review.yml \
  -f pr_number=<número> \
  -f reviewed_head_sha=<sha> \
  -f event=COMMENT \
  -f replies_json='[{"comment_id":<comment-id>,"body":"Fixed in commit <sha>: <brief description>."}]' \
  -f resolve_thread_ids_json='["<thread-node-id>"]'
```

Confirme que a resposta foi publicada pelo App esperado na thread indicada e
que a resolução, quando solicitada, foi aplicada. Uma falha de dispatch ou de
verificação do App é uma falha de publicação; não use fallback nesse caso.

Use o `gh api` com a conta pessoal autenticada somente se a operação do App
correspondente estiver explicitamente indisponível ou não configurada **antes**
do dispatch. Registre no resumo que a ação foi um fallback pessoal e qual login
a publicou. O fallback nunca deve se apresentar como Cody DR ou Claudio DR.

Se o finding foi rejeitado ou adiado, aplique a mesma política de publisher.
Use o exemplo abaixo apenas no fallback pessoal explicitamente permitido:

```bash
gh api repos/{owner}/{repo}/pulls/<número>/comments/<comment-id>/replies \
  -f body="<Explicação do motivo — fora de escopo, não se aplica, etc.>"
```

Resolva o comment se a plataforma permitir e fizer sentido.

Depois de publicar todos os commits, releia o PR e atualize seu corpo quando
os findings mudarem comportamento, testes, documentação, compatibilidade ou
riscos. Preserve o template e os metadados existentes; atualize `What changes`,
o tipo de mudança, o checklist e o contexto adicional para refletir o estado
real do PR. Não deixe o PR descrevendo a versão anterior do diff.

```bash
gh pr view <número> --json body,assignees,labels,milestone,projectItems
gh pr edit <número> --body-file <arquivo-com-corpo-atualizado>
```

Não altere assignees, labels, milestone ou Projects sem necessidade; valide que
eles continuam presentes após atualizar o PR.

### 5. Gerar issues para o que ficou de fora

Para cada finding que foi considerado válido mas fora do escopo desta issue, chame o agente `create-issue` com o contexto necessário para gerar uma issue bem formada.

### 6. Reportar e parar

Reporte ao usuário:
- O que foi corrigido (finding → commit SHA)
- O que foi rejeitado (com justificativa)
- Issues criadas para findings fora de escopo
- Threads respondidas/resolvidas e o que mudou no corpo do PR

**Pare aqui.** Não faça merge sem confirmação explícita do usuário.

## Regras de ouro

- Trate finding válido e dentro de escopo sem pedir confirmação intermediária.
- Um finding = um commit. Sem pacotes.
- Todo commit criado pelo Cody DR inclui `Co-authored-by: Cody DR <dgaramos+cody@gmail.com>`.
- Prefira sempre o App do revisor para replies e resoluções; `gh api` pessoal é
  somente fallback explícito quando o App não está disponível antes do dispatch.
- Nunca mergear.
- Nunca commitar segredos.

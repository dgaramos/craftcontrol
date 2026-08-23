---
name: review-pr
description: Cody DR revisa um PR ou referência explícita do CraftControl com contexto obrigatório, checklist por camada e findings verificáveis. Use com `/review-pr <número|link|branch|intervalo-de-commits>`.
---

# Cody DR

Produza revisões atribuídas a **Cody DR**. Procure defeitos reais,
regressões, riscos de segurança e violações das decisões do CraftControl. Não
reescreva o PR, não reporte preferência subjetiva de estilo e não modifique
código, exceto se o usuário também pedir para tratar os findings.

Exija uma referência explícita: número/link de PR, branch ou intervalo de
commits/diff. Para uma branch, calcule `git merge-base origin/main <branch>` e
compare o resultado com `<branch>`; se a base do PR for outra, use-a
explicitamente. Não rode automaticamente dentro de `/implement` ou
`/execute-issue`, nem infira que mudanças soltas do worktree devem ser
revisadas.

## 1. Formar contexto antes do diff

1. Leia `README.md`, todos os Markdown em `roadmap/`, `AGENTS.md` e
   `CONTRIBUTING.md`. Quando a mudança tocar arquitetura, persistência, runtime
   ou infraestrutura, leia também `docs/architecture.md`.
2. Carregue `.agent-review/craftcontrol/PROFILE.md` e todos os checklists de
   camada aplicáveis. Esse perfil local é a fonte de verdade para salvaguardas
   específicas do CraftControl.
3. Para um PR aberto, carregue título, descrição, base, head SHA, arquivos,
   checks, comentários e issue vinculada. Para diff local, compare com a base
   correta e cubra mudanças staged, rastreadas não staged e o conteúdo de cada
   arquivo não rastreado; não atribua ao PR mudanças alheias de um worktree sujo.
4. Leia os arquivos alterados no contexto de seus chamadores e testes. Um diff
   isolado não basta para provar o comportamento.

```bash
# PR aberto
gh pr view <pr> --json number,title,body,baseRefName,headRefName,headRefOid,files,comments,closingIssuesReferences,statusCheckRollup
gh pr diff <pr>
gh pr checks <pr>

# Diff local
git diff <base>...HEAD
git diff
git diff --staged
git ls-files --others --exclude-standard
# leia o conteúdo de cada arquivo não rastreado listado acima
```

## 2. Escolher os perfis aplicáveis

Ative todos os perfis que correspondam aos arquivos ou fronteiras tocadas:

| Mudança | Perfil |
| --- | --- |
| `apps/backend/` ou `tests/` | Backend |
| `apps/frontend/static/js/` ou `apps/frontend/tests/` | Frontend |
| contratos, rotas HTTP ou tipos gerados | Contratos |
| `packs/telemetry/` | Telemetry Pack |
| `bin/`, Compose, Dockerfile, deploy ou backup | Operações |
| `docs/`, `*.md`, README, CONTRIBUTING ou AGENTS | Docs e contribuição |

Carregue a referência correspondente antes de concluir a revisão: `references/backend.md`,
`references/frontend.md`, `references/contracts.md` ou `references/operations.md`.
Quando mais de um perfil se aplicar, carregue todos. A documentação simples usa
o checklist comum; mudanças de comportamento público também exigem a referência
da camada afetada.

## 3. Aplicar o checklist

### Sempre

- Verifique se o PR cumpre a issue, preserva o escopo e mantém compatibilidade.
- Confirme cobertura na gate correta, sem duplicar teste em gates distintas.
- Proteja `.env`, dados SQLite, mundos Bedrock e segredos.
- Exija documentação quando comportamento público, configuração, persistência,
  recuperação ou contrato mudar.

### Backend e contratos

- Use os checklists especializados de backend e contratos, quando aplicáveis.

### Frontend

- Use o checklist especializado de frontend.

### Telemetry e operações

- Use o checklist especializado de operações.

### Docs

- Valide comandos, caminhos, versões, contratos e links no estado atual.
- Atualize README inglês e tradução quando aplicável. Nunca publique conteúdo do
  roadmap.

## 4. Exigir evidência e concluir

Antes de redigir o resultado, carregue `references/reporting.md` e siga seu
contrato de apresentação. Abra finding apenas com arquivo/linha, fluxo afetado
e consequência plausível. Declare hipóteses não confirmadas e atribua confiança
de 0 a 100. Só inclua findings formais com confiança `>= 80`; abaixo disso,
registre como observação no resumo, nunca como comentário de revisão.

Antes de concluir, verifique os eixos de risco aplicáveis: persistência,
autorização/segurança, contratos, dados de jogadores e backup/recuperação.
Declare explicitamente no resumo quais foram avaliados e quais não se aplicam.

Inicie o relatório com a referência, base/head e arquivos/camadas revisados;
registre explicitamente `head revisado: <sha>` para viabilizar re-reviews.
Finalize com `approve`, `request changes`, `comment` ou `no findings`; informe
checks consultados/não executados, eixos de risco e estado de publicação.

## 5. Publicar somente com autorização

Para um PR aberto, publique apenas se o usuário pedir. Um pedido para “usar o
Cody” ou “usar o bot” também autoriza a publicação pelo Cody DR. Reconfirme PR,
head SHA e findings finais; publique apenas `blocking` ou `important` que
persistam no head atual e tenham confiança `>= 80`.

### Publicador Cody DR

O publicador é o GitHub App `cody-dr`, não a conta pessoal autenticada no `gh`.
Quando existir `.github/workflows/publish-cody-review.yml`, dispare essa
workflow com `gh workflow run` usando `pr_number`, `event`, `review_body`,
`inline_comments_json`, `replies_json` e `resolve_thread_ids_json`. Cada finding
em linha alterada entra como `{path, line, body}`; thread aberta equivalente recebe reply,
nunca uma thread duplicada. Aguarde a execução terminar e confirme que a review criada tem
autor `cody-dr` e o evento esperado.

Para responder uma thread existente, inclua `{comment_id, body}` em `replies_json`.
Confirme que a resposta
foi criada pelo `cody-dr` na thread indicada; não envie também uma nova review
ou comentário inline.

Quando um finding estiver comprovadamente corrigido, a workflow também aceita
`resolve_thread_ids_json`. Verifique o código e os testes no head atual, responda a
thread com o status verificado quando necessário e só então resolva-a pelo
`cody-dr`.

Não faça `gh auth switch`, `gh auth refresh`, `gh auth logout` nem tente
`gh pr review` diretamente para publicar em nome do Cody. A autenticação pessoal
do `gh` serve somente para despachar a workflow; ela não deve ser removida ou
trocada. Se a workflow não existir, não puder ser despachada ou falhar, entregue
comentários prontos e marque como não publicados. Nunca leia tokens, chaves ou
segredos do repositório.

## 6. Re-review de findings resolvidos

Quando receber o mesmo PR depois de correções, faça uma re-review; não repita a
revisão integral como se fosse um PR novo.

1. Carregue o head atual e todas as reviews, comentários gerais e threads,
   incluindo `isResolved`, `isOutdated`, autor, respostas e SHA/commit quando
   disponíveis. Para threads e respostas, use GraphQL; a listagem plana de
   comentários não preserva o estado da conversa.
2. Localize o último head revisado pelo mesmo reviewer no relatório publicado ou
   fornecido pelo usuário. Se não houver um SHA confiável, declare que o delta
   não é verificável e faça uma revisão completa do head atual.
3. Confirme que o último head é ancestral do atual com `git merge-base
   --is-ancestor <ultimo-head> <head-atual>`. Se houve rebase/force-push, diga
   que o histórico foi reescrito e revise `base...head` completo.
4. Para cada finding anterior, valide o código atual e classifique-o como
   `resolvido`, `corrigido mas thread aberta`, `não resolvido`, `substituído` ou
   `não verificável`. Uma resposta na thread ou comentário externo é contexto,
   não prova de correção; confronte-a com código, testes e head atual.
5. Revise somente os commits/diff entre `<ultimo-head>` e `<head-atual>` para
   novos findings. Não replique finding anterior resolvido; caso a correção crie
   regressão, reporte-a como novo finding com evidência própria.

Use este resumo antes de novos findings:

```text
Re-review: <PR/ref> — <ultimo-head> → <head-atual>
Findings anteriores: resolvidos: N; corrigidos/thread aberta: N; não resolvidos: N;
substituídos: N; não verificáveis: N.
Respostas verificadas: <threads/comentários externos consultados>.
Delta revisado: <arquivos e commits novos>.
```

Somente responda, resolva threads ou publique uma nova review se o usuário
autorizar expressamente essas escritas. Se autorizado, responda cada finding
com seu status verificado; não marque como resolvido o que apenas recebeu uma
resposta.

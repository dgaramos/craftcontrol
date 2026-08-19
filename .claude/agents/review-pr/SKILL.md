---
name: review-pr
description: Cláudio Reviewer revisa um PR ou referência explícita do CraftControl com contexto obrigatório, checklist por camada e findings verificáveis. Use com `/review-pr <número|link|branch|intervalo-de-commits>`.
---

# Cláudio Reviewer

Produza revisões atribuídas a **Cláudio Reviewer**. Procure defeitos reais,
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
2. Para um PR aberto, carregue título, descrição, base, head SHA, arquivos,
   checks, comentários e issue vinculada. Para diff local, compare com a base
   correta e cubra mudanças staged, rastreadas não staged e o conteúdo de cada
   arquivo não rastreado; não atribua ao PR mudanças alheias de um worktree sujo.
3. Leia os arquivos alterados no contexto de seus chamadores e testes. Um diff
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

Abra finding apenas com arquivo/linha, fluxo afetado e consequência plausível.
Declare hipóteses não confirmadas e atribua confiança de 0 a 100. Só inclua
findings formais com confiança `>= 80`; abaixo disso, registre como observação
no resumo, nunca como comentário de revisão. Classifique findings formais como
`blocking` (segurança, dados, contrato ou falha material) ou `important`
(regressão provável, cobertura relevante ausente ou incompatibilidade).

Antes de concluir, verifique os eixos de risco aplicáveis: persistência,
autorização/segurança, contratos, dados de jogadores e backup/recuperação.
Declare explicitamente no resumo quais foram avaliados e quais não se aplicam.

```text
[arquivo:linha] [blocking|important] Título curto — confiança: 85/100
Evidência: trecho e fluxo que provam o problema.
Impacto: consequência concreta.
Correção: mudança mínima sugerida.
```

Inicie o relatório com a referência, base/head e arquivos/camadas revisados.
Finalize com `approve`, `request changes`, `comment` ou `no findings`; informe
checks consultados/não executados, eixos de risco e estado de publicação.

## 5. Publicar somente com autorização

Para um PR aberto, publique apenas se o usuário pedir e o publicador do GitHub
App `claudio-reviewer-dr` estiver configurado. Reconfirme PR, head SHA e
findings finais; publique apenas `blocking` ou `important` que persistam no
head atual e tenham confiança `>= 80`. Comentário inline aponta linha alterada. Sem o publicador, entregue
comentários prontos e marque como não publicados. Nunca leia tokens, chaves ou
segredos do repositório.

---
name: execute-issue
description: Executa uma issue do CraftControl a partir do número ou link GitHub até o PR aberto. Use quando o usuário enviar uma issue e quiser que Codex crie a branch, implemente, valide, faça commit, push e abra o PR sem confirmações intermediárias.
---

# execute-issue

Executa uma issue completa até o PR aberto. Orquestra as três skills em sequência, sem pausas entre fases:

1. `$start-issue` — verificação, contexto, mapeamento de código, branch
   - Pare somente se os metadados obrigatórios não puderem ser inferidos da issue ou definidos com segurança.
   - Pare se os critérios de aceite forem realmente ambíguos ou conflitarem com o repositório.
2. `$implement` — implementação, testes, quality gate
3. `$ship-issue` — commit, push e PR aberto

## Entrada

Número da issue (ex.: `42`) ou URL da issue no GitHub.

A solicitação explícita desta skill, ou o envio de um link de issue com a
intenção de executá-la, autoriza as etapas normais deste fluxo: criar branch,
commitar, publicar a branch nos remotes configurados e abrir o PR. Não peça
uma confirmação separada para push ou PR.

## Uso

```text
$execute-issue 42
$execute-issue https://github.com/dgaramos/craftcontrol/issues/42
```

Resolva a URL para o número da issue antes de iniciar. Equivale a rodar
`$start-issue` → `$implement` → `$ship-issue` sequencialmente, com a
autorização já concedida para o envio e a abertura do PR.

Só interrompa o fluxo para um bloqueio real: árvore de trabalho incompatível
com a issue, credenciais/remotes indisponíveis, metadados impossíveis de
determinar, escopo ambíguo, conflito não resolvível ou quality gate falhando.
Nunca faça merge, deploy ou alterações fora do fluxo sem um pedido explícito.

Use as skills individuais quando quiser controle por fase — por exemplo, `$start-issue` + pausa para explorar o código manualmente + `$implement` quando estiver pronto.

# Contrato de apresentação de review

Use este formato para todos os resultados do Claudio DR. Ele deve funcionar igual
no terminal, em um comentário geral e em um comentário inline do GitHub.

## Regras de evidência

- Só um finding com confiança de pelo menos `80/100` é formal.
- Todo finding formal cita `arquivo:linha`, o fluxo afetado e evidência atual;
  não trate resposta em thread, intenção do autor ou ferramenta não executada
  como prova.
- Não invente blocos de ferramentas, métricas, prompts internos ou sugestões
  automáticas. Omita um finding que não seja acionável.
- `nit` é não bloqueante e só deve aparecer se a correção for concreta e trouxer
  valor claro. Ele nunca fundamenta `request changes`.

## Taxonomia

Escolha uma única categoria principal:

| Categoria | Quando usar |
| --- | --- |
| `Security & authorization` | Capabilities, CSRF, segredos, sessões, validação ou exposição indevida. |
| `Data integrity & recovery` | SQLite, migração, eventos, backups, restore ou histórico de jogadores. |
| `API & compatibility` | OpenAPI, rotas, contratos, tipos gerados ou compatibilidade pública. |
| `Behavior & reliability` | Fluxo funcional, idempotência, concorrência, erro ou regressão operacional. |
| `Architecture & maintainability` | Direção de dependências, fronteira de módulo ou manutenção que cause risco concreto. |
| `Tests & observability` | Cobertura de comportamento relevante, sinalização de falha ou diagnóstico. |
| `Documentation & contribution` | Comando, contrato, instrução de contribuição ou documentação pública incorreta. |
| `Performance & capacity` | Custo, retenção, cardinalidade ou degradação mensurável. |

| Classe | Selo | Uso |
| --- | --- | --- |
| `blocking` | `🔴 Critical` | Segurança, dados, contrato ou falha material provável; pede mudança. |
| `important` | `🟠 Major` | Regressão ou incompatibilidade provável; pede mudança. |
| `nit` | `🟡 Minor` | Melhoria não bloqueante; não pede mudança. |

Estime esforço sem precisão artificial: `⚡ Quick win` para alteração local,
`🔧 Focused change` para mudança coordenada pequena e `🧩 Follow-up` quando não
cabe como correção mínima deste PR.

## Finding inline ou geral

```md
<categoria> · <selo de severidade> · <esforço>

**<título imperativo e curto>**

<explicação objetiva do fluxo e da condição que produz o problema.>

**Evidência:** `<arquivo:linha>` — <fato verificável>; confiança: <N>/100.
**Impacto:** <consequência concreta para usuário, dados, segurança ou manutenção>.
**Correção sugerida:** <menor mudança que elimina o problema>.
```

Comentários inline usam uma linha alterada. Sem linha alterada, use o mesmo
formato no corpo da review e abra a primeira linha como `[general]`.

## Resumo de review

O resumo não repete cada finding. Use-o uma vez por review:

```md
## Review — <Claudio DR>

**Escopo:** <PR/ref>, `<base>` → `<head>`
**Head revisado:** `<sha>`
**Camadas:** <perfis revisados>
**Checks:** <consultados e resultado>; não executados: <motivo ou nenhum>
**Findings:** 🔴 Critical: N · 🟠 Major: N · 🟡 Minor: N
**Riscos avaliados:** <eixos aplicáveis>; não aplicáveis: <eixos>
**Veredito:** `<approve|request changes|comment|no findings>`
**Publicação:** <não solicitado|não publicado|publicado por Claudio DR>
```

Sem findings, mantenha o mesmo resumo com contagens zero e declare limitações
reais da análise; não crie categoria, esforço ou correção fictícios.

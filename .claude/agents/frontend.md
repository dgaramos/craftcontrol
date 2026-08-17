---
name: frontend
description: Implementa, refatora e testa código JavaScript do frontend do CraftControl. Usar quando a issue tocar em arquivos em apps/frontend/static/js/ ou apps/frontend/tests/.
---

# frontend

Skill de desenvolvimento frontend para o CraftControl. Cobre a arquitetura do módulo JS, padrões de composição, testes e convenções do projeto.

## Arquitetura

O frontend é vanilla JS ESM sem bundler. A estrutura relevante:

```
apps/frontend/static/js/
├── api.js                  ← cliente HTTP (fetch wrapper)
├── auth.js                 ← requireSession
├── events.js               ← connectEventStream (SSE)
├── composition.js          ← raiz da aplicação; monta todas as features
├── api-contract.d.ts       ← declarações de tipos da API
├── core/                   ← dom.js, state.js, navigation.js, invalidation.js, route.js
├── components/             ← feedback.js (toast), time.js (formatação de datas)
├── features/
│   ├── analytics/          ← index.js, activity.js, blocks.js, combat.js, exploration.js, rankings.js, trends.js
│   ├── players/            ← index.js, access.js, history.js, profile.js, telemetry.js, workspace.js
│   ├── auth/bootstrap.js
│   ├── settings/index.js
│   ├── world/index.js
│   ├── rules/index.js
│   └── server/index.js
└── i18n/                   ← index.js (createI18n), game-terms.js (createGameTerms), en.js, es.js, pt.js
```

## Padrões obrigatórios

### Composição por injeção de dependência

Features recebem todas as suas dependências via objeto no construtor — nunca importam globais diretamente:

```js
// ✅ Correto
export function createSettingsFeature({ state, content, t, api, $, escapeHtml, toast, render }) { ... }

// ❌ Errado — importar state, api, $ diretamente dentro da feature
import { state } from "../core/state.js";
```

`composition.js` é o único lugar onde as dependências reais são montadas e injetadas. Features não instanciam umas às outras.

### Lazy initialization em composition.js

Features são instanciadas sob demanda, não no boot:

```js
let settingsFeature = null;
function getSettingsFeature() {
  if (!settingsFeature) settingsFeature = createSettingsFeature({ ...deps });
  return settingsFeature;
}
```

### Seleção de DOM

Usar o helper `$` (wrapper de `document.querySelector`) injetado — nunca `document.querySelector` diretamente dentro de features:

```js
// ✅ Correto
const el = $("#status");

// ❌ Errado dentro de uma feature
const el = document.querySelector("#status");
```

### Internacionalização

Toda string visível ao usuário passa por `t(key)`. O app suporta `pt`, `en`, `es`. Nunca hardcode strings em português ou inglês no markup gerado por JS.

### Mobile-first

O CSS e o markup gerado devem funcionar em telas pequenas primeiro. Não assumir desktop.

## MUST DO

- Exportar features como `createXFeature({ deps })` — funções de fábrica, não classes
- Usar ESM (`import`/`export`) — o projeto é `"type": "module"`
- Injetar todas as dependências — nunca importar globais dentro de features
- Passar strings pelo `t()` injetado
- Escrever testes para todo comportamento novo ou alterado

## MUST NOT DO

- Usar `var` — sempre `const` ou `let`
- Usar callbacks para controle de fluxo assíncrono — usar Promises e `async`/`await` (callbacks de eventos como `addEventListener`, `onclick`, e callbacks síncronos como `map`, `filter`, `forEach` são permitidos)
- Importar `state`, `api`, `$` diretamente dentro de features
- Hardcodar strings visíveis ao usuário
- Criar classes onde funções de fábrica resolvem

## Testes

### Setup obrigatório

Testes que usam APIs específicas do Jest (`jest.fn()`, `jest.spyOn()`, `jest.mock()`) devem importar `jest` explicitamente de `@jest/globals`. Globais básicos como `describe`, `test` e `expect` são fornecidos automaticamente pelo Jest no modo ESM e não precisam de import:

```js
// Quando usar jest.fn() ou outras APIs Jest:
import { jest } from "@jest/globals";

// Quando usar apenas describe/test/expect:
// nenhum import necessário
```

### Helpers compartilhados

Usar os helpers de `./helpers.js` — nunca redefinir localmente:

```js
import { makeEl, makeSettingsDeps, makeAnalyticsDeps, FakeEventSource } from "./helpers.js";
```

| Helper | Quando usar |
|---|---|
| `makeEl(extra?)` | Stub de elemento DOM |
| `makeSettingsDeps(stateOverrides?)` | Deps para features de settings |
| `makeAnalyticsDeps(stateOverrides?)` | Deps para features de analytics |
| `FakeEventSource` | SSE em testes de eventos |

Se um helper não cobrir um caso novo, **estenda `helpers.js`** — não crie helpers locais no arquivo de teste.

### Save/restore de globals

Quando um teste modifica `global.window` ou `global.document`, salvar e restaurar ambos em `beforeEach`/`afterEach` para evitar vazamento de estado entre testes:

```js
let savedWindow;
let savedDocument;
beforeEach(() => {
  savedWindow = global.window;
  savedDocument = global.document;
});
afterEach(() => {
  global.window = savedWindow;
  global.document = savedDocument;
});
```

### Regras de teste

- [ ] Teste comportamento observável — não implementação interna
- [ ] Não use `@patch` onde injeção resolve — passe um fake como dep
- [ ] Testes determinísticos — sem `setTimeout` real, sem ordem de execução implícita
- [ ] Um `describe` por feature ou comportamento; `it` com descrição do comportamento esperado

### Rodar testes

```bash
cd apps/frontend && npm test
```

## Checklist de implementação

Antes de commitar qualquer mudança de frontend:

- [ ] Feature recebe deps injetadas, não importa globais
- [ ] Strings visíveis passam por `t()`
- [ ] Helpers de teste em `helpers.js`, não duplicados no arquivo de teste
- [ ] `beforeEach`/`afterEach` com save/restore se o teste modificar globals
- [ ] `npm test` passa sem warnings novos

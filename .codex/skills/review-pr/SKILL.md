---
name: review-pr
description: Revisa um PR do CraftControl antes de abrir ou após receber findings — detecta a camada afetada e aplica o checklist correto (backend, frontend ou docs).
---

# review-pr

Skill de code review para o CraftControl. Usada em dois momentos:

1. **Self-review** — antes de abrir o PR, como último passo do `/implement`
2. **Triagem de findings** — ao receber comentários do CodeRabbit ou de outro revisor

## Entrada

Número do PR (ex: `107`) ou diff local (`git diff main`).

## Protocolo

### 1. Carregar o diff

```bash
# PR aberto:
gh pr view <número> --json title,body,files
gh pr diff <número>

# Self-review antes de abrir (inclui arquivos novos não rastreados):
git diff main
git diff --staged
git ls-files --others --exclude-standard
```

### 2. Detectar camada e aplicar checklist

Identifique os arquivos afetados e aplique o perfil correspondente. Um PR pode acionar mais de um perfil.

| Arquivos afetados | Perfil |
|---|---|
| `apps/backend/` ou `tests/` | → **Backend** |
| `apps/frontend/static/js/` ou `apps/frontend/tests/` | → **Frontend** |
| `docs/`, `*.md`, `CONTRIBUTING`, `README`, `AGENTS.md` | → **Docs** |

---

## Perfil: Backend

### Design e arquitetura

- [ ] Direção das dependências: HTTP → services → ports/adapters — nenhuma camada atravessada
- [ ] Routes Flask não acessam repositórios diretamente
- [ ] Dependência nova entra pelo construtor
- [ ] Guard com `is None`: `if dep is None: dep = Default()` — nunca `dep or Default()`
- [ ] Protocol novo em `ports.py` apenas se houver fronteira real — não uma interface por classe
- [ ] `composition.py` é o único lugar onde a dependência real é instanciada

### Lógica e edge cases

- [ ] Inputs nulos, vazios ou inválidos tratados explicitamente
- [ ] Condições de borda cobertas
- [ ] Nenhuma operação falha silenciosamente

**Padrões problemáticos:**

| Sinal | Problema | Correção |
|---|---|---|
| `dep or Default()` | Falsy mock cai no default | `if dep is None: dep = Default()` |
| `@patch` onde injeção resolve | Teste acoplado à implementação | Usar fake injetado |
| `repository.x()` em route handler | Cross-layer | Passar por service |
| `docker.from_env()` dentro de método | Dep não injetada | Injetar via construtor |

### Testes (backend)

- [ ] Comportamento novo coberto por teste
- [ ] Fakes injetados (`FakeBedrock`, `FakeDocker`) — não `@patch` onde injeção existe
- [ ] Banco de dados: `tmp_path` com SQLite real — não mock de repositório
- [ ] Falsy dep coberta quando relevante: `fake.__bool__ = lambda self: False`
- [ ] Testes determinísticos — sem `time.sleep`, sem ordem implícita
- [ ] Novo fake reutilizável adicionado em `tests/fakes.py`

### Segurança (backend)

- [ ] Nenhum segredo ou credencial no código ou nos testes
- [ ] Input de usuário validado antes de usar
- [ ] Operações privilegiadas verificam role/capability

---

## Perfil: Frontend

### Design e composição

- [ ] Feature recebe todas as deps injetadas — não importa `state`, `api`, `$` diretamente
- [ ] `composition.js` é o único lugar onde deps reais são montadas
- [ ] Arquivo novo criado só quando a responsabilidade é genuinamente distinta
- [ ] Strings visíveis passam por `t()` — nenhum hardcode em PT/EN/ES

### Lógica e edge cases

- [ ] Estados vazios e erros de API tratados
- [ ] Nenhum acesso a DOM sem o helper `$` injetado dentro de features

**Padrões problemáticos:**

| Sinal | Problema | Correção |
|---|---|---|
| `import { state }` dentro de feature | Global direto | Injetar como dep |
| `document.querySelector` dentro de feature | DOM global | Usar `$` injetado |
| Helper de teste redefinido localmente | Duplicação | Importar de `helpers.js` |
| `global.window` sem save/restore | Vazamento de estado | `beforeEach`/`afterEach` |

### Testes (frontend)

- [ ] Imports de `@jest/globals` — sem globals implícitos
- [ ] Helpers de `./helpers.js` — nenhum `makeEl`, `makeDeps` local duplicado
- [ ] `beforeEach`/`afterEach` com save/restore se o teste modifica `global.window` ou `global.document`
- [ ] `FakeEventSource` de `helpers.js` para testes de SSE
- [ ] Testes determinísticos — sem `setTimeout` real

### Segurança (frontend)

- [ ] Nenhum token ou credencial exposto no JS
- [ ] Output do usuário escapado via `escapeHtml` injetado antes de inserir no DOM

---

## Perfil: Docs

### Estrutura e completude

- [ ] O documento tem uma pergunta ou objetivo claro — o leitor sabe o que vai encontrar
- [ ] Seções seguem uma ordem lógica (contexto → instrução → resultado)
- [ ] Nenhuma seção vazia ou com placeholder não preenchido

### Clareza e precisão

- [ ] Instruções são imperativas e diretas — sem "você pode", "talvez", "geralmente"
- [ ] Exemplos de código são completos e executáveis como estão
- [ ] Terminologia consistente com o resto do projeto (`ManagerService`, não `Manager`; `compose_manager`, não `build_manager`)
- [ ] Comandos referenciados existem no código atual — verificar se não foram renomeados

### Links e referências

- [ ] Links internos apontam para arquivos que existem
- [ ] Referências a arquivos específicos usam o caminho correto (`apps/backend/minecraft_manager/composition.py`, não `minecraft_manager/composition.py`)

### Cobertura

- [ ] Mudança de comportamento público está documentada (se o PR altera API, CLI ou configuração)
- [ ] `README.md` atualizado se o fluxo de instalação ou uso mudou
- [ ] `CONTRIBUTING.md` atualizado se o workflow de contribuição mudou

---

## Relatório

Priorize findings em três níveis:

**Bloqueador** — corrigir antes de mergear:
- Violação de DI (`or` em vez de `is None`, global importado em feature)
- Cross-layer (route → repository, feature → DOM global)
- Segredo exposto
- Teste não determinístico ou que mocka o banco

**Importante** — corrigir, mas não bloqueia CI:
- Comportamento sem cobertura de teste
- Helper de teste duplicado
- Doc com comando inexistente ou caminho errado

**Sugestão** — melhoria incremental:
- Nome de variável pouco claro
- Edge case improvável não coberto
- Doc com frase ambígua

Formato de cada finding:

```
[arquivo:linha] Categoria: descrição curta
Atual: <o que está errado>
Sugerido: <como corrigir>
```

## Veredicto

| Veredicto | Quando usar |
|---|---|
| **Aprovado** | Nenhum bloqueador; sugestões são opcionais |
| **Solicitar mudanças** | Pelo menos um bloqueador ou importante |
| **Comentário** | Dúvida que precisa de resposta antes de decidir |


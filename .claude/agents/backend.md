---
name: backend
description: Implementa, refatora e testa código Python do backend do CraftControl. Usar quando a issue tocar em arquivos em apps/backend/ ou tests/.
---

# backend

Agente de desenvolvimento backend para o CraftControl. Cobre arquitetura em camadas, injeção de dependência, Protocols, testes e convenções do projeto.

## Arquitetura

O backend é um monólito modular em Flask com runtime orientado a eventos. Estrutura relevante:

```
apps/backend/minecraft_manager/
├── composition.py       ← único composition root; monta o grafo de objetos real
├── ports.py             ← Protocols que definem as fronteiras substituíveis
├── services.py          ← ManagerService (orquestrador principal)
├── runtime.py           ← EventRuntime (loop de eventos em thread separada)
├── docker_ops.py        ← DockerOperations (adapter de container)
├── bedrock.py           ← BedrockClient (adapter de console Bedrock)
├── events.py            ← EventBroker (pub/sub interno)
├── repository.py        ← StateRepository (SQLite)
├── players.py           ← PlayerService + SQLitePlayerRepository
├── telemetry_service.py ← TelemetryService
└── http/                ← rotas Flask; não conhece repositórios diretamente

tests/
├── conftest.py          ← fixtures compartilhadas (app Flask, repositório real)
├── fakes.py             ← FakeBedrock, FakeDocker, FakeConsole, FakeRuntime
└── test_*.py            ← um arquivo por módulo
```

## Padrões obrigatórios

### Injeção de dependência via construtor

Dependências entram pelo `__init__` — nunca instanciadas dentro do método:

```python
# ✅ Correto
class DockerOperations:
    def __init__(self, container: str, project: Path, executor: DockerExecutor | None = None) -> None:
        self._executor: DockerExecutor = executor if executor is not None else subprocess.run

# ❌ Errado — instancia dentro do método
class DockerOperations:
    def run(self, cmd):
        return subprocess.run(cmd, ...)
```

### Guard com `is None` — nunca `or`

```python
# ✅ Correto
if bedrock is None:
    bedrock = BedrockClient(...)

# ❌ Errado — falsy mock cai no default silenciosamente
bedrock = bedrock or BedrockClient(...)
```

### Protocols em vez de herança ou ABC

Fronteiras substituíveis são definidas com `typing.Protocol` em `ports.py`. Não crie uma interface por classe — só onde há uma fronteira real:

```python
class DockerExecutor(Protocol):
    def __call__(self, cmd: list[str], *, capture_output: bool, text: bool, timeout: int, check: bool) -> subprocess.CompletedProcess[str]: ...
```

### composition.py é o único composition root

Dependências reais são construídas **apenas** em `composition.py`. Runtime code não instancia adapters diretamente:

```python
# Em composition.py — correto
if docker is None:
    docker = DockerOperations(settings.container, settings.project)

# Em services.py ou runtime.py — errado
docker = DockerOperations(container, project)
```

### Direção das dependências

```
HTTP (Flask routes) → ManagerService → ports/adapters
```

Nunca atravesse camadas: routes não acessam repositórios diretamente; services não conhecem Flask.

## MUST DO

- `from __future__ import annotations` no topo de todo arquivo Python
- `typing.Protocol` para interfaces de fronteira — não ABC, não herança
- Guards `is None` para dependências opcionais
- Injeção via construtor em todos os adapters e services
- Testes com fakes injetados — não com `@patch` onde injeção resolve

## MUST NOT DO

- Instanciar dependências reais dentro de métodos de negócio
- Usar `dep or Default()` para dependências injetadas
- Importar `docker`, `subprocess`, `threading` diretamente dentro de services
- Deixar routes Flask acessar repositórios
- Criar uma Protocol por classe sem fronteira real justificada

## Testes

### Helpers disponíveis

```python
# tests/fakes.py — fakes reutilizáveis
from tests.fakes import FakeBedrock, FakeDocker, FakeConsole, FakeRuntime

# tests/conftest.py — fixtures pytest
# tmp_path       → Path temporário por teste (pytest built-in)
# app            → Flask app com repositório real em SQLite temporário
```

### Padrão de teste com injeção

```python
def _ops(result=None):
    executor = MagicMock(return_value=result or _completed())
    return DockerOperations("bedrock", Path("/srv"), executor=executor), executor

def test_start_calls_compose_up() -> None:
    ops, executor = _ops()
    ops.execute("start")
    executor.assert_called_once_with(["docker", "compose", ...], ...)
```

### Regras de teste

- [ ] Use fakes injetados (`FakeBedrock`, `FakeDocker`) — não `@patch` onde injeção existe
- [ ] Não mocke o banco de dados — use `tmp_path` com SQLite real
- [ ] Teste comportamento observável, não implementação interna
- [ ] Testes determinísticos — sem `time.sleep`, sem dependência de ordem
- [ ] Cubra o caso de dep falsy injetada quando relevante:

```python
def test_preserves_falsy_injected_dep() -> None:
    fake = MagicMock()
    fake.__bool__ = lambda self: False
    result = compose_manager(settings, runtime=fake, ...)
    assert result.runtime is fake
```

### Rodar testes

```bash
PYTHONPATH=apps/backend:. pytest tests/ -q
# ou o gate completo:
bin/check-backend
```

## Checklist de implementação

Antes de commitar qualquer mudança de backend:

- [ ] Dependência nova entra pelo construtor com guard `is None`
- [ ] Interface nova usa `typing.Protocol` em `ports.py` se for fronteira real
- [ ] `composition.py` instancia a dependência real e injeta
- [ ] Fake correspondente criado ou atualizado em `tests/fakes.py` se necessário
- [ ] Teste cobre o comportamento com fake injetado
- [ ] `bin/check-backend` passa sem erros novos

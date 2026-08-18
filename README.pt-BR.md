<div align="center">
  <p><a href="README.md">Read in English</a></p>
  <img src="apps/frontend/static/craftcontrol-mark.svg" width="112" alt="Logo do CraftControl">
  <h1>CraftControl</h1>
  <p><strong>Um centro de controle mobile-first para servidores Minecraft Bedrock.</strong></p>
  <p>Administre mundos, jogadores, regras, acesso, backups e estatísticas estruturadas sem viver no console do servidor.</p>
  <p>
    <a href="https://github.com/dgaramos/craftcontrol/actions/workflows/quality.yml"><img alt="Portões de qualidade" src="https://github.com/dgaramos/craftcontrol/actions/workflows/quality.yml/badge.svg?branch=main"></a>
    <a href="https://codecov.io/gh/dgaramos/craftcontrol"><img alt="Cobertura" src="https://codecov.io/gh/dgaramos/craftcontrol/graph/badge.svg?branch=main"></a>
    <a href="LICENSE"><img alt="Licença: Apache-2.0" src="https://img.shields.io/badge/License-Apache--2.0-D22128?logo=apache"></a>
    <a href="https://www.python.org/"><img alt="Python 3.12" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white"></a>
    <a href="https://flask.palletsprojects.com/"><img alt="Flask 3" src="https://img.shields.io/badge/Flask-3-101010?logo=flask&logoColor=white"></a>
    <a href="https://www.sqlite.org/"><img alt="SQLite" src="https://img.shields.io/badge/SQLite-durable-003B57?logo=sqlite&logoColor=white"></a>
    <a href="https://www.docker.com/"><img alt="Docker Compose" src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white"></a>
  </p>
  <p>
    <a href="https://nginx.org/"><img alt="Nginx" src="https://img.shields.io/badge/Nginx-static_proxy-2496ED?logo=nginx&logoColor=white"></a>
    <a href="https://developer.mozilla.org/docs/Web/JavaScript"><img alt="Módulos ES JavaScript" src="https://img.shields.io/badge/JavaScript-ES_modules-F7DF1E?logo=javascript&logoColor=101010"></a>
    <a href="packages/contracts/openapi.json"><img alt="OpenAPI 3.1" src="https://img.shields.io/badge/OpenAPI-3.1-6BA539?logo=openapiinitiative&logoColor=white"></a>
    <a href="#contratos-e-documentacao-da-api"><img alt="Swagger UI" src="https://img.shields.io/badge/Swagger-UI-85EA2D?logo=swagger&logoColor=173647"></a>
    <img alt="Idiomas: PT, EN, ES" src="https://img.shields.io/badge/UI-PT%20%7C%20EN%20%7C%20ES-B87333">
  </p>
</div>

> [!IMPORTANT]
> O CraftControl destina-se a redes privadas confiáveis. A autenticação local e a proteção CSRF estão ativas, mas a terminação TLS e o acesso restrito ao Docker continuam sendo requisitos de implantação. Não exponha a porta `8082` diretamente à Internet.

## O que o CraftControl oferece

- Controles específicos para propriedades do servidor, gamerules, horário, clima, permissões, packs e ciclo de vida.
- Perfis permanentes com aliases, sessões, tempo de jogo, mortes, permissões e telemetria individual.
- Análises globais de atividade, mortes, rankings, blocos, combate, exploração e períodos de 7/30 dias.
- Um Behavior Pack complementar para abates, blocos, dano, distância, dimensões e mortes estruturadas autoritativos.
- Backups coordenados do mundo e SQLite com verificação, retenção, restauração offline e cópias de recuperação.
- Contas de proprietário, operador e visualizador vinculadas a jogadores, com sessões opacas e tokens CSRF vinculados à sessão.
- Interface responsiva em português, inglês e espanhol, com ícones pixel-art originais do CraftControl.

O gerenciador continua útil sem o Telemetry Pack, Prometheus, Grafana, Loki ou qualquer serviço externo de observabilidade.

## Interface

As seis áreas principais são orientadas por tarefa:

| Área | Responsabilidade |
| --- | --- |
| Início | Saúde do servidor, jogadores online, atualização e atalhos |
| Mundo | Identidade, geração, horário, clima e ciclos |
| Jogadores | Perfis, sessões, acesso, permissões e telemetria individual |
| Dados | Atividade, mortes, rankings, blocos, combate, exploração e períodos |
| Regras | Jogabilidade, interface, mobs, drops, comandos, fogo, TNT e regeneração |
| Servidor | Telemetry Pack, rede, desempenho, backups e ciclo de vida do contêiner |

A navegação é codificada na URL; recarregar o navegador preserva a área ativa. Mudanças persistentes de configuração entram em uma gaveta de revisão; gamerules marcadas com raio são aplicadas imediatamente.

## Arquitetura

O CraftControl é um monorepo com dois serviços implantáveis de modo independente, não um conjunto de microsserviços. O backend continua sendo um monólito modular.

```text
Celular, tablet ou desktop
          |
          | HTTP :8082 — LAN confiável / proxy TLS externo
          v
┌────────────────────────────────────────────┐
│ Frontend · Nginx · estático e somente leitura│
│ UI do navegador · /api mesma origem + proxy SSE │
└────────────────────┬───────────────────────┘
                     │ rede Compose privada
┌────────────────────▼───────────────────────┐
│ Backend · monólito modular Flask           │
│ HTTP → casos de uso → portas/adapters → SQLite │
└───────────────┬────────────────────────────┘
                │ Docker, arquivos, console, logs
                v
      Servidor dedicado Minecraft Bedrock
                │
                └─ CraftControl Telemetry Pack opcional
```

O frontend é dono da origem pública. O Nginx serve ativos estáticos e encaminha `/api/*`, inclusive Server-Sent Events sem buffer, para o backend privado. O frontend não possui montagens persistentes ou privilegiadas. Somente o backend acessa SQLite, arquivos Bedrock, backups coordenados ou operações Docker.

O backend roda intencionalmente com um worker Gunicorn e várias threads. Seu broker de eventos, supervisores, lock de atualização e entrega SSE são locais ao processo; vários workers duplicariam essas responsabilidades.

### Propriedade do repositório

```text
apps/
├── frontend/                 Imagem Nginx, HTML, CSS e módulos ES nativos
└── backend/                  Imagem Flask, composition root e aplicação Python
packages/contracts/           Contrato OpenAPI 3.1 canônico e tipos gerados
packs/telemetry/              Behavior Pack embutido e ativos de ciclo de vida
bin/                          Comandos de qualidade, implantação, cutover, backup e recuperação
docs/                         Guias de arquitetura, segurança, telemetria e operações
minecraft_manager/            Overlay temporário de compatibilidade do backend
app.py, wsgi.py               Overlays temporários dos pontos de entrada raiz
docker-compose.split.yml      Topologia de produção dividida ativa
docker-compose.yml            Topologia combinada de compatibilidade/recuperação
versions.env                  Par frontend/backend testado
```

Os links Python da raiz e a imagem combinada são overlays de compatibilidade. Eles preservam ferramentas existentes e rollback de emergência enquanto a migração continua; código novo pertence a `apps/`.

### Módulos do frontend

O frontend usa módulos ES nativos do navegador, sem bundler ou framework em tempo de build.

```text
apps/frontend/static/
├── app.js                    Bootstrap mínimo
└── js/
    ├── composition.js        Montagem de dependências e início da aplicação
    ├── core/                 Estado, DOM, rotas, navegação e invalidação
    ├── components/           Feedback compartilhado e apresentação de tempo
    ├── features/             Auth, configurações, mundo, regras, servidor, jogadores, análises
    └── i18n/                 Catálogos PT, EN, ES e terminologia localizada do jogo
```

`app.js` inicia o composition root. As features possuem markup, bindings e estado local; o core não importa features. Dependências compartilhadas são explícitas, e o portão de interação executa navegação, autenticação, sessões, telemetria individual, análises, responsividade, invalidação SSE e localização.

### Camadas do backend

```text
apps/backend/minecraft_manager/
├── composition.py            Injeção manual de dependências de produção
├── http/                     Mapeamento HTTP por domínio
├── players/                  Casos de uso de jogadores
├── auth/                     Contas, sessões, papéis, CSRF e auditoria
├── operations/               Fluxos de backup e restauração
├── services.py               Fachada de orquestração de compatibilidade
├── repository.py             Fachada SQLite de compatibilidade
├── runtime.py                Supervisores de logs, Docker e reconciliação
└── ports.py                  Contratos estruturais de fronteiras externas
```

Rotas traduzem HTTP; casos de uso coordenam comportamento; repositórios possuem a persistência. Adapters isolam Docker, console Bedrock, arquivos e instalação do Telemetry Pack. Dependências são montadas manualmente; não há service locator nem framework de DI.

Veja [Arquitetura](docs/architecture.md) para regras de dependência, consistência de eventos, não-objetivos deliberados e layout-alvo incremental.

### Contratos e documentação da API

`packages/contracts/openapi.json` é o contrato de negócio OpenAPI 3.1 canônico. Declarações geradas do frontend ficam em `apps/frontend/static/js/api-contract.d.ts`; o portão de qualidade rejeita declarações desatualizadas.

Instalações autenticadas expõem:

- `/api/openapi.json` — contrato legível por máquina;
- `/api/docs` — Swagger UI usando a sessão atual;
- `/api/events` — Server-Sent Events persistidos e ao vivo.

O Swagger anexa o token CSRF vinculado à sessão a requisições inseguras de “Try it out” e nunca ignora capabilities de papel. Não há endpoint arbitrário de shell ou console.

## Estado e telemetria orientados por eventos

O CraftControl acompanha logs do Bedrock e eventos de ciclo de vida do Docker, confirma evidências duráveis no SQLite, publica mudanças por SSE, faz atualizações direcionadas e executa uma reconciliação de segurança completa a cada 15 minutos por padrão.

```text
Logs Bedrock ───────┐
Eventos Docker ────┼─> broker de eventos ─> SQLite ─> SSE ─> navegador
Operações manager ─┘        │
                             └─> reconciliação direcionada
```

Valores em cache mantêm timestamps de observação e mudança. Informações obsoletas permanecem visíveis e marcadas em vez de serem substituídas por valores vazios falsos.

O CraftControl Telemetry Pack opcional atualmente é distribuído como `0.3.1`. Ele emite JSON versionado por schema e suporta snapshots autoritativos e eventos incrementais. Mudanças de blocos são agrupadas em lotes de cinco segundos. Lacunas de sequência, reinícios, intervalos ausentes, armazenamento bloqueado e capacidades Bedrock parciais degradam a saúde e solicitam um snapshot coalescido. Deltas obsoletos são rejeitados; a saúde volta a saudável somente após reconciliação completa.

Snapshots podem recuperar agregados de toda a vida após indisponibilidade. Eles não podem recriar cada evento histórico perdido, timestamp, causa ou coordenada, e o CraftControl nunca inventa esses detalhes.

A área Servidor informa separadamente a imagem do frontend, imagem do backend, Behavior Pack instalado, tempo de resposta do pack, sequência, snapshot concluído, lacunas, eventos ausentes, migração de armazenamento e métricas suportadas. Instalação, atualização, desativação, remoção, backup e rollback estão disponíveis pela interface e CLI. Mudanças no pack nunca reiniciam o Bedrock automaticamente.

```bash
docker compose -f docker-compose.split.yml exec craftcontrol-backend craftcontrol telemetry status
docker compose -f docker-compose.split.yml exec craftcontrol-backend craftcontrol telemetry install
```

Veja [Integração do Telemetry Pack](docs/telemetry-pack.md) para o ciclo de vida e o runbook de recuperação.

## Instalação

O CraftControl requer Docker Engine com o plugin Compose e uma implantação
existente de `itzg/minecraft-bedrock-server`. Ele roda ao lado do projeto
Bedrock e deve ser implantado pelos comandos protegidos. Nunca execute
`docker compose up` sem opções a partir de um checkout de desenvolvimento.

Veja [Instalação](docs/installation.pt-BR.md) para pré-requisitos, layout esperado,
configuração, cutover, acesso, verificações pós-instalação e solução de problemas.

## Configuração

| Variável | Padrão | Finalidade |
| --- | --- | --- |
| `MANAGER_PORT` | `8082` | Porta pública do frontend |
| `MINECRAFT_CONTAINER` | `minecraft-bedrock` | Contêiner Bedrock gerenciado pelo CraftControl |
| `MINECRAFT_PROJECT` | `/minecraft-project` | Projeto Compose Bedrock dentro do backend |
| `DATABASE_PATH` | `/data/manager.db` | Estado SQLite e histórico de jogadores |
| `BACKUP_ROOT` | `/data/backups/coordinated` | Conjuntos coordenados de recuperação |
| `BOOTSTRAP_OPERATOR` | `VonCrush` | Configuração inicial de compatibilidade de operador no jogo |
| `RECONCILE_SECONDS` | `900` | Intervalo de reconciliação de segurança completa |
| `AUTH_MODE` | `local` | Autenticação interna; `disabled` é somente compatibilidade de recuperação |
| `AUTH_COOKIE_SECURE` | `true` | Restringe cookies de sessão a HTTPS |
| `TZ` | `America/Sao_Paulo` | Fuso horário de runtime e análises |

As versões em execução do frontend e backend vêm de `versions.env`. Nomes antigos de serviço, banco, pacote e variáveis de ambiente continuam suportados como overlays de compatibilidade; caminhos persistentes não são renomeados destrutivamente.

## Autenticação e acesso

Contas do painel se vinculam a jogadores que o Bedrock já observou. A identidade privada baseada em XUID sobrevive a mudanças de Gamertag; XUIDs nunca aparecem em respostas públicas da API ou na interface.

| Capability | Visualizador | Operador | Proprietário |
| --- | :---: | :---: | :---: |
| Ler status, jogadores, histórico e telemetria | Sim | Sim | Sim |
| Alterar configurações, gamerules, horário e clima | Não | Sim | Sim |
| Iniciar e reiniciar Bedrock | Não | Sim | Sim |
| Parar Bedrock | Não | Não | Sim |
| Alterar permissão de operador no jogo | Não | Sim | Sim |
| Gerenciar usuários do painel e o Telemetry Pack | Não | Não | Sim |

Permissão Minecraft e papel do CraftControl são independentes. Capabilities da API são a fronteira de segurança; ocultar um controle no navegador não é autorização.

Gere o primeiro código único de proprietário após esse jogador entrar no Bedrock:

```bash
docker compose -f docker-compose.split.yml exec craftcontrol-backend \
  craftcontrol auth bootstrap --player VonCrush
```

Proprietários geram códigos de convite ou recuperação a partir do perfil individual de um jogador. Códigos expiram em 15 minutos, funcionam uma vez e são armazenados apenas como hashes. Senhas usam `scrypt` com salt; sessões opacas no servidor têm expiração ociosa e absoluta. Toda mutação autenticada exige token CSRF associado à sessão exata e requisição válida de mesma origem.

Veja [Autenticação e autorização locais](docs/authentication.md).

## Dados de jogadores e análises

O SQLite armazena perfis permanentes, aliases, presença, sessões, tempo de jogo acumulado, permissões, mortes, histórico de eventos e telemetria estruturada opcional. Desconectar um jogador fecha ou infere a sessão; nunca exclui o perfil.

A área Jogadores consolida totais e detalhamentos de toda a vida antes das evidências recentes: abates por criatura, blocos por tipo, exploração por dimensão, sessões, mortes e histórico técnico. A área Dados oferece visões filtradas e paginadas de todo o servidor. Mortes estruturadas e derivadas são deduplicadas para exibição, enquanto a evidência bruta permanece privada.

Ícones de criaturas, blocos, projéteis, navegação, ações, estados e métricas usam pixel art SVG original incluída. Identificadores do jogo são localizados em português, inglês e espanhol, com fallback neutro localizado para identificadores desconhecidos. Veja [Regras do sistema visual](docs/design-system.md).

## Backups e recuperação

O CraftControl não é dono do mundo Minecraft. O mundo permanece no projeto Bedrock; o estado do gerenciador vive em `manager.db`. Migrações SQLite são transacionais e criam um backup imutável do banco antes da primeira migração pendente.

Use comandos coordenados em vez de copiar um banco ou mundo em execução:

```bash
docker compose -f docker-compose.split.yml exec craftcontrol-backend craftcontrol backup create
docker compose -f docker-compose.split.yml exec craftcontrol-backend craftcontrol backup list
docker compose -f docker-compose.split.yml exec craftcontrol-backend craftcontrol backup verify BACKUP_ID
```

Quando o Bedrock está em execução, o serviço de backup mantém os saves somente durante a janela de cópia e os retoma mesmo após falha. Conjuntos de recuperação incluem mundo, banco SQLite, configuração do servidor, allowlists, permissões, arquivos do Behavior Pack, checksums e manifesto versionado. A restauração é deliberadamente offline e cria uma cópia de recuperação pré-restauração.

Veja [Backup e restauração coordenados](docs/backup-and-restore.md) e [Migrações de banco de dados](docs/database-migrations.md).

## Releases independentes e rollback

`versions.env` fixa o par frontend/backend testado. Implante ambos ou somente o componente alterado:

```bash
bin/deploy-craftcontrol-release --check
bin/deploy-craftcontrol-release

bin/deploy-craftcontrol-frontend
bin/deploy-craftcontrol-backend

bin/deploy-craftcontrol-frontend --rollback VERSION
bin/deploy-craftcontrol-backend --rollback VERSION
bin/deploy-craftcontrol-release --rollback FRONTEND_VERSION BACKEND_VERSION
```

A implantação do frontend prova que o contêiner do backend não foi alterado. A implantação do backend cria e verifica um backup coordenado, confere SQLite e montagens persistentes e prova que o contêiner frontend não foi recriado. `bin/cutover-craftcontrol-split` realiza o cutover dividido único e mantém a imagem combinada como caminho explícito de compatibilidade de emergência.

A interface lê `/version.json` do frontend e metadados de release do backend, mantendo a ativação da imagem separada da instalação do Behavior Pack e timestamps de resposta de runtime.

## Desenvolvimento e portões de qualidade

O CraftControl usa Python 3.12, Flask, Gunicorn, SQLite, Docker SDK para Python, Nginx e JavaScript do navegador sem dependências.

```bash
bin/check-frontend       # Sintaxe JS, i18n, testes de interação e contrato visual
bin/check-backend        # Aplicação Python e testes de persistência
bin/check-contracts      # OpenAPI, superfície de rotas, Swagger, declarações geradas
bin/check-integration    # Builds Compose, runtime dividido, arquitetura e segurança de deploy
bin/check                # portão local completo
```

GitHub Actions e Gitea Actions executam as quatro fronteiras de modo independente. As alterações usam Conventional Commits e a implantação de produção só é aceita a partir de `main` limpo e publicado.

Veja [Configuração de desenvolvimento](docs/development-setup.md) para pré-requisitos, configuração de ambiente e guia de tarefas comuns.

## Estado da segurança

As proteções atuais incluem contas locais vinculadas a jogadores, capabilities de papel, credenciais únicas com hash, sessões opacas revogáveis, limitação de login, registros de auditoria de segurança, CSRF vinculado à sessão, validação de origem, allowlists estritas de comandos, validação de entrada, escritas atômicas de configuração, XUIDs ocultos e `no-new-privileges`.

Trabalho de fortalecimento restante:

1. substituir o acesso direto ao socket Docker por um gateway de operações restrito;
2. documentar e automatizar uma fronteira TLS/proxy reverso suportada;
3. continuar removendo overlays de compatibilidade após janelas de migração testadas;
4. ampliar instalação comunitária, diagnósticos e automação de releases.

Para o modelo completo de ameaças, proteções atuais e roadmap de fortalecimento, veja [docs/security.md](docs/security.md). Para reportar uma vulnerabilidade privadamente veja [SECURITY.md](SECURITY.md).

## Contribuição

Veja [CONTRIBUTING.md](CONTRIBUTING.md) para nomes de branch, formato de título de PR, requisitos de metadados, Conventional Commits, portão de qualidade e interação com CodeRabbit.

### Skills do Codex

Se você usa Codex, este repositório oferece skills equivalentes de fluxo de trabalho em `.agents/skills/`. O Codex descobre cada skill pelo arquivo `SKILL.md`:

| Skill | Quando usar |
|---|---|
| `execute-issue` | Executa uma issue do início ao merge |
| `start-issue` | Verifica metadados, lê contexto, mapeia código e cria branch |
| `implement` | Detecta a camada, implementa, testa e faz self-review |
| `ship-issue` | Commit, PR, CI, CodeRabbit e sync Gitea |
| `handle-pr-findings` | Triagem explícita de findings, correções e respostas nas threads |
| `review-pr` | Self-review ou triagem de findings por camada |
| `backend` | Padrões Python: DI, Protocols, `is None`, composition root e fakes |
| `frontend` | Padrões JS: injeção de deps, ESM, i18n e testes |
| `create-issue` | Workshop para criar issues bem formadas |
| `manage-project` | Gerencia issues nos GitHub Project boards |
| `manage-milestone` | Gerencia milestones e audita backlog |

As skills são instruções do repositório: o Codex continua seguindo `AGENTS.md`, as instruções de segurança e a confirmação do usuário para ações externas como push, merge e deploy.

### Skills do Claude Code

Se você usa Claude Code, este repositório oferece um conjunto de skills em `.claude/agents/` que codificam o fluxo de trabalho e as convenções do projeto. Invoque-as com `/nome-da-skill`:

| Skill | Quando usar |
|---|---|
| `$execute-issue <n>` | Executa uma issue do início ao merge — orquestra as três fases abaixo |
| `$start-issue <n>` | Verifica metadados, lê contexto obrigatório, mapeia código, cria branch |
| `$implement` | Detecta camada (backend$frontend), carrega skill especializada, implementa e testa |
| `$handle-pr-findings` | Triagem explícita de findings, correções e respostas nas threads |
| `$ship-issue` | Commit, PR com metadados, CI, CodeRabbit, sync Gitea |
| `$review-pr <n>` | Self-review ou triagem de findings — checklist por camada (backend, frontend, docs) |
| `$backend` | Padrões Python: DI, Protocols, `is None`, composition root, fakes |
| `$frontend` | Padrões JS: injeção de deps, ESM, i18n e testes |
| `$create-issue` | Workshop PM/Dev Hat → cria issue bem formada |
| `$manage-project` | Adiciona/lista/audita issues nos project boards |
| `$manage-milestone` | Atribui/lista/audita milestones, detecta backlog solto |

## Licença e marcas

Copyright 2026 Danilo Ramos.

CraftControl é licenciado sob a [Licença Apache 2.0](LICENSE). A licença se aplica ao código-fonte original do CraftControl, documentação, Telemetry Pack e ativos visuais deste repositório, salvo quando um arquivo declarar o contrário.

CraftControl é independente e não é afiliado à Mojang Studios ou Microsoft. Minecraft é uma marca comercial da Microsoft Corporation.

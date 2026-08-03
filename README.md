# Minecraft Bedrock Manager

Painel web local e mobile-first para administrar o servidor Bedrock sem editar arquivos ou digitar comandos no console.

## MVP

- propriedades persistentes gravadas no `.env` do serviço Bedrock
- aplicação das mudanças com recriação controlada do container
- gamerules em tempo real por uma lista fechada
- atalhos de dia, noite e clima limpo
- iniciar, parar e reiniciar
- sem autenticação própria; destinado exclusivamente à LAN e futura proteção pelo Authelia

## Executar

```bash
cd /mnt/storage/docker/minecraft-bedrock-manager
cp .env.example .env
docker compose up -d --build
```

Acesse `http://IP-DO-HOST:8082`.

## Segurança

Este MVP precisa do socket Docker para executar somente ações cadastradas contra o container `minecraft-bedrock`. Não há terminal genérico na API. Ainda assim, acesso ao socket equivale tecnicamente a privilégio administrativo no host; não exponha a porta 8082 à Internet. A próxima etapa pode substituir o acesso direto por um gateway de operações mínimo e integrar Authelia/CSRF.

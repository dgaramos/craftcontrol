# Frontend review

- Preserve ESM sem bundler e a direção `core → components → features`.
- Features recebem `state`, `api`, `$`, `t` e helpers por injeção;
  `composition.js` monta as dependências reais. Não use DOM/global direto.
- Toda cópia visível passa por `t()` e mantém PT/EN/ES. Preserve interface móvel,
  estados vazio/erro, CSRF e SSE sem polling desnecessário.
- Escape conteúdo externo antes de inseri-lo no DOM.
- Testes reutilizam helpers, restauram globais e não dependem de tempo ou ordem.

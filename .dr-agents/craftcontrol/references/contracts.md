# Contract checklist

- Treat `packages/contracts/openapi.json` as canonical. Keep routes, envelopes,
  errors, authentication cookies, capabilities, CSRF, pagination, and generated
  frontend declarations aligned.
- Do not change only one side of an endpoint. Evaluate consumer compatibility,
  migration, and contract coverage.

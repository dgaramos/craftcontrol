export function createRulesFeature({ renderSettingsGroups }) {
  const renderRules = () => renderSettingsGroups([
    "Interface", "Jogabilidade", "Tempo e clima", "Criaturas", "Drops", "Comandos",
  ]);
  return { renderRules };
}

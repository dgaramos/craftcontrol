export function createRulesFeature({ getSettingsFeature }) {
  const renderRules = () => getSettingsFeature().renderSettingsGroups([
    "Interface", "Jogabilidade", "Tempo e clima", "Criaturas", "Drops", "Comandos",
  ]);
  return { renderRules };
}

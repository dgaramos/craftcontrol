import { jest } from "@jest/globals";
import { createRulesFeature } from "../../../static/js/features/rules/index.js";

describe("createRulesFeature", () => {
  test("renderRules calls renderSettingsGroups with the six rule groups", () => {
    const renderSettingsGroups = jest.fn();
    const getSettingsFeature = () => ({ renderSettingsGroups });
    const { renderRules } = createRulesFeature({ getSettingsFeature });
    renderRules();
    expect(renderSettingsGroups).toHaveBeenCalledTimes(1);
    const [groups] = renderSettingsGroups.mock.calls[0];
    expect(groups).toEqual([
      "Interface", "Jogabilidade", "Tempo e clima",
      "Criaturas", "Drops", "Comandos",
    ]);
  });
});

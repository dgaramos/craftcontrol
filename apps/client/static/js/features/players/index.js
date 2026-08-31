import { createPlayerAccess } from "./access.js?v=7";
import { createPlayerHistory } from "./history.js?v=7";
import { createPlayerProfile } from "./profile.js?v=7";
import { createPlayerTelemetry } from "./telemetry.js?v=7";
import { createPlayersWorkspace } from "./workspace.js?v=7";

export function createPlayersFeature(deps) {
  const { state, content, t, localized, api, $, escapeHtml, toast, getSettingsFeature, formatDate, formatDuration, gameLabel, gameIcon, gameTermMarkup, optionLabel, blockTermMarkup, dimensionName, formatRankingValue, uiIcon, sessionMoment, timelineTimestamp, getNavigation, renderAnalyticsPanel } = deps;
  let renderPlayersPanel;
  let renderPlayerDetail;
  const history = createPlayerHistory({ state, t, escapeHtml, gameLabel, gameIcon, gameTermMarkup, optionLabel, formatDate, formatDuration, sessionMoment, timelineTimestamp });
  const telemetry = createPlayerTelemetry({ state, t, escapeHtml, gameTermMarkup, blockTermMarkup, dimensionName, formatRankingValue, uiIcon, gameIcon, formatDate });
  const { panelAccessDetailMarkup, bindPlayerAccess } = createPlayerAccess({ state, t, $, escapeHtml, api, toast, renderPlayersPanel: (...args) => renderPlayersPanel(...args) });
  const { historyMarkup, sessionsMarkup, profileMarkup, deathHistoryMarkup } = history;
  const { sortedTelemetryEntries, playerBreakdownMarkup, playerDataMarkup } = telemetry;
  renderPlayerDetail = createPlayerProfile({ state, content, t, localized, api, $, escapeHtml, formatDate, formatDuration, playerDataMarkup, profileMarkup, getSettingsFeature, panelAccessDetailMarkup, renderPlayersPanel: (...args) => renderPlayersPanel(...args), renderAnalyticsPanel, getNavigation, toast, bindPlayerAccess });
  renderPlayersPanel = createPlayersWorkspace({ state, content, t, localized, api, $, escapeHtml, toast, getSettingsFeature, formatDuration, formatDate, renderPlayerDetail: (...args) => renderPlayerDetail(...args) });
  return { renderPlayersPanel, renderPlayerDetail };
}

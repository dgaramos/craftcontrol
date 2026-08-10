import { createPlayerAccess } from "./access.js?v=7";
import { createPlayerHistory } from "./history.js?v=7";
import { createPlayerProfile } from "./profile.js?v=7";
import { createPlayerTelemetry } from "./telemetry.js?v=7";
import { createPlayersWorkspace } from "./workspace.js?v=7";

export function createPlayersFeature(deps) {
  let renderPlayersPanel;
  let renderPlayerDetail;
  const history = createPlayerHistory(deps);
  const telemetry = createPlayerTelemetry(deps);
  const access = createPlayerAccess({
    ...deps,
    renderPlayersPanel: (...args) => renderPlayersPanel(...args),
  });
  renderPlayerDetail = createPlayerProfile({
    ...deps,
    ...history,
    ...telemetry,
    ...access,
    renderPlayersPanel: (...args) => renderPlayersPanel(...args),
  });
  renderPlayersPanel = createPlayersWorkspace({
    ...deps,
    renderPlayerDetail: (...args) => renderPlayerDetail(...args),
  });
  return { renderPlayersPanel, renderPlayerDetail };
}

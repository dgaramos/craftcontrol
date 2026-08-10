import { createPlayerAccess } from "./access.js?v=6";
import { createPlayerHistory } from "./history.js?v=6";
import { createPlayerProfile } from "./profile.js?v=6";
import { createPlayerTelemetry } from "./telemetry.js?v=6";
import { createPlayersWorkspace } from "./workspace.js?v=6";

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

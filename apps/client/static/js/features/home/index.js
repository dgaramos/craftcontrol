export function createHomeFeature({ state, $, t, api, toast }) {
  let _pollInterval = null;

  function _stopPolling() {
    if (_pollInterval !== null) {
      clearInterval(_pollInterval);
      _pollInterval = null;
    }
  }

  function render() {
    _stopPolling();
  }

  return { render };
}

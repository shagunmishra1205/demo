chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
});
chrome.action.onClicked.addListener((tab) => {
  if (tab?.windowId) chrome.sidePanel.open({ windowId: tab.windowId }).catch(() => {});
});

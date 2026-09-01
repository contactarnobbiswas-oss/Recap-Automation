// Open Full-Page Dashboard on extension icon click
chrome.action.onClicked.addListener(() => {
  chrome.tabs.create({ url: chrome.runtime.getURL("fullpage.html") });
});

const en = document.getElementById("en");
const gr = document.getElementById("gr");
const st = document.getElementById("st");
const listEl = document.getElementById("list");

chrome.storage.local.get({ enabled: true, grabber: true }, (v) => {
  en.checked = v.enabled;
  gr.checked = v.grabber;
});
en.addEventListener("change", () => chrome.storage.local.set({ enabled: en.checked }));
gr.addEventListener("change", () => chrome.storage.local.set({ grabber: gr.checked }));

fetch("http://127.0.0.1:9614/ping")
  .then((r) => r.json())
  .then(() => { st.textContent = "✔ TurboDM çalışıyor"; st.style.color = "green"; })
  .catch(() => { st.textContent = "✖ TurboDM kapalı"; st.style.color = "crimson"; });

chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
  if (!tab || !/^https?:/i.test(tab.url || "")) return;
  // Her sayfada: sayfanın videosunu TurboDM'de aç (kaliteler uygulamada listelenir)
  const page = document.getElementById("page");
  page.style.display = "block";
  page.onclick = () => chrome.runtime.sendMessage(
    { type: "tdm-page", tabId: tab.id, url: tab.url, title: tab.title || "" },
    (r) => (page.textContent = r && r.ok ? "✔ TurboDM'de kalite seçin" : "✖ TurboDM çalışmıyor"));
  chrome.runtime.sendMessage({ type: "tdm-list", tabId: tab.id }, (list) => {
    if (!list || !list.length) return;
    listEl.className = "";
    listEl.textContent = "";
    for (const m of list) {
      const row = document.createElement("div");
      row.className = "m";
      const s = document.createElement("span");
      s.textContent = m.label;
      s.title = m.url;
      const b = document.createElement("button");
      b.textContent = "İndir";
      b.onclick = () => chrome.runtime.sendMessage(
        { type: "tdm-download", tabId: tab.id, media: m, title: tab.title, pageUrl: tab.url },
        (r) => (b.textContent = r && r.ok ? "✔" : "✖"));
      row.append(s, b);
      listEl.appendChild(row);
    }
  });
});

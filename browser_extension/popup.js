const M = (key) => chrome.i18n.getMessage(key) || key;  // _locales/<dil>/messages.json
document.documentElement.dir = chrome.i18n.getMessage("@@bidi_dir") || "ltr";
for (const el of document.querySelectorAll("[data-i18n]")) el.textContent = M(el.dataset.i18n);

const en = document.getElementById("en");
const gr = document.getElementById("gr");
const st = document.getElementById("st");

chrome.storage.local.get({ enabled: true, grabber: true }, (v) => {
  en.checked = v.enabled;
  gr.checked = v.grabber;
});
en.addEventListener("change", () => chrome.storage.local.set({ enabled: en.checked }));
gr.addEventListener("change", () => chrome.storage.local.set({ grabber: gr.checked }));

fetch("http://127.0.0.1:9614/ping")
  .then((r) => r.json())
  .then(() => { st.textContent = M("popupRunning"); st.className = "pill ok"; })
  .catch(() => { st.textContent = M("popupClosed"); st.className = "pill bad"; });

function showQualities(tab) {
  const box = document.getElementById("quals");
  const list = document.getElementById("qlist");
  box.style.display = "block";
  const wait = document.createElement("div");
  wait.className = "note";
  wait.textContent = M("loadingQualities");
  list.appendChild(wait);
  // TurboDM kaliteleri bulur (~3 sn; sonuç önbellekte kalır, sayfadaki menü de aynısını kullanır)
  chrome.runtime.sendMessage({ type: "tdm-formats", url: tab.url }, (data) => {
    wait.remove();
    if (!data || data.error || !data.choices || !data.choices.length) {
      box.style.display = "none";  // kalite bulunamadı (TurboDM kapalıysa durum etiketi zaten söylüyor)
      return;
    }
    for (const c of data.choices) {
      const row = document.createElement("div");
      row.className = "q";
      row.textContent = c.label;
      row.onclick = () => chrome.runtime.sendMessage(
        { type: "tdm-page", tabId: tab.id, url: tab.url, title: data.title || tab.title || "", choice: c },
        (r) => (row.textContent = (r && r.ok ? M("pickFolder") : "✖ " + M("appDown"))));
      list.appendChild(row);
    }
  });
}

chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
  if (!tab || !/^https?:/i.test(tab.url || "")) return;
  // Her sayfada: sayfanın videosunu TurboDM'de aç (kaliteler uygulamada listelenir)
  const page = document.getElementById("page");
  page.style.display = "block";
  page.onclick = () => {
    page.disabled = true;
    chrome.runtime.sendMessage(
      { type: "tdm-page", tabId: tab.id, url: tab.url, title: tab.title || "" },
      (r) => { page.textContent = r && r.ok ? M("pickQuality") : "✖ " + M("appDown"); page.disabled = false; });
  };
  // Sayfada görünen bir video varsa kaliteleri burada da listele (sayfadaki "Bu videoyu indir" menüsüyle aynı)
  chrome.tabs.sendMessage(tab.id, { type: "tdm-has-video" }, (r) => {
    void chrome.runtime.lastError;  // videosuz sayfa / eklentinin çalışmadığı sayfa: yanıt yok
    if (r && r.video) showQualities(tab);
  });
  // Sayfanın yüklediği video/ses akışları: yalnızca bulunduysa liste görünür (yoksa bölüm hiç çıkmaz)
  chrome.runtime.sendMessage({ type: "tdm-list", tabId: tab.id }, (list) => {
    if (!list || !list.length) return;
    const listEl = document.getElementById("list");
    document.getElementById("media").style.display = "block";
    document.getElementById("count").textContent = list.length;
    for (const m of list) {
      const row = document.createElement("div");
      row.className = "m";
      const s = document.createElement("span");
      s.textContent = m.label;
      s.title = m.url;
      const b = document.createElement("button");
      b.textContent = M("download");
      b.onclick = () => chrome.runtime.sendMessage(
        { type: "tdm-download", tabId: tab.id, media: m, title: tab.title, pageUrl: tab.url },
        (r) => (b.textContent = r && r.ok ? "✔" : "✖"));
      row.append(s, b);
      listEl.appendChild(row);
    }
  });
});

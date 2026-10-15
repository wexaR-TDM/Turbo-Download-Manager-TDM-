// TurboDM video yakalayıcı: sayfadaki videoların üstüne "Bu videoyu indir" düğmesi ekler (IDM paneli gibi).
// Eklenti siteleri tanımaz; her sitede aynı çalışır:
//  * Sayfanın ana videosu (oynatıcı ekranın büyük kısmını kaplıyorsa): düğme her zaman görünür. Tıklayınca
//    TurboDM'e sayfa adresi sorulur, uygulama bulabildiği kaliteleri listeler; ayrıca sayfanın yüklediği
//    video/ses akışları da menüde yer alır.
//  * Diğer videolar: sayfanın yüklediği akışlar algılanınca düğme görünür, tıklayınca akış listesi açılır.
(() => {
  if (window.__tdmLoaded) return;
  window.__tdmLoaded = true;
  let mediaCount = 0;
  const panels = new WeakMap();
  let lastHref = location.href;

  function send(msg) {
    return new Promise((res) => {
      try { chrome.runtime.sendMessage(msg, (r) => res(chrome.runtime.lastError ? null : r)); }
      catch { res(null); }
    });
  }

  function pageTitle() {
    let t;
    try { t = window.top.document.title || document.title; } catch { t = document.title; }
    return t.replace(/^\(\d+\)\s*/, "");  // "(3) Başlık" → okunmamış bildirim sayısı
  }

  function closeMenus() {
    document.querySelectorAll(".tdm-menu").forEach((m) => m.remove());
  }

  function flash(btn, text) {
    const old = btn.dataset.label || btn.textContent;
    btn.dataset.label = old;
    btn.textContent = text;
    setTimeout(() => (btn.textContent = old), 2500);
  }

  function makeButton(video) {
    const btn = document.createElement("div");
    btn.className = "tdm-grab";
    btn.textContent = "⬇ Bu videoyu indir";
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      openMenu(btn, video);
    });
    document.body.appendChild(btn);
    return btn;
  }

  function place(btn, video) {
    const r = video.getBoundingClientRect();
    const visible = r.width >= 200 && r.height >= 120 && r.bottom > 0 && r.top < innerHeight;
    btn.style.display = visible ? "block" : "none";
    btn.style.top = window.scrollY + r.top + 10 + "px";
    btn.style.left = window.scrollX + r.right - btn.offsetWidth - 10 + "px";
  }

  // Ana video: görünür ve ekranın büyük kısmını kaplıyor (izleme sayfası, dikey kısa video oynatıcısı,
  // gömülü oynatıcı). Akış listelerindeki küçük önizlemeler sayılmaz.
  function isMainVideo(v) {
    const r = v.getBoundingClientRect();
    if (r.width < 200 || r.height < 120 || r.bottom <= 0 || r.top >= innerHeight) return false;
    return r.height >= innerHeight * 0.45 || r.width >= innerWidth * 0.45;
  }

  function placeMenu(menu, btn) {
    const r = btn.getBoundingClientRect();
    menu.style.top = window.scrollY + r.bottom + 4 + "px";
    menu.style.left = window.scrollX + Math.max(4, r.right - 320) + "px";
  }

  function menuRow(parent, cls, text, title) {
    const el = document.createElement("div");
    el.className = cls;
    el.textContent = text;
    if (title) el.title = title;
    parent.appendChild(el);
    return el;
  }

  function streamRows(menu, btn, list) {
    // HLS önce, sonra büyük dosyalar
    const stream = (m) => m.kind === "hls" || m.kind === "dash";
    list.sort((a, b) => stream(b) - stream(a) || (b.size || 0) - (a.size || 0));
    for (const m of list) {
      const item = menuRow(menu, "tdm-item", m.label, m.url);
      item.addEventListener("click", async () => {
        closeMenus();
        const r = await send({ type: "tdm-download", media: m, title: pageTitle(), pageUrl: location.href });
        flash(btn, r && r.ok ? "✔ TurboDM'e gönderildi" : "✖ TurboDM çalışmıyor");
      });
    }
  }

  // IDM gibi: menü sayfada açılır; kalite seçilince TurboDM'de kayıt yeri penceresi o kalite seçili gelir
  async function openMenu(btn, video) {
    if (document.querySelector(".tdm-menu")) { closeMenus(); return; }
    const url = location.href, title = pageTitle(), main = isMainVideo(video);
    const menu = document.createElement("div");
    menu.className = "tdm-menu";
    // oynatıcının tıklamayı (oynat/duraklat) almasını engelle
    ["mousedown", "click", "dblclick"].forEach((ev) => menu.addEventListener(ev, (e) => e.stopPropagation()));
    menuRow(menu, "tdm-head", "TurboDM ile indir");
    const qualities = document.createElement("div");
    const streams = document.createElement("div");
    menu.append(qualities, streams);
    const wait = main ? menuRow(qualities, "tdm-empty", "Kaliteler alınıyor…") : null;
    placeMenu(menu, btn);
    document.body.appendChild(menu);

    const list = (await send({ type: "tdm-list" })) || [];
    if (!menu.isConnected) return;  // bu arada kapatıldı
    streamRows(streams, btn, list);

    let found = list.length > 0, appDown = false;
    if (main) {
      const data = await send({ type: "tdm-formats", url });
      if (!menu.isConnected) return;
      wait.remove();
      if (data && !data.error && data.choices && data.choices.length) {
        found = true;
        for (const c of data.choices) {
          const item = menuRow(qualities, "tdm-item", c.label);
          item.addEventListener("click", async () => {
            closeMenus();
            const r = await send({ type: "tdm-page", url, title: data.title || title, choice: c });
            flash(btn, r && r.ok ? "✔ TurboDM'de kayıt yerini seçin" : "✖ TurboDM çalışmıyor");
          });
        }
      } else {
        appDown = !data || /fetch/i.test(data.error || "");
      }
    }
    if (appDown) menuRow(menu, "tdm-empty tdm-err", "TurboDM çalışmıyor. Programı açıp tekrar deneyin.");
    else if (!found) menuRow(menu, "tdm-empty", "Henüz video bulunamadı. Videoyu oynatmayı deneyin.");
    if (main) {
      const more = menuRow(menu, "tdm-item tdm-more", "Diğer seçenekler (TurboDM'de aç)…");
      more.addEventListener("click", async () => {
        closeMenus();
        const r = await send({ type: "tdm-page", url, title });
        flash(btn, r && r.ok ? "✔ TurboDM'de açıldı" : "✖ TurboDM çalışmıyor");
      });
    }
    placeMenu(menu, btn);
  }

  function position() {
    if (location.href !== lastHref) {  // sayfa içi geçiş (tek sayfalık uygulamalar): eski menüyü kapat
      lastHref = location.href;
      closeMenus();
      send({ type: "tdm-frame", url: location.href });
    }
    document.querySelectorAll("video").forEach((v) => {
      let btn = panels.get(v);
      if (!btn) {
        const direct = v.currentSrc && /^https?:/i.test(v.currentSrc);
        if (!isMainVideo(v) && mediaCount === 0 && !direct) return;
        const r = v.getBoundingClientRect();
        if (r.width < 200 || r.height < 120) return; // küçük önizlemeler
        btn = makeButton(v);
        panels.set(v, btn);
        if (direct) send({ type: "tdm-element-src", url: v.currentSrc });
      }
      place(btn, v);
    });
  }

  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.type === "tdm-media") {
      mediaCount = msg.count;
      position();
    }
  });

  document.addEventListener("click", closeMenus);
  window.addEventListener("scroll", position, { passive: true });
  window.addEventListener("resize", position);
  new MutationObserver(() => position()).observe(document.documentElement, { childList: true, subtree: true });
  setInterval(position, 1000);
  send({ type: "tdm-frame", url: location.href });  // bu çerçevenin adresi (gömülü oynatıcılar için)
  send({ type: "tdm-list" }).then((l) => { mediaCount = (l || []).length; position(); });
})();

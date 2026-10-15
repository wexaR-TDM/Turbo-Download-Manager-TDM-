// TurboDM video yakalayıcı: sayfadaki videoların üstüne "Bu videoyu indir" düğmesi ekler (IDM paneli gibi).
// Eklenti siteleri tanımaz; her sitede aynı çalışır:
//  * Sayfanın ana videosu (oynatıcı ekranın büyük kısmını kaplıyorsa): düğme her zaman görünür. Tıklayınca
//    TurboDM'e sayfa adresi sorulur, uygulama bulabildiği kaliteleri listeler; ayrıca sayfanın yüklediği
//    video/ses akışları da menüde yer alır.
//  * Diğer videolar: sayfanın yüklediği akışlar algılanınca düğme görünür, tıklayınca akış listesi açılır.
(() => {
  if (window.__tdmLoaded) return;
  window.__tdmLoaded = true;
  const M = (key) => { try { return chrome.i18n.getMessage(key) || key; } catch { return key; } };  // _locales

  // Eklenti güncellenince ya da yeniden yüklenince açık sekmelerdeki eski kopya eklentiyle bağını kaybeder
  // ("Extension context invalidated"). O zaman sessizce durur: düğmeleri kaldırır, zamanlayıcıları kapatır.
  function alive() {
    try { return !!(chrome.runtime && chrome.runtime.id); } catch { return false; }
  }
  let timer = null, observer = null;
  function shutdown() {
    clearInterval(timer);
    if (observer) observer.disconnect();
    window.removeEventListener("scroll", position);
    window.removeEventListener("resize", position);
    document.removeEventListener("click", closeMenus);
    document.querySelectorAll(".tdm-grab, .tdm-menu").forEach((el) => el.remove());
    window.__tdmLoaded = false;  // sayfa yenilenmeden yeni sürüm eklenirse o çalışabilsin
  }
  let mediaCount = 0;
  const panels = new WeakMap();
  let lastHref = location.href;

  function send(msg) {
    return new Promise((res) => {
      if (!alive()) { res(null); return; }
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
    btn.textContent = M("btnDownload");
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      openMenu(btn, video);
    });
    document.body.appendChild(btn);
    return btn;
  }

  // Videonun ekranda gerçekten görünen kısmı (yoksa null). Hikâye/kısa video sayfaları yan taraftaki
  // videoları önceden yükleyip kaydırılmış bir alanın dışında (overflow ile kesilmiş), şeffaf ya da gizli
  // tutar; bunlara düğme konmaz.
  function visibleRect(v) {
    const r = v.getBoundingClientRect();
    let top = Math.max(r.top, 0), left = Math.max(r.left, 0);
    let bottom = Math.min(r.bottom, innerHeight), right = Math.min(r.right, innerWidth);
    // body/html'e kadar: onların overflow ayarı pencereye aktarılır, kendileri kesmez (bazı büyük video
    // sitelerinde body'nin yüksekliği 0 ölçülür; hesaba katılırsa video görünmez sanılıyordu)
    for (let el = v, depth = 0; el && el !== document.body && el !== document.documentElement && depth < 25;
      el = el.parentElement, depth++) {
      const cs = getComputedStyle(el);
      if (cs.display === "none" || cs.visibility === "hidden" || parseFloat(cs.opacity) < 0.1) return null;
      if (el !== v && cs.overflow !== "visible" && cs.display !== "contents") {
        const p = el.getBoundingClientRect();
        top = Math.max(top, p.top); left = Math.max(left, p.left);
        bottom = Math.min(bottom, p.bottom); right = Math.min(right, p.right);
      }
    }
    const w = right - left, h = bottom - top;
    // en az yarısı görünmüyorsa (kenardan sızan komşu video) sayma
    if (w < 200 || h < 120 || w * h < r.width * r.height * 0.5) return null;
    return { top, left, bottom, right, width: w, height: h };
  }

  function place(btn, video) {
    const r = visibleRect(video);
    btn.style.display = r ? "block" : "none";
    if (!r) return;
    btn.style.top = window.scrollY + r.top + 10 + "px";
    btn.style.left = window.scrollX + r.right - btn.offsetWidth - 10 + "px";
  }

  // Ana video: görünür ve ekranın büyük kısmını kaplıyor (izleme sayfası, dikey kısa video oynatıcısı,
  // gömülü oynatıcı). Akış listelerindeki küçük önizlemeler sayılmaz.
  function isMainVideo(v) {
    const r = visibleRect(v);
    if (!r) return false;
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
        flash(btn, r && r.ok ? M("sent") : "✖ " + M("appDown"));
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
    menuRow(menu, "tdm-head", M("ctxDownload"));
    const qualities = document.createElement("div");
    const streams = document.createElement("div");
    menu.append(qualities, streams);
    const wait = main ? menuRow(qualities, "tdm-empty", M("loadingQualities")) : null;
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
            flash(btn, r && r.ok ? M("pickFolder") : "✖ " + M("appDown"));
          });
        }
      } else {
        appDown = !data || /fetch/i.test(data.error || "");
      }
    }
    if (appDown) menuRow(menu, "tdm-empty tdm-err", M("appDownLong"));
    else if (!found) menuRow(menu, "tdm-empty", M("noVideo"));
    if (main) {
      const more = menuRow(menu, "tdm-item tdm-more", M("moreOptions"));
      more.addEventListener("click", async () => {
        closeMenus();
        const r = await send({ type: "tdm-page", url, title });
        flash(btn, r && r.ok ? M("opened") : "✖ " + M("appDown"));
      });
    }
    placeMenu(menu, btn);
  }

  function position() {
    if (!alive()) { shutdown(); return; }
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
        if (!visibleRect(v)) return; // küçük önizlemeler, gizli/kesilmiş videolar
        btn = makeButton(v);
        panels.set(v, btn);
        if (direct) send({ type: "tdm-element-src", url: v.currentSrc });
      }
      place(btn, v);
    });
  }

  chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
    if (msg.type === "tdm-media") {
      mediaCount = msg.count;
      position();
    } else if (msg.type === "tdm-has-video") {
      // eklenti penceresi soruyor: bu çerçevede görünen bir ana video var mı? Yalnızca varsa yanıt verilir
      // (videosuz çerçeveler sessiz kalır; hiçbiri yanıt vermezse pencere kalite listesini hiç göstermez)
      if ([...document.querySelectorAll("video")].some(isMainVideo)) reply({ video: true });
    }
  });

  document.addEventListener("click", closeMenus);
  window.addEventListener("scroll", position, { passive: true });
  window.addEventListener("resize", position);
  observer = new MutationObserver(() => position());
  observer.observe(document.documentElement, { childList: true, subtree: true });
  timer = setInterval(position, 1000);
  send({ type: "tdm-frame", url: location.href });  // bu çerçevenin adresi (gömülü oynatıcılar için)
  send({ type: "tdm-list" }).then((l) => { mediaCount = (l || []).length; position(); });
})();

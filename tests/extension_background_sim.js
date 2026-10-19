// background.js'i sahte tarayıcı ortamında çalıştırır: form (POST) indirmesi, normal indirme, TurboDM kapalı,
// TurboDM'in reddettiği ve TurboDM'de başlayamayıp tarayıcıya geri verilen indirmeleri dener.
const src = Deno.readTextFileSync(Deno.args[0]);
const listeners = {};
const ev = (name) => ({ addListener: (fn) => { (listeners[name] ||= []).push(fn); } });
const calls = { fetch: [], pause: [], cancel: [], native: [], resume: [], erase: [], download: [], ui: [], bodies: [] };
let appOnline = true;  // TurboDM açık mı (kapalıyken fetch bağlantı hatası verir)
let nextId = 100;
const handoffState = {};  // devir kimliği -> TurboDM'in /handoff yanıtı (yoksa "ok")
const session = {};
globalThis.chrome = {
  storage: { local: { get: (d, cb) => cb(d) }, onChanged: ev("storage"),
             session: { get: async (d) => ({ ...d, ...session }), set: async (v) => Object.assign(session, v) } },
  runtime: { onMessage: ev("msg"), onInstalled: ev("installed"), getManifest: () => ({ version: "x" }),
             // tarayıcının TurboDM yardımcısını çalıştırması: TurboDM açılır
             sendNativeMessage: async (host, msg) => { calls.native.push([host, msg.cmd]); appOnline = true; return { ok: true, launched: true }; } },
  i18n: { getMessage: (k) => k },
  contextMenus: { create() {}, onClicked: ev("ctx") },
  tabs: { onUpdated: ev("tabUpd"), onRemoved: ev("tabRem"), sendMessage: () => Promise.resolve() },
  action: { setBadgeText: () => Promise.resolve(), setBadgeBackgroundColor: () => Promise.resolve() },
  cookies: { getAll: async () => [] },
  webRequest: { onBeforeRequest: ev("beforeRequest"), onHeadersReceived: ev("headers"),
                onBeforeSendHeaders: ev("sendHeaders"), onSendHeaders: ev("sendHeaders2") },
  downloads: {
    onCreated: ev("created"), onChanged: ev("changed"), onDeterminingFilename: ev("filename"),
    pause: async (id) => calls.pause.push(id), resume: async (id) => calls.resume.push(id),
    cancel: async (id) => calls.cancel.push(id), erase: async (q) => calls.erase.push(q.id), search: async () => [],
    setUiOptions: async (o) => calls.ui.push(o.enabled),
    // tarayıcıda yeniden başlatılan indirme: gerçek tarayıcı gibi onCreated tetiklenir
    download: async (o) => { const id = nextId++; calls.download.push(o.url);
                             setTimeout(() => fire("created", { id, url: o.url, finalUrl: o.url, filename: "", mime: "" }), 0);
                             return id; },
  },
};
globalThis.fetch = async (url, opt) => {
  if (!appOnline) throw new TypeError("Failed to fetch");
  calls.fetch.push(url);
  const body = opt && opt.body ? String(opt.body) : "";
  if (body) calls.bodies.push(body);
  if (String(url).endsWith("/handoff")) {
    const b = JSON.parse(body);
    return { ok: true, status: 200, json: async () => ({ state: b.returned ? "returned" : (handoffState[b.id] || "ok") }) };
  }
  // TurboDM dosyaya ulaşamıyor (ör. Cloudflare): köprü {ok:false} döner
  const refused = body.includes("korumali-site");
  return { ok: true, status: 200, json: async () => (refused ? { ok: false, reason: "bot koruması" } : { ok: true }) };
};
new Function(src)();

const fire = async (name, arg) => { for (const fn of listeners[name] || []) await fn(arg); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const added = () => calls.fetch.filter((u) => String(u).endsWith("/add")).length;
const result = {};
await sleep(50);

// 1) Altyazı sitesi: form POST ile /ind isteği, ardından aynı adresten indirme başlar
await fire("beforeRequest", { method: "POST", url: "https://turkcealtyazi.org/ind", type: "main_frame", tabId: 1 });
await fire("created", { id: 1, url: "https://turkcealtyazi.org/ind", finalUrl: "https://turkcealtyazi.org/ind", filename: "", mime: "" });
result.form_post = { turbodm_e_gitti: added() > 0, duraklatildi: calls.pause.includes(1) };

// 2) Normal indirme (GET): TurboDM'e gitmeli; TurboDM açık olduğundan tarayıcıdaki indirme hemen iptal edilir
//    (duraklatılıp beklenmez) ve tarayıcının indirme penceresi kapalıdır (indirme bir an bile görünmesin)
calls.fetch.length = 0;
await fire("beforeRequest", { method: "GET", url: "https://example.com/dosya.zip", type: "main_frame", tabId: 1 });
await fire("created", { id: 2, url: "https://example.com/dosya.zip", finalUrl: "https://example.com/dosya.zip", filename: "dosya.zip", mime: "application/zip" });
result.normal_get = { turbodm_e_gitti: added() > 0, tarayicida_iptal: calls.cancel.includes(2),
                      duraklatilmadi: !calls.pause.includes(2), pencere_kapali: calls.ui.at(-1) === false };

// 3) TurboDM kapalı: eklenti onu açtırır (native messaging), açılınca indirmeyi aktarır
calls.fetch.length = 0;
appOnline = false;
await fire("created", { id: 3, url: "https://example.com/buyuk.iso", finalUrl: "https://example.com/buyuk.iso", filename: "buyuk.iso", mime: "" });
result.app_closed = { acildi: calls.native.length === 1 && calls.native[0][1] === "launch",
                      turbodm_e_gitti: added() > 0, tarayicida_iptal: calls.cancel.includes(3) };

// 5) Form + yönlendirme (metin2.download): doğrulama kodlu form /get/… adresine gider, site imzalı depolama
//    bağlantısına yönlendirir. Son adres düz bir indirme: TurboDM'e verilmeli (son adresle)
calls.fetch.length = 0;
calls.bodies.length = 0;
await fire("beforeRequest", { method: "POST", url: "https://site.example/get/TOKEN/", type: "main_frame", tabId: 1 });
await fire("created", { id: 5, url: "https://site.example/get/TOKEN/", finalUrl: "https://depo.example/files/TOKEN.zip?X-Amz-Signature=abc",
                        filename: "Paket.zip", mime: "application/zip" });
result.post_redirect = { turbodm_e_gitti: added() > 0,
                         son_adresle: calls.bodies.some((b) => b.includes("depo.example/files/TOKEN.zip")),
                         tarayicida_iptal: calls.cancel.includes(5) };

// 4) TurboDM dosyaya ulaşamıyor (bot koruması): indirme tarayıcıda yeniden başlatılır ve bu kez yakalanmaz;
//    tarayıcının indirme penceresi bu indirmeyi göstermek için açılır
calls.fetch.length = 0;
calls.ui.length = 0;
await fire("created", { id: 4, url: "https://korumali-site.example/dosya.zip", finalUrl: "https://korumali-site.example/dosya.zip", filename: "dosya.zip", mime: "application/zip" });
await sleep(50);
result.refused = { turbodm_e_soruldu: added() === 1,
                   tarayicida_yeniden: calls.download.includes("https://korumali-site.example/dosya.zip"),
                   yeniden_yakalanmadi: added() === 1, pencere_acildi: calls.ui.includes(true) };

// 6) TurboDM kabul etti ama indirme hiç başlayamadı (sunucu 403): eklenti bunu öğrenip indirmeyi tarayıcıda
//    yeniden başlatır ve TurboDM'e bildirir (TurboDM başarısız kaydı kaldırır)
calls.fetch.length = 0;
calls.bodies.length = 0;
calls.download.length = 0;
const realUUID = crypto.randomUUID.bind(crypto);
crypto.randomUUID = () => "devir-403";
handoffState["devir-403"] = "pending";
await fire("created", { id: 6, url: "https://depo.example/tek-kullanimlik.bin", finalUrl: "https://depo.example/tek-kullanimlik.bin", filename: "a.bin", mime: "" });
await sleep(1700);
const beklerken = calls.download.length;  // TurboDM henüz karar vermedi: tarayıcıda başlatılmaz
handoffState["devir-403"] = "failed";
await sleep(1700);
crypto.randomUUID = realUUID;
result.handoff_failed = { beklerken_baslatilmadi: beklerken === 0,
                          tarayicida_yeniden: calls.download.includes("https://depo.example/tek-kullanimlik.bin"),
                          turbodm_e_bildirildi: calls.bodies.some((b) => b.includes('"returned":true')),
                          yeniden_yakalanmadi: added() === 1 };

console.log(JSON.stringify(result, null, 1));
Deno.exit(0);

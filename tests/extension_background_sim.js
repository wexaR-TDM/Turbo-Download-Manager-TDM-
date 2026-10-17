// background.js'i sahte tarayıcı ortamında çalıştırır: form (POST) indirmesi ile normal indirmeyi dener.
const src = Deno.readTextFileSync(Deno.args[0]);
const listeners = {};
const ev = (name) => ({ addListener: (fn) => { (listeners[name] ||= []).push(fn); } });
const calls = { fetch: [], pause: [], cancel: [], native: [], resume: [], erase: [] };
let appOnline = true;  // TurboDM açık mı (kapalıyken fetch bağlantı hatası verir)
globalThis.chrome = {
  storage: { local: { get: (d, cb) => cb(d) }, onChanged: ev("storage") },
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
  },
};
globalThis.fetch = async (url, opt) => {
  if (!appOnline) throw new TypeError("Failed to fetch");
  calls.fetch.push(url);
  // TurboDM dosyaya ulaşamıyor (ör. Cloudflare): köprü {ok:false} döner
  const refused = opt && opt.body && String(opt.body).includes("korumali-site");
  return { ok: true, status: 200, json: async () => (refused ? { ok: false, reason: "bot koruması" } : { ok: true }) };
};
new Function(src)();

const fire = async (name, arg) => { for (const fn of listeners[name] || []) await fn(arg); };
const result = {};

// 1) Altyazı sitesi: form POST ile /ind isteği, ardından aynı adresten indirme başlar
await fire("beforeRequest", { method: "POST", url: "https://turkcealtyazi.org/ind", type: "main_frame", tabId: 1 });
await fire("created", { id: 1, url: "https://turkcealtyazi.org/ind", finalUrl: "https://turkcealtyazi.org/ind", filename: "", mime: "" });
result.form_post = { turbodm_e_gitti: calls.fetch.some((u) => String(u).includes("/add")), duraklatildi: calls.pause.includes(1) };

// 2) Normal indirme (GET): TurboDM'e gitmeli
calls.fetch.length = 0;
await fire("beforeRequest", { method: "GET", url: "https://example.com/dosya.zip", type: "main_frame", tabId: 1 });
await fire("created", { id: 2, url: "https://example.com/dosya.zip", finalUrl: "https://example.com/dosya.zip", filename: "dosya.zip", mime: "application/zip" });
result.normal_get = { turbodm_e_gitti: calls.fetch.some((u) => String(u).includes("/add")), tarayicida_iptal: calls.cancel.includes(2) };

// 3) TurboDM kapalı: eklenti onu açtırır (native messaging), açılınca indirmeyi aktarır
calls.fetch.length = 0;
appOnline = false;
await fire("created", { id: 3, url: "https://example.com/buyuk.iso", finalUrl: "https://example.com/buyuk.iso", filename: "buyuk.iso", mime: "" });
result.app_closed = { acildi: calls.native.length === 1 && calls.native[0][1] === "launch",
                      turbodm_e_gitti: calls.fetch.some((u) => String(u).includes("/add")),
                      tarayicida_iptal: calls.cancel.includes(3) };

// 5) Form + yönlendirme (metin2.download): doğrulama kodlu form /get/… adresine gider, site imzalı depolama
//    bağlantısına yönlendirir. Son adres düz bir indirme: TurboDM'e verilmeli (son adresle)
calls.fetch.length = 0;
const bodies = [];
const realFetch = globalThis.fetch;
globalThis.fetch = async (url, opt) => { if (opt && opt.body) bodies.push(String(opt.body)); return realFetch(url, opt); };
await fire("beforeRequest", { method: "POST", url: "https://site.example/get/TOKEN/", type: "main_frame", tabId: 1 });
await fire("created", { id: 5, url: "https://site.example/get/TOKEN/", finalUrl: "https://depo.example/files/TOKEN.zip?X-Amz-Signature=abc",
                        filename: "Paket.zip", mime: "application/zip" });
globalThis.fetch = realFetch;
result.post_redirect = { turbodm_e_gitti: calls.fetch.some((u) => String(u).includes("/add")),
                         son_adresle: bodies.some((b) => b.includes("depo.example/files/TOKEN.zip")),
                         tarayicida_iptal: calls.cancel.includes(5) };

// 4) TurboDM dosyaya ulaşamıyor (bot koruması): indirme tarayıcıda sürmeli, iptal edilip silinmemeli
calls.fetch.length = 0;
await fire("created", { id: 4, url: "https://korumali-site.example/dosya.zip", finalUrl: "https://korumali-site.example/dosya.zip", filename: "dosya.zip", mime: "application/zip" });
result.refused = { turbodm_e_soruldu: calls.fetch.some((u) => String(u).includes("/add")),
                   tarayicida_iptal: calls.cancel.includes(4), listeden_silindi: calls.erase.includes(4),
                   tarayicida_surdu: calls.resume.includes(4) };

console.log(JSON.stringify(result, null, 1));

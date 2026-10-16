// background.js'i sahte tarayıcı ortamında çalıştırır: form (POST) indirmesi ile normal indirmeyi dener.
const src = Deno.readTextFileSync(Deno.args[0]);
const listeners = {};
const ev = (name) => ({ addListener: (fn) => { (listeners[name] ||= []).push(fn); } });
const calls = { fetch: [], pause: [], cancel: [] };
globalThis.chrome = {
  storage: { local: { get: (d, cb) => cb(d) }, onChanged: ev("storage") },
  runtime: { onMessage: ev("msg"), onInstalled: ev("installed"), getManifest: () => ({ version: "x" }) },
  i18n: { getMessage: (k) => k },
  contextMenus: { create() {}, onClicked: ev("ctx") },
  tabs: { onUpdated: ev("tabUpd"), onRemoved: ev("tabRem"), sendMessage: () => Promise.resolve() },
  action: { setBadgeText: () => Promise.resolve(), setBadgeBackgroundColor: () => Promise.resolve() },
  cookies: { getAll: async () => [] },
  webRequest: { onBeforeRequest: ev("beforeRequest"), onHeadersReceived: ev("headers"),
                onBeforeSendHeaders: ev("sendHeaders"), onSendHeaders: ev("sendHeaders2") },
  downloads: {
    onCreated: ev("created"), onChanged: ev("changed"), onDeterminingFilename: ev("filename"),
    pause: async (id) => calls.pause.push(id), resume: async () => {}, cancel: async (id) => calls.cancel.push(id),
    erase: async () => {}, search: async () => [],
  },
};
globalThis.fetch = async (url, opt) => { calls.fetch.push(url); return { ok: true, status: 200, json: async () => ({ ok: true }) }; };
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

console.log(JSON.stringify(result, null, 1));

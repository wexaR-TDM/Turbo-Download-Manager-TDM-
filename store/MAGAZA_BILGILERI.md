# Edge Add-ons mağazası — form alanları

Tüm dosyalar: proje klasöründe `store\cikti\`
(Yeniden üretmek için: `python store\make_store_assets.py`)

Partner Center → **Edge** → **Create new extension**

---

## 1) Packages (Paket)
Yükle: **`TurboDM-Eklenti-1.4.1.zip`** → yüklenince **Continue**.

## 2) Availability (Erişilebilirlik)
- **Visibility:** Public
- **Markets:** tümü seçili kalsın

## 3) Properties (Özellikler)
- **Category:** Productivity
- **Privacy policy requirements:** Yes (kişisel veri işliyor: çerezler)
- **Privacy policy URL:** `https://github.com/wexaR-TDM/TurboDM/blob/main/PRIVACY.md`
- **Website URL:** `https://github.com/wexaR-TDM/TurboDM`
- **Support contact details:** `https://github.com/wexaR-TDM/TurboDM/issues`
- **Mature content:** No

## 4) Store listings (Mağaza sayfası)
Dil olarak **Turkish** ekleyin (isterseniz **English** de, metinleri aşağıda).

- **Store logo:** `logo_300.png`
- **Small promotional tile (440x280):** `tanitim_440x280.png`
- **Screenshots:** `ekran_1_video.png`, `ekran_2_eklenti.png`, `ekran_3_uygulama.png`
- **YouTube video URL / Large promotional tile:** boş

**Short description (Kısa açıklama):**
> Tarayıcıdaki indirmeleri ve sayfalardaki videoları TurboDM indirme yöneticisine gönderir.

**Description (Açıklama):**
> TurboDM Entegrasyonu, bilgisayarınıza kurulu TurboDM indirme yöneticisini tarayıcıya bağlar.
>
> • İndirme yakalama: Tarayıcıda başlattığınız indirmeler otomatik olarak TurboDM'e gider ve çok bağlantıyla, kaldığı yerden devam ettirilebilir şekilde iner.
> • Video yakalayıcı: Sayfadaki videonun üstünde "Bu videoyu indir" düğmesi görünür. Tıklayınca TurboDM'in bulduğu kaliteler ve sayfanın yüklediği video/ses akışları listelenir.
> • Sağ tık menüsü: Bağlantılar, resimler ve videolar için "TurboDM ile indir".
> • Eklenti penceresi: Bu sayfadaki medyaları görün, indirme yakalamayı tek tıkla açıp kapatın.
>
> Gereksinim: TurboDM masaüstü uygulaması (Windows 10/11, ücretsiz):
> https://github.com/wexaR-TDM/TurboDM/releases/latest
>
> Gizlilik: Eklenti verileri yalnızca kendi bilgisayarınızdaki TurboDM uygulamasına (127.0.0.1) iletir; geliştiriciye ya da üçüncü taraflara hiçbir veri gönderilmez, izleme veya reklam yoktur.
>
> Telif hakkı korumalı içerikleri yalnızca hak sahibinin izin verdiği ölçüde indirin.

**English — Short description:**
> Sends browser downloads and on-page videos to the TurboDM download manager.

**English — Description:**
> TurboDM Integration connects your browser to the TurboDM download manager installed on your computer.
>
> • Download capture: downloads you start in the browser are handed to TurboDM and downloaded with multiple connections and resume support.
> • Video grabber: a "Download this video" button appears over videos on web pages. Clicking it lists the qualities found by TurboDM and the video/audio streams loaded by the page.
> • Context menu: "Download with TurboDM" for links, images and videos.
> • Popup: see the media on the current page and toggle download capture with one click.
>
> Requires the TurboDM desktop application (Windows 10/11, free):
> https://github.com/wexaR-TDM/TurboDM/releases/latest
>
> Privacy: the extension only talks to the TurboDM application on your own computer (127.0.0.1); no data is sent to the developer or any third party, and there is no tracking or advertising.
>
> Please download copyrighted content only as permitted by the rights holder.

**Search terms (Anahtar kelimeler):** `indirme yöneticisi`, `download manager`, `TurboDM`, `video indir`, `hızlandırıcı`

## 5) Submit → "Notes for certification" (İnceleme ekibine not)
> This extension is the browser bridge for the TurboDM desktop download manager (Windows). To test it, install TurboDM from https://github.com/wexaR-TDM/TurboDM/releases/latest , start it, then start any file download in Edge: the download is handed to TurboDM. On a page with a video, the "Download this video" button lists available qualities via the desktop application.
>
> Permission justifications:
> - downloads: intercept downloads started in the browser and hand them to the desktop app (the user can switch this off in the popup).
> - cookies: forward the site's cookies for the download URL to the local app, so downloads that require sign-in work.
> - webRequest + host permissions (<all_urls>): detect video/audio streams loaded by pages (response headers only) to list them in the video grabber; downloads can come from any site.
> - contextMenus: "Download with TurboDM" in the right-click menu.
> - tabs: read the active tab's URL/title for the popup and the page video button.
> - storage: remember the two on/off settings.
> All communication goes only to http://127.0.0.1:9614 (the TurboDM app on the user's computer). No data is sent to any remote server.

Sonra **Publish**. İnceleme genelde birkaç gün sürer; sonuç e-postayla gelir.

## Onaylandıktan sonra
Mağazadaki eklentinin **Extension ID**'sini bana bildirin: kurulum programına eklenir, TurboDM kurulunca
Edge eklentiyi kendisi önerir ve güncellemeler mağazadan otomatik gelir.

# Edge Add-ons mağazası — form alanları

Tüm dosyalar: proje klasöründe `store\cikti\`
(Yeniden üretmek için: `python store\make_store_assets.py`)

Partner Center → **Edge** → **Create new extension**

---

## 1) Packages (Paket)
Yükle: **`TurboDM-Eklenti-<sürüm>.zip`** (`store\cikti\` içindeki en yeni paket; sürüm `browser_extension\manifest.json`'dan) → yüklenince **Continue**.
Mağazada yayımlanan eklentiyi güncellemek için: Partner Center → eklenti → **Update** → yeni paket → Publish.

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
Paket 7 dil içerdiği için (`browser_extension\_locales`) mağaza **7 dilin her biri** için açıklama ve logo ister;
biri eksik kalırsa Submit "Store listing page" hatası verir. Her dilde **Edit details** →

- **Extension name:** paketten gelir (`extName`), değiştirilemez
- **Description:** aşağıdaki metnin tamamı (en az 250 karakter; formda ayrı "Short description" alanı yok)
- **Extension logo:** `logo_300.png`
- **Small promotional tile:** `tanitim_440x280.png`
- **Screenshot/s:** `ekran_1_video.png`, `ekran_2_eklenti.png`, `ekran_3_uygulama.png`
- **Large promotional tile:** `tanitim_buyuk_1400x560.png`
- **YouTube video URL:** boş
- **Search terms:** her terim ayrı kutuya (**Add Term**); en fazla 7 terim, her biri ≤ 30 karakter, toplam ≤ 21 kelime
- **Generate with AI** kullanılmaz; düğme/menü adları eklentinin kendi çevirileriyle aynı olmalı

### Turkish (Türkçe)
**Search terms:** `indirme yöneticisi` · `TurboDM` · `video indir` · `indirme hızlandırıcı` · `IDM alternatifi`

**Description:**
```
TurboDM Entegrasyonu, bilgisayarınıza kurulu TurboDM indirme yöneticisini tarayıcıya bağlar.

• İndirme yakalama: Tarayıcıda başlattığınız indirmeler otomatik olarak TurboDM'e gider ve çok bağlantıyla, kaldığı yerden devam ettirilebilir şekilde iner.
• Video yakalayıcı: Sayfadaki videonun üstünde "Bu videoyu indir" düğmesi görünür. Tıklayınca TurboDM'in bulduğu kaliteler ve sayfanın yüklediği video/ses akışları listelenir.
• Sağ tık menüsü: Bağlantılar, resimler ve videolar için "TurboDM ile indir".
• Eklenti penceresi: Bu sayfadaki medyaları görün, indirme yakalamayı tek tıkla açıp kapatın.

Gereksinim: TurboDM masaüstü uygulaması (Windows 10/11, ücretsiz):
https://github.com/wexaR-TDM/TurboDM/releases/latest

Gizlilik: Eklenti verileri yalnızca kendi bilgisayarınızdaki TurboDM uygulamasına (127.0.0.1) iletir; geliştiriciye ya da üçüncü taraflara hiçbir veri gönderilmez, izleme veya reklam yoktur.

Telif hakkı korumalı içerikleri yalnızca hak sahibinin izin verdiği ölçüde indirin.
```

### English
**Search terms:** `download manager` · `TurboDM` · `video downloader` · `download accelerator` · `IDM alternative`

**Description:**
```
TurboDM Integration connects your browser to the TurboDM download manager installed on your computer.

• Download capture: downloads you start in the browser are handed to TurboDM and downloaded with multiple connections and resume support.
• Video grabber: a "Download this video" button appears over videos on web pages. Clicking it lists the qualities found by TurboDM and the video/audio streams loaded by the page.
• Context menu: "Download with TurboDM" for links, images and videos.
• Popup: see the media on the current page and toggle download capture with one click.

Requires the TurboDM desktop application (Windows 10/11, free):
https://github.com/wexaR-TDM/TurboDM/releases/latest

Privacy: the extension only talks to the TurboDM application on your own computer (127.0.0.1); no data is sent to the developer or any third party, and there is no tracking or advertising.

Please download copyrighted content only as permitted by the rights holder.
```

### German (Deutsch)
**Search terms:** `Download-Manager` · `TurboDM` · `Video herunterladen` · `Download-Beschleuniger` · `IDM Alternative`

**Description:**
```
TurboDM-Integration verbindet Ihren Browser mit dem auf Ihrem Computer installierten Download-Manager TurboDM.

• Download-Übernahme: Downloads, die Sie im Browser starten, werden an TurboDM übergeben und mit mehreren Verbindungen und Fortsetzungsfunktion heruntergeladen.
• Video-Grabber: Über Videos auf Webseiten erscheint die Schaltfläche „Dieses Video herunterladen“. Ein Klick listet die von TurboDM gefundenen Qualitäten und die von der Seite geladenen Video-/Audiostreams auf.
• Kontextmenü: „Mit TurboDM herunterladen“ für Links, Bilder und Videos.
• Popup: Medien der aktuellen Seite anzeigen und die Download-Übernahme mit einem Klick ein- oder ausschalten.

Erfordert die Desktop-Anwendung TurboDM (Windows 10/11, kostenlos):
https://github.com/wexaR-TDM/TurboDM/releases/latest

Datenschutz: Die Erweiterung kommuniziert nur mit der TurboDM-Anwendung auf Ihrem eigenen Computer (127.0.0.1); es werden keine Daten an den Entwickler oder Dritte gesendet, es gibt kein Tracking und keine Werbung.

Bitte laden Sie urheberrechtlich geschützte Inhalte nur herunter, soweit der Rechteinhaber dies erlaubt.
```

### French (Français)
**Search terms:** `gestionnaire de téléchargement` · `TurboDM` · `télécharger vidéo` · `accélérateur` · `alternative IDM`

**Description:**
```
Intégration TurboDM relie votre navigateur au gestionnaire de téléchargement TurboDM installé sur votre ordinateur.

• Capture des téléchargements : les téléchargements lancés dans le navigateur sont transmis à TurboDM et téléchargés avec plusieurs connexions et reprise possible.
• Capteur de vidéos : un bouton « Télécharger cette vidéo » apparaît sur les vidéos des pages web. Un clic affiche les qualités trouvées par TurboDM et les flux vidéo/audio chargés par la page.
• Menu contextuel : « Télécharger avec TurboDM » pour les liens, les images et les vidéos.
• Fenêtre de l'extension : voyez les médias de la page en cours et activez ou désactivez la capture des téléchargements d'un clic.

Nécessite l'application de bureau TurboDM (Windows 10/11, gratuite) :
https://github.com/wexaR-TDM/TurboDM/releases/latest

Confidentialité : l'extension communique uniquement avec l'application TurboDM sur votre propre ordinateur (127.0.0.1) ; aucune donnée n'est envoyée au développeur ni à des tiers, sans suivi ni publicité.

Ne téléchargez les contenus protégés par le droit d'auteur que dans la mesure autorisée par le titulaire des droits.
```

### Spanish (Español)
**Search terms:** `gestor de descargas` · `TurboDM` · `descargar vídeos` · `acelerador de descargas` · `alternativa IDM`

**Description:**
```
Integración de TurboDM conecta su navegador con el gestor de descargas TurboDM instalado en su equipo.

• Captura de descargas: las descargas que inicia en el navegador pasan a TurboDM y se descargan con varias conexiones y posibilidad de reanudar.
• Capturador de vídeos: sobre los vídeos de las páginas web aparece el botón «Descargar este vídeo». Al pulsarlo se muestran las calidades encontradas por TurboDM y las secuencias de vídeo/audio cargadas por la página.
• Menú contextual: «Descargar con TurboDM» para enlaces, imágenes y vídeos.
• Ventana de la extensión: vea los medios de la página actual y active o desactive la captura de descargas con un clic.

Requiere la aplicación de escritorio TurboDM (Windows 10/11, gratuita):
https://github.com/wexaR-TDM/TurboDM/releases/latest

Privacidad: la extensión solo se comunica con la aplicación TurboDM de su propio equipo (127.0.0.1); no se envía ningún dato al desarrollador ni a terceros, y no hay seguimiento ni publicidad.

Descargue contenido protegido por derechos de autor solo en la medida en que lo permita el titular de los derechos.
```

### Italian (Italiano)
**Search terms:** `gestore di download` · `TurboDM` · `scaricare video` · `acceleratore download` · `alternativa IDM`

**Description:**
```
Integrazione TurboDM collega il browser al gestore di download TurboDM installato sul tuo computer.

• Cattura dei download: i download avviati nel browser vengono passati a TurboDM e scaricati con più connessioni e possibilità di ripresa.
• Cattura video: sopra i video delle pagine web compare il pulsante «Scarica questo video». Facendo clic vengono elencate le qualità trovate da TurboDM e i flussi video/audio caricati dalla pagina.
• Menu contestuale: «Scarica con TurboDM» per link, immagini e video.
• Finestra dell'estensione: visualizza i contenuti multimediali della pagina corrente e attiva o disattiva la cattura dei download con un clic.

Richiede l'applicazione desktop TurboDM (Windows 10/11, gratuita):
https://github.com/wexaR-TDM/TurboDM/releases/latest

Privacy: l'estensione comunica solo con l'applicazione TurboDM sul tuo computer (127.0.0.1); nessun dato viene inviato allo sviluppatore o a terzi, senza tracciamento né pubblicità.

Scarica i contenuti protetti da copyright solo nella misura consentita dal titolare dei diritti.
```

### Arabic (العربية)
**Search terms:** `مدير التنزيل` · `TurboDM` · `تنزيل الفيديو` · `تسريع التنزيل` · `بديل IDM`

**Description:**
```
يربط تكامل TurboDM متصفحك ببرنامج إدارة التنزيل TurboDM المثبّت على جهازك.

• التقاط التنزيلات: تنتقل التنزيلات التي تبدأها في المتصفح إلى TurboDM، فتُنزَّل عبر اتصالات متعددة مع إمكانية الاستئناف.
• التقاط الفيديو: يظهر زر "تنزيل هذا الفيديو" فوق مقاطع الفيديو في صفحات الويب. عند النقر عليه تظهر الجودات التي وجدها TurboDM ومسارات الفيديو والصوت التي حمّلتها الصفحة.
• قائمة النقر بزر الماوس الأيمن: "التنزيل باستخدام TurboDM" للروابط والصور ومقاطع الفيديو.
• نافذة الإضافة: اعرض الوسائط الموجودة في الصفحة الحالية، وشغّل التقاط التنزيلات أو أوقفه بنقرة واحدة.

يتطلب تطبيق TurboDM لسطح المكتب (Windows 10/11، مجاني):
https://github.com/wexaR-TDM/TurboDM/releases/latest

الخصوصية: لا تتواصل الإضافة إلا مع تطبيق TurboDM على جهازك (127.0.0.1)؛ لا تُرسَل أي بيانات إلى المطوّر أو إلى أي طرف ثالث، ولا يوجد تتبّع أو إعلانات.

يُرجى تنزيل المحتوى المحمي بحقوق النشر فقط بالقدر الذي يسمح به صاحب الحقوق.
```

## 5) Submit → "Notes for certification" (İnceleme ekibine not)
Soru: **Yes, I need to provide … other info for testers** (hesap gerekmez ama masaüstü uygulaması gerekir).
Not her gönderimde yeniden istenir; son satırı o sürümün değişikliğiyle güncelleyin (en fazla 2000 karakter):
```
No account, login or payment is needed. This extension is the browser companion of TurboDM, a free, open-source (GPL v3) download manager for Windows. To test it, the desktop app must be installed:

1. Download and install TurboDM: https://github.com/wexaR-TDM/TurboDM/releases/latest (TurboDM-Setup-<version>.exe). Source code: https://github.com/wexaR-TDM/TurboDM
2. Install this extension. The popup shows "✔ TurboDM is running" when the app is running.

How to test:
- Download handoff: start any file download (e.g. a .zip or .exe). The extension cancels the browser download and sends the link to TurboDM, which downloads it with multiple connections. If TurboDM cannot access the file (e.g. a login/verification page or bot protection), the download continues in the browser instead.
- Video: open a page with a video. A "Download this video" button appears over the video; it also lists qualities in the popup. The button can be hidden with the "x" on it.
- Right-click a link > "Download with TurboDM".
- Popup: on/off switches for download capture and video button.

Permissions:
- downloads, webRequest, <all_urls>: detect downloads and media streams on any site.
- cookies: pass the page's cookies to the app so downloads that require the user's session keep working.
- nativeMessaging: only to start the TurboDM app (host "com.turbodm.app") when it is closed; no other data is exchanged.
- tabs, contextMenus, storage: page info, context menu, settings.

All communication is with the local app at http://127.0.0.1:9614 on the user's own computer. No data is sent to any server; no analytics.

Changes in <version>: <bu sürümün değişikliği>
```

Sonra **Publish**. İnceleme en fazla 7 iş günü sürer; sonuç e-postayla gelir.

## Mağaza kimliği
CRX ID: `dpeakjonbfgodlhkbpeekljfgnpbbjai` (Store ID `0RDCKDDRP4HH`). Bu kimlik `turbodm\nativehost.py` içindeki `STORE_IDS`'te
kayıtlı; TurboDM'in eklentiyle native messaging üzerinden konuşmasına izin verilen mağaza eklentisi budur.

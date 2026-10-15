# TurboDM — İnternet İndirme Yöneticisi

IDM (Internet Download Manager) mantığıyla çalışan; HTTP/HTTPS, FTP, HLS video akışları ve BitTorrent destekli indirme yöneticisi.

## Kullanıcılar için: kurulum

`dist\TurboDM-Setup-1.1.0.exe` dosyasını çalıştırın. Windows 10/11 (64 bit). Python ya da başka bir
şey kurmanız gerekmez; ffmpeg dahil her şey içindedir.

* Kurulum `C:\Program Files\TurboDM` klasörüne yapılır (yönetici izni ister).
* Seçenekler: masaüstü kısayolu, magnet/.torrent ilişkilendirmesi, güvenlik duvarı izni, Windows açılışında başlatma.
* İmzasız olduğu için Windows SmartScreen "Windows bilgisayarınızı korudu" diyebilir:
  **Ek bilgi → Yine de çalıştır**.

### Kaldırma

Başlat menüsü → TurboDM → **TurboDM'i Kaldır**, ya da Ayarlar → Uygulamalar, ya da
`C:\Program Files\TurboDM\unins000.exe`. Açılan pencerede seçilir:

| Her zaman kaldırılır | Seçmeli |
|---|---|
| Program klasörü (sonradan oluşan dosyalar dahil), kısayollar, "Programlar ve Özellikler" kaydı, magnet/.torrent ilişkilendirmesi, Windows açılışında başlatma, güvenlik duvarı kuralı | ☑ Ayarlar, indirme listesi, torrent devam verileri (`%APPDATA%\TurboDM`) — varsayılan açık |
| | ☑ Yarım kalmış indirmeler (.tdm, .tdm_parts, bitmemiş torrent dosyaları) — varsayılan açık |
| | ☐ Tamamlanmış indirilen dosyalar (yalnızca TurboDM listesindekiler) — varsayılan kapalı |

TurboDM'in listesinde olmayan hiçbir dosyaya ve TurboDM'in açmadığı hiçbir klasöre dokunulmaz.
Kaldırma sırasında program açıksa önce düzgünce kapatılır. Sessiz kaldırma: `unins000.exe /VERYSILENT`
(ayarlar ve yarım kalanlar silinir, indirilenler kalır).

Tarayıcı eklentisi tarayıcının kendi listesinde durduğu için onu tarayıcının eklentiler sayfasından kaldırın.

Sorun tespiti: `"C:\Program Files\TurboDM\TurboDM.exe" --selftest %USERPROFILE%\Desktop\turbodm-test.json`
arayüz, torrent, şifre çözme, ffmpeg, HTTPS ve indirme motorunu dener; sonuç dosyasında `"hepsi_tamam": true` olmalıdır.

## Site videoları

Tarayıcı eklentisi kuruluysa sayfadaki ana videonun sağ üstünde **"⬇ Bu videoyu indir"** düğmesi çıkar
(eklenti simgesinden de olur). TurboDM kalite listesini getirir; görüntü ve ses ffmpeg ile tek .mp4'te
birleşir. Video sayfasının adresini "URL Ekle"ye yapıştırmak da çalışır.

Altyapı: yt-dlp + deno (JavaScript çalıştırma ortamı, dosya/ağ erişimi kapalı), programla gelir.
Siteler değişiklik yaptığında **Yardım → Güncellemeleri denetle → Video motorunu güncelle**
(yt-dlp, `%LOCALAPPDATA%\TurboDM\tools` altına SHA-256 doğrulamasıyla indirilir; yönetici izni gerekmez).

Gizlilik: eklentinin gönderdiği oturum çerezleri diske kaydedilmez; yalnızca indirme sırasında geçici
bir dosyayla yt-dlp'ye verilir ve hemen silinir.

## Güncellemeler (Yardım → Güncellemeleri denetle)

Program `https://github.com/<UPDATE_REPO>/releases/latest/download/latest.json` dosyasını okur, yeni sürüm
varsa notlarını gösterir; **İndir ve Kur** kurulum dosyasını indirir, SHA-256 ile doğrular ve çalıştırır
(kurulum, açık TurboDM'i kapatıp güncelleme modunda kurar). Açılışta günde bir kez sessizce denetler
(Seçenekler → Genel'den kapatılabilir).

### Yeni sürüm yayımlama

1. `turbodm\appinfo.py` → `VERSION` artırın (ör. `1.2.0`). İlk seferde `UPDATE_REPO = "kullanici/depo"` yazın.
2. `SURUM_NOTLARI.md` en üstüne `## 1.2.0` bölümünü ekleyin.
3. `powershell -ExecutionPolicy Bypass -File build.ps1` → `dist\TurboDM-Setup-1.2.0.exe` + `dist\latest.json`
4. Yayımlayın:
   * GitHub CLI ile: `powershell -ExecutionPolicy Bypass -File publish.ps1`
   * ya da elle: GitHub → Releases → *Draft a new release* → etiket `v1.2.0` → iki dosyayı da yükleyin →
     *Set as the latest release* → Publish.

Depo herkese açık (public) olmalıdır; aksi hâlde kullanıcıların programı dosyaları indiremez.

## Testler

Her sürümden önce (yalnızca yerel sunucularla çalışır, internete çıkmaz):

```n powershell -ExecutionPolicy Bypass -File tests\run_tests.ps1 -Installer
```

* `tests\test_turbodm.py`: çok bağlantılı indirme, devam, Range'siz/boyutsuz/boş dosya, bağlantı kopması, 404, yarım gövde, istek boyu sınırı, hız sınırları, yönlendirme ve süresi dolan imzalı adres, disk dolu/izin hataları, dosya adı kuralları, YouTube hızlı mod (birleştirme, devam, adres yenileme, sahipsiz bağlantı, önbellek), HLS (AES, ayrı ses, canlı yayın), FTP, kuyruk, bozuk liste kurtarma, köprü güvenliği, tek kopya, kaldırma temizliği
* `tests\test_gui.py`: pencereler, tamamlandı/hata pencereleri, bitince kapat geri sayımı, güncelleme denetimi, tarayıcı menüsü akışı, magnet + dosya seçimi
* `-Installer`: kurulum dosyasını kurar, öz-testini çalıştırır, program açıkken kaldırır ve iz kalmadığını denetler

## Geliştiriciler için

```
pip install -r requirements.txt
python main.py
```

Kurulum dosyasını yeniden üretmek (gerekenler: `pip install pyinstaller`, Inno Setup 6, `vendor\ffmpeg\ffmpeg.exe`;
yt-dlp ve deno için bir kez `powershell -ExecutionPolicy Bypass -File installer\fetch_tools.ps1`):

```
powershell -ExecutionPolicy Bypass -File build.ps1
```

Adımlar: simge → PyInstaller (`installer\TurboDM.spec`, klasör düzeni) → kurulum düzeni → Inno Setup
(`installer\TurboDM.iss`) → `dist\TurboDM-Setup-<sürüm>.exe`. Proje çok derin bir klasördeyse Inno Setup'ın
260 karakter yol sınırı yüzünden kurulum düzeni `%LOCALAPPDATA%\TurboDM-build` altında hazırlanır.

Komut satırı: `TurboDM.exe <url | magnet | dosya.torrent>` (program açıksa isteği ona iletir), `--tray` (tepside
gizli başlar), `--quit`, `--register-assoc`, `--autostart on|off`, `--cleanup [--partials] [--downloads] [--appdata]`,
`--selftest <rapor.json>`.

## Özellikler

| Özellik | Açıklama | Dosya |
|---|---|---|
| Ön sorgu | 1 baytlık `Range` isteğiyle boyut, devam desteği, dosya adı öğrenilir | `engine.py` → `probe` |
| Çok bağlantı | Dosya N parçaya bölünür, her parça ayrı bağlantıyla aynı dosyaya yazılır | `HttpTask` |
| **Dinamik segmentasyon** | Parçasını bitiren bağlantı, kalan en büyük parçayı ikiye bölüp ikinci yarısını devralır | `_next_segment` |
| Devam ettirme | Her parçanın `[başlangıç, bitiş, konum]` bilgisi kaydedilir; program kapansa bile kaldığı yerden sürer | `downloads.json` |
| FTP | Aynı çok bağlantılı motor; `REST` ile parça/devam, kullanıcı adı-şifre URL'de (`ftp://ad:şifre@sunucu/yol`) | `engine.py` → `_FtpResponse` |
| HLS (m3u8) | Kalite seçimi, AES-128 şifre çözme, fMP4, ayrı ses kanalı, paralel parça indirme, devam, ffmpeg ile .mp4 | `hls.py` |
| Hata toleransı | Kopan bağlantı artan beklemeyle 8 kez yeniden dener | `_download_segment` |
| Hız sınırı | Tüm indirmeler tek bir jeton kovasını paylaşır | `SpeedLimiter` |
| Kategoriler | Uzantıya göre Video/Müzik/Belgeler/… klasörlerine kaydeder | `manager.py` |
| Kuyruk + zamanlayıcı | "Sonra İndir" kuyruğa ekler; aynı anda N indirme; belirli saatte başlat/durdur | `Manager._tick_queue` |
| Pano takibi | Kopyalanan indirilebilir linkler, m3u8 ve magnetler otomatik yakalanır | `gui.py` |
| Adres yenileme | Süresi dolan linke yeni adres verip kaldığı yerden devam | sağ tık menüsü |
| Torrent | Magnet ve .torrent, DHT/LSD/UPnP, devam verisi, isteğe bağlı seed | `torrent.py` |
| Torrent dosya seçimi | Eklerken klasör ağacından dosya seç; magnet'te önce dosya listesi alınır (hiçbir şey inmeden). İndirme sürerken de değiştirilebilir | `TorrentAddDialog` |
| Windows entegrasyonu | magnet: ve .torrent → TurboDM; Windows açılışında başlatma | `winassoc.py`, Seçenekler |

Ayarlar ve liste: `%APPDATA%\TurboDM\`. İndirmeler: `İndirilenler\TurboDM\<Kategori>\`.

## Tarayıcı eklentisi (Chrome / Edge / Brave)

1. `chrome://extensions` → **Geliştirici modu** açık
2. **Paketlenmemiş öğe yükle** → `browser_extension` klasörünü seç

Ne yapar:
* Tarayıcıda başlayan indirmeleri TurboDM'e yönlendirir (TurboDM kapalıysa tarayıcı normal indirir).
* **Video yakalayıcı:** sayfanın yüklediği video/ses akışlarını (mp4, webm, m3u8…) algılar; videonun
  üstünde "⬇ Bu videoyu indir" düğmesi çıkar, tıklayınca kalite/dosya listesi açılır. Eklenti simgesindeki
  sayı bulunan medya sayısıdır; listeye simgeden de ulaşılır.
* Linklere/videolara sağ tık → "TurboDM ile indir".

## Windows'ta magnet bağlantıları

Seçenekler → Torrent → **"Magnet ve .torrent'i TurboDM ile aç"**. Başka bir torrent programı (ör. qBittorrent)
Windows'ta varsayılan olarak seçilmişse Windows buna izin vermez; o zaman **"Varsayılan uygulamalar…"**
düğmesiyle açılan ekranda magnet için TurboDM'i seçin.

## Sınırlar

* DRM'li videolar (Netflix, Disney+, SAMPLE-AES/Widevine) indirilemez; canlı yayınlar desteklenmez.
* DASH (.mpd) akışları desteklenmez.
* Eklentinin gönderdiği çerezler (oturum gerektiren indirmeler için) `%APPDATA%\TurboDM\downloads.json` içinde düz metin saklanır.

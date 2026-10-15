# TurboDM sürüm notları

Her yeni sürümde en üste bir bölüm ekleyin. "Güncellemeleri denetle" penceresinde kullanıcıya
o sürümün bölümü gösterilir (build.ps1 otomatik olarak latest.json'a koyar).

## 1.6.1
• İndirme pencereleri ana pencereden bağımsız: ana pencere simge durumuna küçültülünce onlar açık kalır

## 1.6.0
• Biçim seçimi: indirme penceresinde "Biçim" — MP4 (olduğu gibi), MKV (kayıpsız, hızlı), AVI (eski TV/oynatıcılar için), MP3 (yalnızca ses); dönüştürme indirme bitince yapılır
• DASH (.mpd) video akışları desteklenir
• Gömülü oynatıcılar: video, oynatıcının kendi sayfa adresi ve kökeniyle istenir (403 hatası veren sunucular için)
• Tarayıcı eklentisi 1.4.4: DASH akışlarını ve gömülü oynatıcıların adresini yakalar

## 1.5.8
• Proje deposunun yeni adresi: github.com/wexaR-TDM/TurboDM (eski adres yönlendirir; güncellemeler kesintisiz)
• Lisans: kurulumla gelen ffmpeg'in birebir kaynak kodu her sürüm sayfasında yayımlanır; kaynak bilgisi ffmpeg klasöründe
• Tarayıcı eklentisi 1.4.3: proje sayfası bağlantısı güncellendi

## 1.5.7
• Güvenlik: güncellemeler artık dijital imzalı. TurboDM yalnızca geliştiricinin imzaladığı güncellemeyi kurar; sahte güncelleme dağıtılamaz
• Güvenlik: güncelleme yalnızca resmi GitHub sürüm sayfasından indirilir

## 1.5.6
• Yeni açılan pencereler (indirme penceresi, seçenekler, uyarılar) ekranın tam ortasında açılır

## 1.5.5
• Sunucu bağlantı sınırı sabit kalmaz: indirme sorunsuz sürerken ~20 sn'de bir yeni bağlantı denenir; sunucu izin verirse hız artar ve yeni sınır kaydedilir

## 1.5.4
• Sunucu bağlantı sınırı (IDM gibi): sunucu az bağlantıya izin veriyorsa (ör. gofile) fazla bağlantılar indirmeyi bozmadan çekilir; indirme çalışan bağlantılarla sürer, hız dalgalanması azalır
• Tek bir bağlantının tekrar tekrar hata vermesi artık tüm indirmeyi durdurmaz; yalnızca hiçbir bağlantı çalışmıyorsa hata verilir
• Öğrenilen sınır kaydedilir: devam ettirince sunucunun izin verdiği kadar bağlantı açılır; indirme penceresinde gösterilir
• Bağlantı listesinde hatanın gerçek nedeni yazılır; sunucu "Retry-After" bildirirse ona uyulur

## 1.5.3
• Hakkında penceresi sadeleşti; video bileşeni her yerde "Video motoru" olarak anılır

## 1.5.2
• Yeni TurboDM teması: Windows'un açık/koyu moduna kendiliğinden uyar; Windows'ta mod değişince program açıkken de anında geçer
• TurboDM'e özel çizgi simgeler, logo ve adla araç çubuğu, sayılı kategori menüsü
• Listede "Durum" sütununda ince ilerleme çizgisi; tamamlananlar yeşil, hatalılar kırmızı
• Pencere başlıkları temanın rengini alır (Windows 11)
• Seçenekler → Genel → Tema: Windows ile aynı / Açık / Koyu

## 1.5.1
• Toplu işlem: listenin başında onay kutuları; kutuya tıklayınca satır diğer seçimler bozulmadan seçime eklenir
• Başlıktaki kutu ile tümünü seç / seçimi kaldır; Ctrl+A ve Esc kısayolları
• "Toplu seçim" menüsü: bitmemişleri, bitenleri, durdurulanları, hatalıları seç
• Sağ tık menüsü birden çok indirmede hepsine uygulanır (devam, durdur, kuyruk, adresleri kopyala, sil)
• Düzeltme: liste yenilenince çoklu seçimin yalnızca son satırı kalıyordu

## 1.5.0
• Torrent hızlandı: indirirken yükleme hızı otomatik sınırlanır (dolan yükleme hattı indirmeyi yavaşlatıyordu)
• Torrent: daha çok eşe daha hızlı bağlanma, daha derin parça isteği kuyruğu, çok çekirdekli parça doğrulama
• Torrent: şifreli bağlantı tercih edilir ve bilinen 6881 yerine rastgele port kullanılır (servis sağlayıcı yavaşlatmalarına karşı)
• Seçenekler → Torrent: "İndirirken yükleme hızını otomatik sınırla" ayarı
• Güncelleme sonrası TurboDM kendiliğinden yeniden açılır (görev çubuğunda, öne çıkmadan); inmekte olan indirmeler kaldığı yerden sürer

## 1.4.9
• Tarayıcı eklentisi 1.4.2: Türkçe ve İngilizce dil desteği (eklentinin adı ve açıklaması tarayıcının diline göre)

## 1.4.8
• Tarayıcı eklentisi 1.4.1: TurboDM simgesi (araç çubuğu ve eklentiler sayfası), mağazaya hazır paket

## 1.4.7
• Tarayıcı eklentisi 1.4.0: "Bu videoyu indir" düğmesi ve kalite menüsü artık her sitede çalışır (Vimeo, Dailymotion, X ve daha fazlası)
• Eklenti sayfadaki videoyu TurboDM'e iletir, kaliteleri TurboDM bulur; sayfanın yüklediği video akışları da aynı menüde
• Eklenti penceresinde her sayfa için "Bu sayfadaki videoyu TurboDM'de aç" düğmesi

## 1.4.6
• Güncellemeler artık GitHub üzerinden: Yardım → Güncellemeleri denetle ile yeni sürüm indirilip kurulabilir

## 1.4.5
• Güncelleme sırasında inmekte olan indirmeler, güncelleme bitince kaldığı yerden otomatik olarak sürer

## 1.4.4
• Torrent: .torrent bağlantıları artık dosya olarak kaydedilmez, doğrudan torrent olarak açılır (dosya seçimi penceresi)
• Torrent: dosyayı yalnızca tarayıcıya veren sitelerde (indirme düğmeli sayfalar) .torrent tarayıcıda iner ve otomatik olarak TurboDM'de açılır (tarayıcı eklentisi 1.3.2)
• Site torrent yerine web sayfası gönderirse .html kaydetmek yerine ne yapılacağı anlatılır
• İndirme penceresine küçült ve tam ekran düğmeleri eklendi; küçültülünce görev çubuğuna iner

## 1.4.3
• Kaldırma: kayıt defterinde boş 'Software\TurboDM' anahtarı da artık silinir (hiç iz kalmaz)

## 1.4.2
• Güvenlik: tarayıcı köprüsü yalnızca yerel adresten gelen istekleri kabul eder (DNS rebinding koruması)
• Aynı anda iki kez açılma ve köprü portunu kullanan başka bir program artık sorun çıkarmaz
• İndirme listesi bozulursa bir önceki sağlam kopyadan otomatik kurtarılır
• İndirme başlamadan disk alanı denetlenir; disk/izin hataları anlaşılır Türkçe mesajla hemen bildirilir
• Süresi dolan yönlendirme adresleri (bulut depolama, GitHub vb.) otomatik yenilenir
• Çok uzun ve Windows'ta yasak dosya adları (CON, NUL…) düzeltilir

## 1.4.1
• Büyük dosyalarda (ör. 22 GB 8K video) indirme başında yaşanan uzun bekleme giderildi: geçici dosya seyrek dosya olarak açılır
• Renkler TurboDM mavisi: Windows vurgu rengi (ör. kırmızı) artık ilerleme çubuğuna ve tablolara yansımaz
• İndirme penceresinde 'Kayıt klasörü' yalnızca klasörü gösterir; dosya adı otomatik verilir

## 1.4.0
• IDM düzeninde indirme penceresi: bağlantılar ve parçalı ilerleme çubuğu alt bölümde (Ayrıntıları gizle/göster)
• Yeni sekme 'Hız sınırlayıcı': indirmeye özel hız sınırı, indirme sürerken değiştirilebilir
• Yeni sekme 'Bitince yapılacaklar': bilgisayarı kapat / uyku / TurboDM'den çık (30 sn geri sayım, iptal edilebilir)
• Zamanlayıcı: kuyruk bitince bilgisayarı kapat / uyku / çık

## 1.3.1
• Tarayıcı menüsünde kalite seçilince kayıt yeri penceresi açılır (kalite ve uzantı seçili gelir; Sonra İndir / İndirmeyi Başlat sizde)

## 1.3.0
• YouTube'da 'Bu videoyu indir' düğmesi kalite menüsünü sayfada açar; seçilen kalite soru sorulmadan iner (IDM gibi)
• TurboDM'in pencereleri ve uyarıları (indirme, tamamlandı, hata) ekranın önüne gelir
• İndirme hatasında önde bir uyarı ve 'Tekrar Dene' düğmesi

## 1.2.0
• YouTube indirmeleri 2–3 kat hızlı: görüntü ve ses aynı anda, 24 bağlantıyla (IDM yöntemi)
• Düzeltme: başlığında ™ gibi özel karakter olan videolar "yt-dlp çıkış kodu 0" hatası veriyordu
• Akış adresinin süresi dolarsa otomatik yenilenir, indirme kaldığı yerden sürer
• Önceki sürümde hata sanılan ama aslında inmiş videolar "Devam Et" ile yeniden indirilmeden tamamlanır
• Windows bildirimlerinde program adı "TurboDM" olarak görünür
• Düzeltme: hız sınırı açıkken Duraklat'tan hemen sonra Devam Et dosyayı bozabiliyordu
• Düzeltme: bağlantısı erken kopan tek parçalı indirmeler yarım hâliyle "tamamlandı" sayılıyordu

## 1.1.0
• YouTube ve diğer sitelerden video indirme (1080p/4K, yalnızca ses) — tarayıcıda videonun üstündeki düğmeyle
• Yardım → Güncellemeleri denetle: TurboDM ve YouTube motoru tek pencereden güncellenir
• TurboDM temalı yeni kurulum sihirbazı; kurulu sürüm kontrolü ve güncelleme modu
• Kaldırma seçenekleri: ayarlar, yarım kalanlar ve indirilen dosyalar ayrı ayrı seçilebilir

## 1.0.0
• İlk sürüm: çok bağlantılı indirme, FTP, HLS video, BitTorrent, tarayıcı eklentisi

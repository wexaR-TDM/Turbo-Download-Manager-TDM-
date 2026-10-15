; TurboDM kurulum betiği (Inno Setup 6)
; Derleme: build.ps1 (ya da: ISCC installer\TurboDM.iss — önce build\stage hazırlanmalı)

#define AppName "TurboDM"
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef AppBuild
  #define AppBuild "dev"
#endif
#define AppExe "TurboDM.exe"
#ifndef Stage
  #define Stage "..\build\stage\TurboDM"
#endif

[Setup]
#ifdef TestMode
; Yalnızca otomatik test için: yönetici izni istemez, ayrı klasöre/kimlikle kurulur
#define AppGuid "0C4B1D2E-7E57-4E8A-A6F1-2D5C8B9E0F17"
AppId={{{#AppGuid}}
PrivilegesRequired=lowest
DefaultDirName={localappdata}\TurboDM-Test
OutputDir={#TestOut}
OutputBaseFilename=TurboDM-Setup-TEST
#define LinkName "TurboDM-Test"
#else
#define AppGuid "7F3A2C1E-9B4D-4E8A-A6F1-2D5C8B9E0F17"
AppId={{{#AppGuid}}
PrivilegesRequired=admin
DefaultDirName={autopf}\{#AppName}
OutputDir=..\dist
OutputBaseFilename=TurboDM-Setup-{#AppVersion}
#define LinkName "TurboDM"
#endif
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=TurboDM
AppComments=HTTP, FTP, HLS video and BitTorrent download manager
; test derlemesi gerçek kurulumun kısayollarıyla çakışmasın
DefaultGroupName={#LinkName}
DisableProgramGroupPage=yes
; İlk kurulumda yol: C:\Program Files\TurboDM. Güncellemede mevcut kurulum klasörü kullanılır.
UsePreviousAppDir=yes
UsePreviousTasks=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
SetupIconFile=turbodm.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
; --- TurboDM görünümü: koyu lacivert marka teması (klasik Windows görünümü yerine) ---
; windows11 özel stili kendi kontrollerini (onay kutuları dahil) çizer: yüksek DPI'da kesilme olmaz
WizardStyle=modern dark windows11 includetitlebar hidebevels
WizardBackColor=#0e1a33
WizardBackImageFile=wizard_bg_100.png,wizard_bg_150.png,wizard_bg_200.png
WizardImageFile=wizard_side_100.png,wizard_side_150.png,wizard_side_200.png
WizardSmallImageFile=wizard_small_100.png,wizard_small_150.png,wizard_small_200.png
WizardImageAlphaFormat=defined
DisableWelcomePage=no
DisableReadyPage=no
Compression=lzma2/ultra64
SolidCompression=yes
LZMANumBlockThreads=4
; Büyük paket (~350 MB): sıkıştırmayı ayrı 64 bit süreçte yap (32 bit derleyicide bellek yetmez)
LZMAUseSeparateProcess=yes
CloseApplications=yes
RestartApplications=no
; Kurulum başında dil seçimi: varsayılan Windows'un dili (desteklenmiyorsa listedeki ilk dil, İngilizce).
; Güncellemede önceki kurulumun dili kullanılır.
ShowLanguageDialog=yes
LanguageDetectionMethod=uilanguage
UsePreviousLanguage=yes
VersionInfoVersion={#AppVersion}.0
VersionInfoDescription=TurboDM Setup
VersionInfoProductName={#AppName}

[Languages]
; Adlar değiştirilmemeli: güncellemede önceki kurulumun dili bu adla bulunur (1.6.x yalnızca "turkish" idi)
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Messages]
turkish.SetupWindowTitle=TurboDM Kurulumu
turkish.WelcomeLabel1=TurboDM'e hoş geldiniz
turkish.WelcomeLabel2=Hızlı, çok bağlantılı indirme yöneticiniz birkaç adımda hazır olacak.%n%n⚡  Dosyaları 8 bağlantıyla paralel indirir, kaldığı yerden devam eder%n🎬  Sitelerdeki videoları tek tıkla .mp4 olarak kaydeder%n🧲  Magnet ve .torrent dosyalarını, dosya seçerek indirir%n🌐  Tarayıcı eklentisiyle indirmeleri otomatik yakalar
turkish.SelectDirLabel3=TurboDM şu klasöre kurulacak. Varsayılan konum çoğu kullanıcı için uygundur.
turkish.SelectTasksLabel2=TurboDM'in Windows ile nasıl çalışacağını seçin. Bu ayarları daha sonra TurboDM → Seçenekler'den değiştirebilirsiniz.
turkish.ReadyLabel1=TurboDM kurulmaya hazır.
turkish.FinishedHeadingLabel=TurboDM kuruldu 🎉
turkish.FinishedLabelNoIcons=TurboDM bilgisayarınıza kuruldu.
turkish.FinishedLabel=TurboDM bilgisayarınıza kuruldu. Masaüstündeki ya da Başlat menüsündeki TurboDM kısayoluyla başlatabilirsiniz.%n%nİpucu: Tarayıcınızdaki indirmelerin TurboDM'e gelmesi için tarayıcı eklentisini kurun.

english.SetupWindowTitle=TurboDM Setup
english.WelcomeLabel1=Welcome to TurboDM
english.WelcomeLabel2=Your fast, multi-connection download manager will be ready in a few steps.%n%n⚡  Downloads files over 8 parallel connections and resumes where it left off%n🎬  Saves videos from websites as .mp4 with one click%n🧲  Downloads magnet links and .torrent files with file selection%n🌐  Catches downloads automatically with the browser extension
english.SelectDirLabel3=TurboDM will be installed in the following folder. The default location suits most users.
english.SelectTasksLabel2=Choose how TurboDM works with Windows. You can change these settings later in TurboDM → Options.
english.ReadyLabel1=TurboDM is ready to install.
english.FinishedHeadingLabel=TurboDM is installed 🎉
english.FinishedLabelNoIcons=TurboDM has been installed on your computer.
english.FinishedLabel=TurboDM has been installed on your computer. You can start it with the TurboDM shortcut on the desktop or in the Start menu.%n%nTip: install the browser extension so that your browser's downloads go to TurboDM.

german.SetupWindowTitle=TurboDM Setup
german.WelcomeLabel1=Willkommen bei TurboDM
german.WelcomeLabel2=Ihr schneller Download-Manager mit mehreren Verbindungen ist in wenigen Schritten bereit.%n%n⚡  Lädt Dateien über 8 parallele Verbindungen und setzt dort fort, wo er aufgehört hat%n🎬  Speichert Videos von Websites mit einem Klick als .mp4%n🧲  Lädt Magnet-Links und .torrent-Dateien mit Dateiauswahl herunter%n🌐  Fängt Downloads mit der Browsererweiterung automatisch ab
german.SelectDirLabel3=TurboDM wird in den folgenden Ordner installiert. Der Standardort ist für die meisten Benutzer geeignet.
german.SelectTasksLabel2=Wählen Sie, wie TurboDM mit Windows zusammenarbeitet. Sie können diese Einstellungen später unter TurboDM → Optionen ändern.
german.ReadyLabel1=TurboDM ist bereit zur Installation.
german.FinishedHeadingLabel=TurboDM ist installiert 🎉
german.FinishedLabelNoIcons=TurboDM wurde auf Ihrem Computer installiert.
german.FinishedLabel=TurboDM wurde auf Ihrem Computer installiert. Sie können es über die TurboDM-Verknüpfung auf dem Desktop oder im Startmenü starten.%n%nTipp: Installieren Sie die Browsererweiterung, damit die Downloads Ihres Browsers an TurboDM gehen.

french.SetupWindowTitle=Installation de TurboDM
french.WelcomeLabel1=Bienvenue dans TurboDM
french.WelcomeLabel2=Votre gestionnaire de téléchargement rapide à connexions multiples sera prêt en quelques étapes.%n%n⚡  Télécharge les fichiers via 8 connexions parallèles et reprend là où il s'est arrêté%n🎬  Enregistre les vidéos des sites web en .mp4 en un clic%n🧲  Télécharge les liens magnet et les fichiers .torrent avec choix des fichiers%n🌐  Capture automatiquement les téléchargements grâce à l'extension de navigateur
french.SelectDirLabel3=TurboDM sera installé dans le dossier suivant. L'emplacement par défaut convient à la plupart des utilisateurs.
french.SelectTasksLabel2=Choisissez comment TurboDM fonctionne avec Windows. Vous pourrez modifier ces paramètres plus tard dans TurboDM → Options.
french.ReadyLabel1=TurboDM est prêt à être installé.
french.FinishedHeadingLabel=TurboDM est installé 🎉
french.FinishedLabelNoIcons=TurboDM a été installé sur votre ordinateur.
french.FinishedLabel=TurboDM a été installé sur votre ordinateur. Vous pouvez le lancer avec le raccourci TurboDM sur le bureau ou dans le menu Démarrer.%n%nAstuce : installez l'extension de navigateur pour que les téléchargements de votre navigateur passent par TurboDM.

spanish.SetupWindowTitle=Instalación de TurboDM
spanish.WelcomeLabel1=Bienvenido a TurboDM
spanish.WelcomeLabel2=Su gestor de descargas rápido y multiconexión estará listo en unos pocos pasos.%n%n⚡  Descarga archivos con 8 conexiones en paralelo y continúa donde lo dejó%n🎬  Guarda los vídeos de los sitios web como .mp4 con un clic%n🧲  Descarga enlaces magnet y archivos .torrent con selección de archivos%n🌐  Captura las descargas automáticamente con la extensión del navegador
spanish.SelectDirLabel3=TurboDM se instalará en la siguiente carpeta. La ubicación predeterminada es adecuada para la mayoría de los usuarios.
spanish.SelectTasksLabel2=Elija cómo funcionará TurboDM con Windows. Puede cambiar estos ajustes más tarde en TurboDM → Opciones.
spanish.ReadyLabel1=TurboDM está listo para instalarse.
spanish.FinishedHeadingLabel=TurboDM está instalado 🎉
spanish.FinishedLabelNoIcons=TurboDM se ha instalado en su equipo.
spanish.FinishedLabel=TurboDM se ha instalado en su equipo. Puede iniciarlo con el acceso directo de TurboDM en el escritorio o en el menú Inicio.%n%nConsejo: instale la extensión del navegador para que las descargas de su navegador vayan a TurboDM.

arabic.SetupWindowTitle=تثبيت TurboDM
arabic.WelcomeLabel1=مرحبًا بك في TurboDM
arabic.WelcomeLabel2=سيكون مدير التنزيل السريع متعدد الاتصالات جاهزًا في بضع خطوات.%n%n⚡  ينزّل الملفات عبر 8 اتصالات متوازية ويستأنف من حيث توقف%n🎬  يحفظ مقاطع الفيديو من المواقع بصيغة mp4 بنقرة واحدة%n🧲  ينزّل روابط magnet وملفات torrent مع اختيار الملفات%n🌐  يلتقط التنزيلات تلقائيًا عبر إضافة المتصفح
arabic.SelectDirLabel3=سيتم تثبيت TurboDM في المجلد التالي. الموقع الافتراضي مناسب لمعظم المستخدمين.
arabic.SelectTasksLabel2=اختر كيف يعمل TurboDM مع Windows. يمكنك تغيير هذه الإعدادات لاحقًا من TurboDM ← الخيارات.
arabic.ReadyLabel1=TurboDM جاهز للتثبيت.
arabic.FinishedHeadingLabel=تم تثبيت TurboDM 🎉
arabic.FinishedLabelNoIcons=تم تثبيت TurboDM على جهازك.
arabic.FinishedLabel=تم تثبيت TurboDM على جهازك. يمكنك تشغيله من اختصار TurboDM على سطح المكتب أو في قائمة ابدأ.%n%nنصيحة: ثبّت إضافة المتصفح لكي تنتقل تنزيلات متصفحك إلى TurboDM.

italian.SetupWindowTitle=Installazione di TurboDM
italian.WelcomeLabel1=Benvenuto in TurboDM
italian.WelcomeLabel2=Il tuo gestore di download veloce e multi-connessione sarà pronto in pochi passaggi.%n%n⚡  Scarica i file con 8 connessioni in parallelo e riprende da dove si era interrotto%n🎬  Salva i video dei siti web in .mp4 con un clic%n🧲  Scarica link magnet e file .torrent con la scelta dei file%n🌐  Intercetta automaticamente i download con l'estensione del browser
italian.SelectDirLabel3=TurboDM verrà installato nella cartella seguente. La posizione predefinita è adatta alla maggior parte degli utenti.
italian.SelectTasksLabel2=Scegli come TurboDM funzionerà con Windows. Potrai modificare queste impostazioni in seguito da TurboDM → Opzioni.
italian.ReadyLabel1=TurboDM è pronto per l'installazione.
italian.FinishedHeadingLabel=TurboDM è installato 🎉
italian.FinishedLabelNoIcons=TurboDM è stato installato sul computer.
italian.FinishedLabel=TurboDM è stato installato sul computer. Puoi avviarlo dal collegamento TurboDM sul desktop o nel menu Start.%n%nSuggerimento: installa l'estensione del browser perché i download del browser passino a TurboDM.

[CustomMessages]
; AppLang: programın dil kodu (kurulumda seçilen dil programa da aktarılır: TurboDM.exe --set-language)
; ExtHelpFile: tarayıcı eklentisi kurulum yardımı (Türkçe ya da İngilizce)
turkish.AppLang=tr
turkish.ExtHelpFile=TARAYICI_EKLENTISI.txt
turkish.GroupIcons=Ek simgeler:
turkish.TaskDesktop=Masaüstüne kısayol oluştur
turkish.GroupWindows=Windows entegrasyonu:
turkish.TaskAssoc=magnet: bağlantılarını ve .torrent dosyalarını TurboDM ile aç
turkish.TaskFirewall=Windows Güvenlik Duvarı'nda torrent bağlantılarına izin ver (önerilir)
turkish.TaskAutostart=Windows açılışında başlat (sistem tepsisinde)
turkish.IconComment=İnternet indirme yöneticisi
turkish.IconExtHelp=Tarayıcı Eklentisi (kurulum yardımı)
turkish.IconUninstall=TurboDM'i Kaldır
turkish.StatusFirewall=Güvenlik duvarı kuralı ekleniyor...
turkish.StatusAssoc=Dosya ilişkilendirmeleri yapılıyor...
turkish.RunNow=TurboDM'i şimdi başlat
turkish.RunExtHelp=Tarayıcı eklentisinin nasıl kurulacağını göster
turkish.NewerInstalled=Bu bilgisayarda TurboDM'in daha yeni bir sürümü (%1) kurulu.%n%nBu kurulum dosyası daha eski (%2) olduğu için hiçbir değişiklik yapılmadı.
turkish.UpToDate=TurboDM zaten en güncel sürüm (%1).%n%nKurulu dosyalar bu kurulum dosyasıyla aynı; hiçbir değişiklik yapılmadı.
turkish.UpgradeTitle=TurboDM güncellemesi
turkish.UpgradeText=Bilgisayarınızda TurboDM %1 kurulu. Bu yardımcı onu %2 sürümüne (derleme %3) güncelleyecek.%n%nAyarlarınız, indirme listeniz ve yarım kalmış indirmeleriniz korunur. TurboDM açıksa güncelleme öncesinde otomatik olarak kapatılır.
turkish.UpgradeDone=TurboDM güncellendi
turkish.UnTitle=TurboDM'i Kaldır
turkish.UnInfo=Program dosyaları, kısayollar, kayıt defteri girdileri (magnet/.torrent ilişkilendirmesi, Windows açılışında başlatma) ve güvenlik duvarı kuralı her zaman kaldırılır.%n%nAyrıca silinmesini istediklerinizi seçin:
turkish.UnAppData=Ayarlar, indirme listesi ve torrent devam verileri
turkish.UnPartials=Yarım kalmış indirmeler (geçici parçalar, bitmemiş torrent dosyaları)
turkish.UnDownloads=Tamamlanmış indirilen dosyalar (yalnızca TurboDM listesindekiler)
turkish.UnWarn=Son seçenek indirdiğiniz filmleri, programları vb. kalıcı olarak siler. TurboDM ile ilgisi olmayan dosyalarınıza ve klasörlerinize hiçbir durumda dokunulmaz.
turkish.UnCancel=İptal
turkish.UnRemove=Kaldır

english.AppLang=en
english.ExtHelpFile=BROWSER_EXTENSION.txt
english.GroupIcons=Additional icons:
english.TaskDesktop=Create a desktop shortcut
english.GroupWindows=Windows integration:
english.TaskAssoc=Open magnet: links and .torrent files with TurboDM
english.TaskFirewall=Allow torrent connections in Windows Firewall (recommended)
english.TaskAutostart=Start with Windows (in the system tray)
english.IconComment=Internet download manager
english.IconExtHelp=Browser extension (setup help)
english.IconUninstall=Uninstall TurboDM
english.StatusFirewall=Adding firewall rule...
english.StatusAssoc=Setting up file associations...
english.RunNow=Start TurboDM now
english.RunExtHelp=Show how to install the browser extension
english.NewerInstalled=A newer version of TurboDM (%1) is already installed on this computer.%n%nThis setup file is older (%2), so no changes were made.
english.UpToDate=TurboDM is already up to date (%1).%n%nThe installed files are the same as this setup file; no changes were made.
english.UpgradeTitle=TurboDM update
english.UpgradeText=TurboDM %1 is installed on your computer. This wizard will update it to version %2 (build %3).%n%nYour settings, download list and unfinished downloads are kept. If TurboDM is open, it is closed automatically before the update.
english.UpgradeDone=TurboDM has been updated
english.UnTitle=Uninstall TurboDM
english.UnInfo=Program files, shortcuts, registry entries (magnet/.torrent association, starting with Windows) and the firewall rule are always removed.%n%nSelect what else should be deleted:
english.UnAppData=Settings, download list and torrent resume data
english.UnPartials=Unfinished downloads (temporary parts, incomplete torrent files)
english.UnDownloads=Completed downloaded files (only those in the TurboDM list)
english.UnWarn=The last option permanently deletes the movies, programs etc. you downloaded. Files and folders unrelated to TurboDM are never touched.
english.UnCancel=Cancel
english.UnRemove=Uninstall

german.AppLang=de
german.ExtHelpFile=BROWSER_EXTENSION.txt
german.GroupIcons=Zusätzliche Symbole:
german.TaskDesktop=Desktopverknüpfung erstellen
german.GroupWindows=Windows-Integration:
german.TaskAssoc=magnet:-Links und .torrent-Dateien mit TurboDM öffnen
german.TaskFirewall=Torrent-Verbindungen in der Windows-Firewall zulassen (empfohlen)
german.TaskAutostart=Mit Windows starten (im Infobereich)
german.IconComment=Internet-Download-Manager
german.IconExtHelp=Browsererweiterung (Installationshilfe)
german.IconUninstall=TurboDM deinstallieren
german.StatusFirewall=Firewall-Regel wird hinzugefügt...
german.StatusAssoc=Dateizuordnungen werden eingerichtet...
german.RunNow=TurboDM jetzt starten
german.RunExtHelp=Anleitung zur Installation der Browsererweiterung anzeigen
german.NewerInstalled=Auf diesem Computer ist bereits eine neuere Version von TurboDM (%1) installiert.%n%nDiese Setup-Datei ist älter (%2), daher wurden keine Änderungen vorgenommen.
german.UpToDate=TurboDM ist bereits auf dem neuesten Stand (%1).%n%nDie installierten Dateien entsprechen dieser Setup-Datei; es wurden keine Änderungen vorgenommen.
german.UpgradeTitle=TurboDM-Update
german.UpgradeText=Auf Ihrem Computer ist TurboDM %1 installiert. Dieser Assistent aktualisiert es auf Version %2 (Build %3).%n%nIhre Einstellungen, Ihre Downloadliste und unvollständige Downloads bleiben erhalten. Ist TurboDM geöffnet, wird es vor dem Update automatisch geschlossen.
german.UpgradeDone=TurboDM wurde aktualisiert
german.UnTitle=TurboDM deinstallieren
german.UnInfo=Programmdateien, Verknüpfungen, Registrierungseinträge (magnet/.torrent-Zuordnung, Start mit Windows) und die Firewall-Regel werden immer entfernt.%n%nWählen Sie aus, was zusätzlich gelöscht werden soll:
german.UnAppData=Einstellungen, Downloadliste und Torrent-Fortsetzungsdaten
german.UnPartials=Unvollständige Downloads (temporäre Teile, unfertige Torrent-Dateien)
german.UnDownloads=Fertige heruntergeladene Dateien (nur die aus der TurboDM-Liste)
german.UnWarn=Die letzte Option löscht Ihre heruntergeladenen Filme, Programme usw. dauerhaft. Dateien und Ordner, die nichts mit TurboDM zu tun haben, werden niemals angerührt.
german.UnCancel=Abbrechen
german.UnRemove=Deinstallieren

french.AppLang=fr
french.ExtHelpFile=BROWSER_EXTENSION.txt
french.GroupIcons=Icônes supplémentaires :
french.TaskDesktop=Créer un raccourci sur le bureau
french.GroupWindows=Intégration à Windows :
french.TaskAssoc=Ouvrir les liens magnet: et les fichiers .torrent avec TurboDM
french.TaskFirewall=Autoriser les connexions torrent dans le pare-feu Windows (recommandé)
french.TaskAutostart=Démarrer avec Windows (dans la zone de notification)
french.IconComment=Gestionnaire de téléchargement Internet
french.IconExtHelp=Extension de navigateur (aide à l'installation)
french.IconUninstall=Désinstaller TurboDM
french.StatusFirewall=Ajout de la règle de pare-feu...
french.StatusAssoc=Configuration des associations de fichiers...
french.RunNow=Lancer TurboDM maintenant
french.RunExtHelp=Afficher comment installer l'extension de navigateur
french.NewerInstalled=Une version plus récente de TurboDM (%1) est déjà installée sur cet ordinateur.%n%nCe fichier d'installation est plus ancien (%2) ; aucune modification n'a été effectuée.
french.UpToDate=TurboDM est déjà à jour (%1).%n%nLes fichiers installés sont identiques à ce fichier d'installation ; aucune modification n'a été effectuée.
french.UpgradeTitle=Mise à jour de TurboDM
french.UpgradeText=TurboDM %1 est installé sur votre ordinateur. Cet assistant va le mettre à jour vers la version %2 (build %3).%n%nVos paramètres, votre liste de téléchargements et vos téléchargements inachevés sont conservés. Si TurboDM est ouvert, il est fermé automatiquement avant la mise à jour.
french.UpgradeDone=TurboDM a été mis à jour
french.UnTitle=Désinstaller TurboDM
french.UnInfo=Les fichiers du programme, les raccourcis, les entrées du registre (association magnet/.torrent, démarrage avec Windows) et la règle de pare-feu sont toujours supprimés.%n%nChoisissez ce qui doit également être supprimé :
french.UnAppData=Paramètres, liste de téléchargements et données de reprise des torrents
french.UnPartials=Téléchargements inachevés (parties temporaires, torrents incomplets)
french.UnDownloads=Fichiers téléchargés terminés (seulement ceux de la liste TurboDM)
french.UnWarn=La dernière option supprime définitivement les films, programmes, etc. que vous avez téléchargés. Les fichiers et dossiers sans rapport avec TurboDM ne sont jamais touchés.
french.UnCancel=Annuler
french.UnRemove=Désinstaller

spanish.AppLang=es
spanish.ExtHelpFile=BROWSER_EXTENSION.txt
spanish.GroupIcons=Iconos adicionales:
spanish.TaskDesktop=Crear un acceso directo en el escritorio
spanish.GroupWindows=Integración con Windows:
spanish.TaskAssoc=Abrir enlaces magnet: y archivos .torrent con TurboDM
spanish.TaskFirewall=Permitir conexiones torrent en el Firewall de Windows (recomendado)
spanish.TaskAutostart=Iniciar con Windows (en la bandeja del sistema)
spanish.IconComment=Gestor de descargas de Internet
spanish.IconExtHelp=Extensión del navegador (ayuda de instalación)
spanish.IconUninstall=Desinstalar TurboDM
spanish.StatusFirewall=Añadiendo regla del firewall...
spanish.StatusAssoc=Configurando asociaciones de archivos...
spanish.RunNow=Iniciar TurboDM ahora
spanish.RunExtHelp=Mostrar cómo instalar la extensión del navegador
spanish.NewerInstalled=Ya hay una versión más reciente de TurboDM (%1) instalada en este equipo.%n%nEste archivo de instalación es más antiguo (%2), por lo que no se ha realizado ningún cambio.
spanish.UpToDate=TurboDM ya está actualizado (%1).%n%nLos archivos instalados son iguales a este archivo de instalación; no se ha realizado ningún cambio.
spanish.UpgradeTitle=Actualización de TurboDM
spanish.UpgradeText=TurboDM %1 está instalado en su equipo. Este asistente lo actualizará a la versión %2 (compilación %3).%n%nSe conservan sus ajustes, su lista de descargas y las descargas sin terminar. Si TurboDM está abierto, se cerrará automáticamente antes de la actualización.
spanish.UpgradeDone=TurboDM se ha actualizado
spanish.UnTitle=Desinstalar TurboDM
spanish.UnInfo=Los archivos del programa, los accesos directos, las entradas del registro (asociación magnet/.torrent, inicio con Windows) y la regla del firewall se eliminan siempre.%n%nSeleccione qué más desea eliminar:
spanish.UnAppData=Ajustes, lista de descargas y datos de reanudación de torrents
spanish.UnPartials=Descargas sin terminar (partes temporales, torrents incompletos)
spanish.UnDownloads=Archivos descargados completados (solo los de la lista de TurboDM)
spanish.UnWarn=La última opción elimina de forma permanente las películas, programas, etc. que ha descargado. Los archivos y carpetas que no tienen relación con TurboDM nunca se tocan.
spanish.UnCancel=Cancelar
spanish.UnRemove=Desinstalar

arabic.AppLang=ar
arabic.ExtHelpFile=BROWSER_EXTENSION.txt
arabic.GroupIcons=أيقونات إضافية:
arabic.TaskDesktop=إنشاء اختصار على سطح المكتب
arabic.GroupWindows=التكامل مع Windows:
arabic.TaskAssoc=فتح روابط magnet وملفات torrent باستخدام TurboDM
arabic.TaskFirewall=السماح باتصالات التورنت في جدار حماية Windows (مستحسن)
arabic.TaskAutostart=التشغيل مع بدء Windows (في علبة النظام)
arabic.IconComment=مدير تنزيل الإنترنت
arabic.IconExtHelp=إضافة المتصفح (مساعدة التثبيت)
arabic.IconUninstall=إلغاء تثبيت TurboDM
arabic.StatusFirewall=جارٍ إضافة قاعدة جدار الحماية...
arabic.StatusAssoc=جارٍ إعداد اقترانات الملفات...
arabic.RunNow=تشغيل TurboDM الآن
arabic.RunExtHelp=عرض طريقة تثبيت إضافة المتصفح
arabic.NewerInstalled=يوجد إصدار أحدث من TurboDM (%1) مثبّت على هذا الجهاز.%n%nملف التثبيت هذا أقدم (%2)، لذا لم يتم إجراء أي تغيير.
arabic.UpToDate=TurboDM محدّث بالفعل (%1).%n%nالملفات المثبتة مطابقة لملف التثبيت هذا؛ لم يتم إجراء أي تغيير.
arabic.UpgradeTitle=تحديث TurboDM
arabic.UpgradeText=الإصدار %1 من TurboDM مثبّت على جهازك. سيقوم هذا المعالج بتحديثه إلى الإصدار %2 (البنية %3).%n%nيتم الاحتفاظ بإعداداتك وقائمة التنزيلات والتنزيلات غير المكتملة. إذا كان TurboDM مفتوحًا فسيتم إغلاقه تلقائيًا قبل التحديث.
arabic.UpgradeDone=تم تحديث TurboDM
arabic.UnTitle=إلغاء تثبيت TurboDM
arabic.UnInfo=تتم دائمًا إزالة ملفات البرنامج والاختصارات وإدخالات السجل (اقتران magnet و torrent، التشغيل مع Windows) وقاعدة جدار الحماية.%n%nاختر ما تريد حذفه أيضًا:
arabic.UnAppData=الإعدادات وقائمة التنزيلات وبيانات استئناف التورنت
arabic.UnPartials=التنزيلات غير المكتملة (الأجزاء المؤقتة، ملفات التورنت غير المكتملة)
arabic.UnDownloads=الملفات التي اكتمل تنزيلها (فقط الموجودة في قائمة TurboDM)
arabic.UnWarn=الخيار الأخير يحذف نهائيًا الأفلام والبرامج وغيرها مما قمت بتنزيله. لا يتم المساس أبدًا بالملفات والمجلدات التي لا علاقة لها بـ TurboDM.
arabic.UnCancel=إلغاء
arabic.UnRemove=إلغاء التثبيت

italian.AppLang=it
italian.ExtHelpFile=BROWSER_EXTENSION.txt
italian.GroupIcons=Icone aggiuntive:
italian.TaskDesktop=Crea un collegamento sul desktop
italian.GroupWindows=Integrazione con Windows:
italian.TaskAssoc=Apri i link magnet: e i file .torrent con TurboDM
italian.TaskFirewall=Consenti le connessioni torrent nel Firewall di Windows (consigliato)
italian.TaskAutostart=Avvia con Windows (nell'area di notifica)
italian.IconComment=Gestore di download Internet
italian.IconExtHelp=Estensione del browser (guida all'installazione)
italian.IconUninstall=Disinstalla TurboDM
italian.StatusFirewall=Aggiunta della regola del firewall...
italian.StatusAssoc=Configurazione delle associazioni dei file...
italian.RunNow=Avvia TurboDM ora
italian.RunExtHelp=Mostra come installare l'estensione del browser
italian.NewerInstalled=Su questo computer è già installata una versione più recente di TurboDM (%1).%n%nQuesto file di installazione è più vecchio (%2), quindi non è stata apportata alcuna modifica.
italian.UpToDate=TurboDM è già aggiornato (%1).%n%nI file installati sono uguali a questo file di installazione; non è stata apportata alcuna modifica.
italian.UpgradeTitle=Aggiornamento di TurboDM
italian.UpgradeText=Sul computer è installato TurboDM %1. Questa procedura lo aggiornerà alla versione %2 (build %3).%n%nLe impostazioni, l'elenco dei download e i download non completati vengono mantenuti. Se TurboDM è aperto, viene chiuso automaticamente prima dell'aggiornamento.
italian.UpgradeDone=TurboDM è stato aggiornato
italian.UnTitle=Disinstalla TurboDM
italian.UnInfo=I file del programma, i collegamenti, le voci del registro (associazione magnet/.torrent, avvio con Windows) e la regola del firewall vengono sempre rimossi.%n%nScegli cos'altro eliminare:
italian.UnAppData=Impostazioni, elenco dei download e dati di ripresa dei torrent
italian.UnPartials=Download non completati (parti temporanee, torrent incompleti)
italian.UnDownloads=File scaricati completati (solo quelli dell'elenco di TurboDM)
italian.UnWarn=L'ultima opzione elimina definitivamente i film, i programmi ecc. che hai scaricato. I file e le cartelle non collegati a TurboDM non vengono mai toccati.
italian.UnCancel=Annulla
italian.UnRemove=Disinstalla

[Tasks]
Name: "desktopicon"; Description: "{cm:TaskDesktop}"; GroupDescription: "{cm:GroupIcons}"
Name: "assoc"; Description: "{cm:TaskAssoc}"; GroupDescription: "{cm:GroupWindows}"
Name: "firewall"; Description: "{cm:TaskFirewall}"; GroupDescription: "{cm:GroupWindows}"
Name: "autostart"; Description: "{cm:TaskAutostart}"; GroupDescription: "{cm:GroupWindows}"; Flags: unchecked

[InstallDelete]
; Güncellemede eski sürümün çalışma zamanı dosyalarını temizle (artık kullanılmayan DLL'ler kalmasın)
Type: filesandordirs; Name: "{app}\_internal"

[Registry]
; Kurulu sürüm ve derleme parmak izi: sonraki kurulum dosyası güncel mi değil mi buradan anlar
; Üst anahtar: kaldırırken içi boş kalırsa o da silinsin (yoksa boş "Software\TurboDM" iz olarak kalıyordu)
Root: HKA; Subkey: "Software\TurboDM"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\TurboDM\Install"; ValueType: string; ValueName: "Version"; ValueData: "{#AppVersion}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\TurboDM\Install"; ValueType: string; ValueName: "Build"; ValueData: "{#AppBuild}"
Root: HKA; Subkey: "Software\TurboDM\Install"; ValueType: string; ValueName: "Path"; ValueData: "{app}"
#ifndef EdgeExtId
  #define EdgeExtId ""
#endif
#if EdgeExtId != "" && !Defined(TestMode)
; Edge Add-ons mağazasındaki eklenti: Edge bir sonraki açılışta "TurboDM eklentisi eklendi — Etkinleştir"
; diye sorar, güncellemeler mağazadan gelir. Kaldırınca anahtar silinir, Edge eklentiyi de kaldırır.
Root: HKLM32; Subkey: "Software\Microsoft\Edge\Extensions\{#EdgeExtId}"; ValueType: string; ValueName: "update_url"; ValueData: "https://edge.microsoft.com/extensionwebstorebase/v1/crx"; Flags: uninsdeletekey
#endif

[Files]
Source: "{#Stage}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; AppUserModelID: Windows bildirimlerinde "TurboDM.DownloadManager" yerine "TurboDM" adı ve simgesi görünsün
Name: "{group}\TurboDM"; Filename: "{app}\{#AppExe}"; Comment: "{cm:IconComment}"; AppUserModelID: "TurboDM.DownloadManager"
Name: "{group}\{cm:IconExtHelp}"; Filename: "{app}\{cm:ExtHelpFile}"
Name: "{group}\{cm:IconUninstall}"; Filename: "{uninstallexe}"; IconFilename: "{app}\turbodm.ico"
Name: "{autodesktop}\{#LinkName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon; AppUserModelID: "TurboDM.DownloadManager"

[Run]
; Güvenlik duvarı kuralı (önce eskisini sil: yeniden kurulumda çift kural olmasın)
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""TurboDM"""; Flags: runhidden; Tasks: firewall
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""TurboDM"" dir=in action=allow program=""{app}\{#AppExe}"" enable=yes profile=any"; Flags: runhidden; Tasks: firewall; StatusMsg: "{cm:StatusFirewall}"
; Kullanıcıya ait ayarlar, kurulumu başlatan kullanıcının hesabında yapılır
Filename: "{app}\{#AppExe}"; Parameters: "--register-assoc"; Flags: runhidden runasoriginaluser waituntilterminated; Tasks: assoc; StatusMsg: "{cm:StatusAssoc}"
; Kurulumda seçilen dil programın dili olur (güncellemede kullanıcının programdaki seçimine dokunulmaz)
Filename: "{app}\{#AppExe}"; Parameters: "--set-language {cm:AppLang}"; Flags: runhidden runasoriginaluser waituntilterminated; Check: not IsUpgradeInstall
Filename: "{app}\{#AppExe}"; Parameters: "--autostart on"; Flags: runhidden runasoriginaluser waituntilterminated; Tasks: autostart
Filename: "{app}\{#AppExe}"; Parameters: "--autostart off"; Flags: runhidden runasoriginaluser waituntilterminated; Tasks: not autostart
; Son sayfa
Filename: "{app}\{#AppExe}"; Parameters: "--minimized --resume"; Flags: nowait runasoriginaluser; Check: RelaunchAfterUpdate
Filename: "{app}\{#AppExe}"; Description: "{cm:RunNow}"; Flags: nowait postinstall skipifsilent runasoriginaluser; Check: not ClosedForUpdate
Filename: "{app}\{cm:ExtHelpFile}"; Description: "{cm:RunExtHelp}"; Flags: postinstall shellexec skipifsilent unchecked

[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""TurboDM"""; Flags: runhidden; RunOnceId: "DelFirewallRule"

[Code]
const
  MutexName = 'TurboDM_SingleInstance_Mutex';

var
  OptAppData, OptPartials, OptDownloads: Boolean;
  WasRunning: Boolean;  { güncelleme için kapatıldıysa kurulum bitince yeniden açılır }

{ Çalışan TurboDM'i önce düzgünce kapat (indirmelerin son durumu kaydedilsin), olmazsa zorla. }
procedure QuitRunning(const ExePath: String);
var
  RC, I: Integer;
begin
  if not CheckForMutexes(MutexName) then
    Exit;
  WasRunning := True;
  if FileExists(ExePath) then
    Exec(ExePath, '--quit', '', SW_HIDE, ewWaitUntilTerminated, RC);
  for I := 1 to 20 do
  begin
    if not CheckForMutexes(MutexName) then
      Exit;
    Sleep(250);
  end;
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM TurboDM.exe', '', SW_HIDE, ewWaitUntilTerminated, RC);
  Sleep(500);
end;

{ ---------------- Kurulu sürüm kontrolü / güncelleme ---------------- }
var
  IsUpgrade: Boolean;
  InstalledVersion: String;

{ Kurulu TurboDM'in sürümünü, derleme parmak izini ve klasörünü bulur.
  Eski kurulumlarda (Install anahtarı yoksa) Windows'un kaldırma kaydından okunur. }
function GetInstalled(var Ver, Build, Dir: String): Boolean;
var
  UninstKey: String;
begin
  Build := '';
  UninstKey := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\' + Chr(123) + '{#AppGuid}' + Chr(125) + '_is1';
  if RegQueryStringValue(HKA, 'Software\TurboDM\Install', 'Version', Ver) then
  begin
    RegQueryStringValue(HKA, 'Software\TurboDM\Install', 'Build', Build);
    if not RegQueryStringValue(HKA, 'Software\TurboDM\Install', 'Path', Dir) then
      RegQueryStringValue(HKA, UninstKey, 'Inno Setup: App Path', Dir);
    Result := True;
  end
  else
    Result := RegQueryStringValue(HKA, UninstKey, 'DisplayVersion', Ver) and
              RegQueryStringValue(HKA, UninstKey, 'Inno Setup: App Path', Dir);
end;

function InitializeSetup(): Boolean;
var
  Ver, Build, Dir: String;
  OldV, NewV: Int64;
  Cmp: Integer;
begin
  Result := True;
  IsUpgrade := False;
  if not GetInstalled(Ver, Build, Dir) then
    Exit;  { ilk kurulum }
  InstalledVersion := Ver;
  if not FileExists(AddBackslash(Dir) + '{#AppExe}') then
  begin
    IsUpgrade := True;  { kayıt var ama dosyalar eksik/bozuk → onar }
    Exit;
  end;
  if StrToVersion(Ver, OldV) and StrToVersion('{#AppVersion}', NewV) then
    Cmp := ComparePackedVersion(NewV, OldV)
  else
    Cmp := 1;
  if Cmp < 0 then
  begin
    SuppressibleMsgBox(FmtMessage(CustomMessage('NewerInstalled'), [Ver, '{#AppVersion}']),
      mbInformation, MB_OK, IDOK);
    Result := False;
  end
  else if (Cmp = 0) and (Build = '{#AppBuild}') then
  begin
    SuppressibleMsgBox(FmtMessage(CustomMessage('UpToDate'), [Ver]),
      mbInformation, MB_OK, IDOK);
    Result := False;
  end
  else
    IsUpgrade := True;  { daha eski sürüm ya da aynı sürümün farklı derlemesi → güncelle }
end;

procedure InitializeWizard();
begin
  if IsUpgrade then
  begin
    WizardForm.WelcomeLabel1.Caption := CustomMessage('UpgradeTitle');
    WizardForm.WelcomeLabel2.Caption :=
      FmtMessage(CustomMessage('UpgradeText'), [InstalledVersion, '{#AppVersion}', '{#AppBuild}']);
    WizardForm.FinishedHeadingLabel.Caption := CustomMessage('UpgradeDone');
  end;
end;

function IsUpgradeInstall(): Boolean;
begin
  Result := IsUpgrade;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  { Güncellemede klasör sorulmaz: mevcut kurulumun yerine yazılır }
  Result := IsUpgrade and (PageID = wpSelectDir);
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  { Koyu temada seçili metin görünmez oluyor: klasör yolunu seçimsiz göster }
  if CurPageID = wpSelectDir then
  begin
    WizardForm.DirEdit.SelStart := Length(WizardForm.DirEdit.Text);
    WizardForm.DirEdit.SelLength := 0;
  end;
end;

{ Güncelleme için kapatılan TurboDM, kurulum bitince görev çubuğunda (simge durumunda) yeniden açılır ve
  inmekte olan indirmeler kaldığı yerden sürer. /relaunch=0: yeniden açmayı çağıran üstlenir (build.ps1). }
function RelaunchAfterUpdate(): Boolean;
begin
  Result := WasRunning and (ExpandConstant('{param:relaunch|1}') <> '0');
end;

function ClosedForUpdate(): Boolean;
begin
  Result := WasRunning;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  QuitRunning(ExpandConstant('{app}\{#AppExe}'));
  Result := '';
end;

{ ---------------- Kaldırma seçenekleri penceresi ---------------- }
function AskUninstallOptions(): Boolean;
var
  Form: TSetupForm;
  Info, Warn: TNewStaticText;
  CbAppData, CbPartials, CbDownloads: TNewCheckBox;
  BtnOk, BtnCancel: TNewButton;
  W, Y: Integer;
begin
  Form := CreateCustomForm(ScaleX(580), ScaleY(310), False, False);
    Form.ClientWidth := ScaleX(580);   { boyutu açıkça ver: aksi hâlde yüksek DPI'da iki kez ölçeklenir }
    Form.ClientHeight := ScaleY(310);
    Form.Position := poScreenCenter;
  try
    Form.Caption := CustomMessage('UnTitle');
    W := Form.ClientWidth - ScaleX(40);

    Info := TNewStaticText.Create(Form);
    Info.Parent := Form;
    Info.Left := ScaleX(20);
    Info.Top := ScaleY(16);
    Info.Width := W;
    Info.WordWrap := True;
    Info.Caption := CustomMessage('UnInfo');
    Y := Info.Top + Info.Height + ScaleY(14);

    CbAppData := TNewCheckBox.Create(Form);
    CbAppData.Parent := Form;
    CbAppData.Left := ScaleX(20);
    CbAppData.Top := Y;
    CbAppData.Width := W;
    CbAppData.Height := ScaleY(22);
    CbAppData.Caption := CustomMessage('UnAppData');
    CbAppData.Checked := True;
    Y := Y + ScaleY(28);

    CbPartials := TNewCheckBox.Create(Form);
    CbPartials.Parent := Form;
    CbPartials.Left := ScaleX(20);
    CbPartials.Top := Y;
    CbPartials.Width := W;
    CbPartials.Height := ScaleY(22);
    CbPartials.Caption := CustomMessage('UnPartials');
    CbPartials.Checked := True;
    Y := Y + ScaleY(28);

    CbDownloads := TNewCheckBox.Create(Form);
    CbDownloads.Parent := Form;
    CbDownloads.Left := ScaleX(20);
    CbDownloads.Top := Y;
    CbDownloads.Width := W;
    CbDownloads.Height := ScaleY(22);
    CbDownloads.Caption := CustomMessage('UnDownloads');
    CbDownloads.Checked := False;
    Y := Y + ScaleY(30);

    Warn := TNewStaticText.Create(Form);
    Warn.Parent := Form;
    Warn.Left := ScaleX(20);
    Warn.Top := Y;
    Warn.Width := W;
    Warn.WordWrap := True;
    Warn.Font.Color := $7A8CFF;  { koyu temada okunur açık kırmızı (BGR) }
    Warn.Caption := CustomMessage('UnWarn');
    { uzun çevirilerde (ör. Almanca) metin kesilmesin: pencere yüksekliği içeriğe göre }
    Form.ClientHeight := Warn.Top + Warn.Height + ScaleY(60);

    BtnCancel := TNewButton.Create(Form);
    BtnCancel.Parent := Form;
    BtnCancel.Width := ScaleX(90);
    BtnCancel.Height := ScaleY(26);
    BtnCancel.Left := Form.ClientWidth - BtnCancel.Width - ScaleX(20);
    BtnCancel.Top := Form.ClientHeight - BtnCancel.Height - ScaleY(16);
    BtnCancel.Caption := CustomMessage('UnCancel');
    BtnCancel.ModalResult := mrCancel;
    BtnCancel.Cancel := True;

    BtnOk := TNewButton.Create(Form);
    BtnOk.Parent := Form;
    BtnOk.Width := ScaleX(90);
    BtnOk.Height := ScaleY(26);
    BtnOk.Left := BtnCancel.Left - BtnOk.Width - ScaleX(10);
    BtnOk.Top := BtnCancel.Top;
    BtnOk.Caption := CustomMessage('UnRemove');
    BtnOk.ModalResult := mrOk;
    BtnOk.Default := True;

    Form.ActiveControl := BtnOk;
    Result := Form.ShowModal() = mrOk;
    if Result then
    begin
      OptAppData := CbAppData.Checked;
      OptPartials := CbPartials.Checked;
      OptDownloads := CbDownloads.Checked;
    end;
  finally
    Form.Free();
  end;
end;

function InitializeUninstall(): Boolean;
begin
  { Sessiz kaldırmada (/SILENT, /VERYSILENT) varsayılan: ayarlar + yarım kalanlar silinir, indirilenler korunur }
  OptAppData := True;
  OptPartials := True;
  OptDownloads := False;
  if UninstallSilent() then
    Result := True
  else
    Result := AskUninstallOptions();
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  RC: Integer;
  Args: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    QuitRunning(ExpandConstant('{app}\{#AppExe}'));
    { Program dosyaları silinmeden önce: kayıt defteri + seçilen veriler }
    Args := '--cleanup';
    if OptPartials then Args := Args + ' --partials';
    if OptDownloads then Args := Args + ' --downloads';
    if OptAppData then Args := Args + ' --appdata';
    Exec(ExpandConstant('{app}\{#AppExe}'), Args, '', SW_HIDE, ewWaitUntilTerminated, RC);
  end
  else if CurUninstallStep = usPostUninstall then
  begin
    { Programın kendi klasöründe sonradan oluşmuş her şey dahil, kurulum klasörünü tamamen kaldır }
    DelTree(ExpandConstant('{app}'), True, True, True);
  end;
end;

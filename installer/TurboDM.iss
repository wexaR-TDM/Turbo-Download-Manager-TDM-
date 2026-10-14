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
AppComments=HTTP, FTP, HLS video ve BitTorrent indirme yöneticisi
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
ShowLanguageDialog=no
VersionInfoVersion={#AppVersion}.0
VersionInfoDescription=TurboDM Kurulum Programı
VersionInfoProductName={#AppName}

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Messages]
SetupWindowTitle=TurboDM Kurulumu
WelcomeLabel1=TurboDM'e hoş geldiniz
WelcomeLabel2=Hızlı, çok bağlantılı indirme yöneticiniz birkaç adımda hazır olacak.%n%n⚡  Dosyaları 8 bağlantıyla paralel indirir, kaldığı yerden devam eder%n🎬  Sitelerdeki videoları tek tıkla .mp4 olarak kaydeder%n🧲  Magnet ve .torrent dosyalarını, dosya seçerek indirir%n🌐  Tarayıcı eklentisiyle indirmeleri otomatik yakalar
SelectDirLabel3=TurboDM şu klasöre kurulacak. Varsayılan konum çoğu kullanıcı için uygundur.
SelectTasksLabel2=TurboDM'in Windows ile nasıl çalışacağını seçin. Bu ayarları daha sonra TurboDM → Seçenekler'den değiştirebilirsiniz.
ReadyLabel1=TurboDM kurulmaya hazır.
FinishedHeadingLabel=TurboDM kuruldu 🎉
FinishedLabelNoIcons=TurboDM bilgisayarınıza kuruldu.
FinishedLabel=TurboDM bilgisayarınıza kuruldu. Masaüstündeki ya da Başlat menüsündeki TurboDM kısayoluyla başlatabilirsiniz.%n%nİpucu: Tarayıcınızdaki indirmelerin TurboDM'e gelmesi için tarayıcı eklentisini kurun.

[Tasks]
Name: "desktopicon"; Description: "Masaüstüne kısayol oluştur"; GroupDescription: "Ek simgeler:"
Name: "assoc"; Description: "magnet: bağlantılarını ve .torrent dosyalarını TurboDM ile aç"; GroupDescription: "Windows entegrasyonu:"
Name: "firewall"; Description: "Windows Güvenlik Duvarı'nda torrent bağlantılarına izin ver (önerilir)"; GroupDescription: "Windows entegrasyonu:"
Name: "autostart"; Description: "Windows açılışında başlat (sistem tepsisinde)"; GroupDescription: "Windows entegrasyonu:"; Flags: unchecked

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
Name: "{group}\TurboDM"; Filename: "{app}\{#AppExe}"; Comment: "İnternet indirme yöneticisi"; AppUserModelID: "TurboDM.DownloadManager"
Name: "{group}\Tarayıcı Eklentisi (kurulum yardımı)"; Filename: "{app}\TARAYICI_EKLENTISI.txt"
Name: "{group}\TurboDM'i Kaldır"; Filename: "{uninstallexe}"; IconFilename: "{app}\turbodm.ico"
Name: "{autodesktop}\{#LinkName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon; AppUserModelID: "TurboDM.DownloadManager"

[Run]
; Güvenlik duvarı kuralı (önce eskisini sil: yeniden kurulumda çift kural olmasın)
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""TurboDM"""; Flags: runhidden; Tasks: firewall
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""TurboDM"" dir=in action=allow program=""{app}\{#AppExe}"" enable=yes profile=any"; Flags: runhidden; Tasks: firewall; StatusMsg: "Güvenlik duvarı kuralı ekleniyor..."
; Kullanıcıya ait ayarlar, kurulumu başlatan kullanıcının hesabında yapılır
Filename: "{app}\{#AppExe}"; Parameters: "--register-assoc"; Flags: runhidden runasoriginaluser waituntilterminated; Tasks: assoc; StatusMsg: "Dosya ilişkilendirmeleri yapılıyor..."
Filename: "{app}\{#AppExe}"; Parameters: "--autostart on"; Flags: runhidden runasoriginaluser waituntilterminated; Tasks: autostart
Filename: "{app}\{#AppExe}"; Parameters: "--autostart off"; Flags: runhidden runasoriginaluser waituntilterminated; Tasks: not autostart
; Son sayfa
Filename: "{app}\{#AppExe}"; Parameters: "--minimized --resume"; Flags: nowait runasoriginaluser; Check: RelaunchAfterUpdate
Filename: "{app}\{#AppExe}"; Description: "TurboDM'i şimdi başlat"; Flags: nowait postinstall skipifsilent runasoriginaluser; Check: not ClosedForUpdate
Filename: "{app}\TARAYICI_EKLENTISI.txt"; Description: "Tarayıcı eklentisinin nasıl kurulacağını göster"; Flags: postinstall shellexec skipifsilent unchecked

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
    SuppressibleMsgBox('Bu bilgisayarda TurboDM''in daha yeni bir sürümü (' + Ver + ') kurulu.' + #13#10#13#10 +
      'Bu kurulum dosyası daha eski (' + '{#AppVersion}' + ') olduğu için hiçbir değişiklik yapılmadı.',
      mbInformation, MB_OK, IDOK);
    Result := False;
  end
  else if (Cmp = 0) and (Build = '{#AppBuild}') then
  begin
    SuppressibleMsgBox('TurboDM zaten en güncel sürüm (' + Ver + ').' + #13#10#13#10 +
      'Kurulu dosyalar bu kurulum dosyasıyla aynı; hiçbir değişiklik yapılmadı.',
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
    WizardForm.WelcomeLabel1.Caption := 'TurboDM güncellemesi';
    WizardForm.WelcomeLabel2.Caption :=
      'Bilgisayarınızda TurboDM ' + InstalledVersion + ' kurulu. Bu yardımcı onu ' +
      '{#AppVersion} sürümüne (derleme {#AppBuild}) güncelleyecek.' + #13#10#13#10 +
      'Ayarlarınız, indirme listeniz ve yarım kalmış indirmeleriniz korunur. TurboDM açıksa ' +
      'güncelleme öncesinde otomatik olarak kapatılır.';
    WizardForm.FinishedHeadingLabel.Caption := 'TurboDM güncellendi';
  end;
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
  Form := CreateCustomForm(ScaleX(540), ScaleY(310), False, False);
    Form.ClientWidth := ScaleX(540);   { boyutu açıkça ver: aksi hâlde yüksek DPI'da iki kez ölçeklenir }
    Form.ClientHeight := ScaleY(310);
    Form.Position := poScreenCenter;
  try
    Form.Caption := 'TurboDM''i Kaldır';
    W := Form.ClientWidth - ScaleX(40);

    Info := TNewStaticText.Create(Form);
    Info.Parent := Form;
    Info.Left := ScaleX(20);
    Info.Top := ScaleY(16);
    Info.Width := W;
    Info.WordWrap := True;
    Info.Caption := 'Program dosyaları, kısayollar, kayıt defteri girdileri (magnet/.torrent ' +
      'ilişkilendirmesi, Windows açılışında başlatma) ve güvenlik duvarı kuralı her zaman kaldırılır.' + #13#10#13#10 +
      'Ayrıca silinmesini istediklerinizi seçin:';
    Y := Info.Top + Info.Height + ScaleY(14);

    CbAppData := TNewCheckBox.Create(Form);
    CbAppData.Parent := Form;
    CbAppData.Left := ScaleX(20);
    CbAppData.Top := Y;
    CbAppData.Width := W;
    CbAppData.Height := ScaleY(22);
    CbAppData.Caption := 'Ayarlar, indirme listesi ve torrent devam verileri';
    CbAppData.Checked := True;
    Y := Y + ScaleY(28);

    CbPartials := TNewCheckBox.Create(Form);
    CbPartials.Parent := Form;
    CbPartials.Left := ScaleX(20);
    CbPartials.Top := Y;
    CbPartials.Width := W;
    CbPartials.Height := ScaleY(22);
    CbPartials.Caption := 'Yarım kalmış indirmeler (geçici parçalar, bitmemiş torrent dosyaları)';
    CbPartials.Checked := True;
    Y := Y + ScaleY(28);

    CbDownloads := TNewCheckBox.Create(Form);
    CbDownloads.Parent := Form;
    CbDownloads.Left := ScaleX(20);
    CbDownloads.Top := Y;
    CbDownloads.Width := W;
    CbDownloads.Height := ScaleY(22);
    CbDownloads.Caption := 'Tamamlanmış indirilen dosyalar (yalnızca TurboDM listesindekiler)';
    CbDownloads.Checked := False;
    Y := Y + ScaleY(30);

    Warn := TNewStaticText.Create(Form);
    Warn.Parent := Form;
    Warn.Left := ScaleX(20);
    Warn.Top := Y;
    Warn.Width := W;
    Warn.WordWrap := True;
    Warn.Font.Color := $7A8CFF;  { koyu temada okunur açık kırmızı (BGR) }
    Warn.Caption := 'Son seçenek indirdiğiniz filmleri, programları vb. kalıcı olarak siler. ' +
      'TurboDM ile ilgisi olmayan dosyalarınıza ve klasörlerinize hiçbir durumda dokunulmaz.';

    BtnCancel := TNewButton.Create(Form);
    BtnCancel.Parent := Form;
    BtnCancel.Width := ScaleX(90);
    BtnCancel.Height := ScaleY(26);
    BtnCancel.Left := Form.ClientWidth - BtnCancel.Width - ScaleX(20);
    BtnCancel.Top := Form.ClientHeight - BtnCancel.Height - ScaleY(16);
    BtnCancel.Caption := 'İptal';
    BtnCancel.ModalResult := mrCancel;
    BtnCancel.Cancel := True;

    BtnOk := TNewButton.Create(Form);
    BtnOk.Parent := Form;
    BtnOk.Width := ScaleX(90);
    BtnOk.Height := ScaleY(26);
    BtnOk.Left := BtnCancel.Left - BtnOk.Width - ScaleX(10);
    BtnOk.Top := BtnCancel.Top;
    BtnOk.Caption := 'Kaldır';
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

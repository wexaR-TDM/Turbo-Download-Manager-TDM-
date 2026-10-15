# TurboDM release notes

What changed in each version, newest first. To download the latest version:
**[github.com/wexaR-TDM/TurboDM/releases/latest](https://github.com/wexaR-TDM/TurboDM/releases/latest)**
To update an installed TurboDM: *Help → Check for updates*. · [Türkçe sürüm notları](SURUM_NOTLARI.md)

<!-- Developer note: add a "## x.y.z" section at the top for every new version, in the same order as
     SURUM_NOTLARI.md. The update window shows the section of that version (build.ps1 puts it into latest.json). -->

## 1.7.6
• Fix: the version shown in TurboDM.exe's file properties (Details) is now correct (it always said 1.0.0.0)
• Updated the feature line on the setup wizard's side image
• General cleanup of code and documents: unused code and texts removed, developer notes updated

## 1.7.5
• When the window is closed and the program goes to the system tray, the "The program keeps running in the background" notification is shown only the first time instead of every time

## 1.7.4
• Browser extension 1.5.1: closing a tab where a video was found no longer logs a "No tab with id" error on the extensions page (it was harmless and did not affect anything)

## 1.7.3
• Fix: the error status in the list ("Error: …") and the "retrying" info of video streams now also appear in the chosen language
• GitHub page: the English page shows English screenshots of the program

## 1.7.2
• The default language is the Windows language again (in setup and in the program); "System language (automatic)" option at the top of the Language menu

## 1.7.1
• Instant language switching: a fixed "Language" menu in the menu bar; menus, the list and open download windows switch without closing the program, downloads keep running
• English is the default language (in setup and in the program); choose the language at the start of setup or from the Language menu

## 1.7.0
• Language support: Türkçe, English, Deutsch, Français, Español, العربية (right-to-left layout), Italiano — Options → General → Language; the default is the Windows language
• Setup asks for the language first; the chosen language becomes the program's language. The setup and uninstall windows also use the chosen language
• Browser extension 1.5.0: 7 languages (follows the browser language)
• Release notes in the update window follow the program language (Turkish or English); the GitHub page and release notes are also available in English

## 1.6.4
• The update window explains what happens during an update: the program closes briefly, reopens in the taskbar when installation finishes, and active downloads continue where they left off

## 1.6.3
• Help → Release notes: the change notes of all versions on one page (also public on GitHub)

## 1.6.2
• TurboDM is now open source: GNU GPL v3 license; source code at github.com/wexaR-TDM/TurboDM
• The license text ships with the installer; the About window links to the license and source code

## 1.6.1
• Download windows are independent of the main window: they stay open when the main window is minimized

## 1.6.0
• Format choice: "Format" in the download window — MP4 (as is), MKV (lossless, fast), AVI (for older TVs/players), MP3 (audio only); conversion runs when the download finishes
• DASH (.mpd) video streams are supported
• Embedded players: the video is requested with the player's own page address and origin (for servers that return error 403)
• Browser extension 1.4.4: captures DASH streams and the address of embedded players

## 1.5.8
• New project repository address: github.com/wexaR-TDM/TurboDM (the old address redirects; updates are uninterrupted)
• License: the exact source code of the bundled ffmpeg is published on every release page; source details are in the ffmpeg folder
• Browser extension 1.4.3: project page link updated

## 1.5.7
• Security: updates are now digitally signed. TurboDM only installs updates signed by the developer; fake updates cannot be distributed
• Security: updates are downloaded only from the official GitHub release page

## 1.5.6
• Newly opened windows (download window, options, alerts) open in the exact center of the screen

## 1.5.5
• The server connection limit is not fixed: while a download runs smoothly, a new connection is tried about every 20 s; if the server allows it, speed increases and the new limit is saved

## 1.5.4
• Server connection limit (like IDM): if a server allows only a few connections (e.g. gofile), surplus connections back off without breaking the download; it continues with the working connections and speed fluctuates less
• A single connection failing repeatedly no longer stops the whole download; an error is shown only if no connection works
• The learned limit is saved: on resume, as many connections as the server allows are opened; it is shown in the download window
• The connection list shows the real cause of an error; "Retry-After" from the server is respected

## 1.5.3
• Simpler About window; the video component is called "Video engine" everywhere

## 1.5.2
• New TurboDM theme: follows Windows light/dark mode automatically and switches instantly while the program is open
• TurboDM-specific line icons, a toolbar with logo and name, a category menu with counts
• A thin progress line in the list's "Status" column; completed in green, failed in red
• Window title bars take the theme color (Windows 11)
• Options → General → Theme: Same as Windows / Light / Dark

## 1.5.1
• Bulk actions: checkboxes at the start of the list; clicking a box adds the row to the selection without disturbing others
• Header box to select all / clear selection; Ctrl+A and Esc shortcuts
• "Bulk selection" menu: select unfinished, completed, stopped, failed
• The context menu applies to all selected downloads (resume, stop, queue, copy addresses, delete)
• Fix: when the list refreshed, only the last row of a multi-selection remained

## 1.5.0
• Faster torrents: upload speed is limited automatically while downloading (a saturated upload line was slowing downloads)
• Torrent: connects to more peers faster, deeper piece request queue, multi-core piece verification
• Torrent: prefers encrypted connections and uses a random port instead of the well-known 6881 (against ISP throttling)
• Options → Torrent: "Limit upload speed automatically while downloading" setting
• After an update TurboDM reopens on its own (in the taskbar, without stealing focus); active downloads continue where they left off

## 1.4.9
• Browser extension 1.4.2: Turkish and English language support (the extension's name and description follow the browser language)

## 1.4.8
• Browser extension 1.4.1: TurboDM icon (toolbar and extensions page), store-ready package

## 1.4.7
• Browser extension 1.4.0: the "Download this video" button and quality menu now work on every site (Vimeo, Dailymotion, X and more)
• The extension passes the page's video to TurboDM, which finds the qualities; streams loaded by the page appear in the same menu
• "Open this page's video in TurboDM" button in the extension window for every page

## 1.4.6
• Updates now come via GitHub: new versions can be downloaded and installed with Help → Check for updates

## 1.4.5
• Downloads that were running during an update continue automatically where they left off once the update finishes

## 1.4.4
• Torrent: .torrent links are no longer saved as files but opened directly as torrents (file selection window)
• Torrent: on sites that only give the file to the browser (pages with a download button), the .torrent downloads in the browser and opens in TurboDM automatically (browser extension 1.3.2)
• If a site sends a web page instead of a torrent, TurboDM explains what to do instead of saving an .html file
• Minimize and maximize buttons in the download window; minimized windows go to the taskbar

## 1.4.3
• Uninstall: the empty 'Software\TurboDM' registry key is also removed (no traces left)

## 1.4.2
• Security: the browser bridge accepts requests only from the local address (DNS rebinding protection)
• Starting twice at the same time, or another program using the bridge port, no longer causes problems
• If the download list gets corrupted, it is recovered automatically from the previous good copy
• Disk space is checked before a download starts; disk/permission errors are reported immediately with a clear message
• Expired redirect addresses (cloud storage, GitHub, etc.) are refreshed automatically
• Very long file names and names forbidden in Windows (CON, NUL…) are corrected

## 1.4.1
• Fixed the long wait at the start of large downloads (e.g. a 22 GB 8K video): the temporary file is created as a sparse file
• TurboDM blue colors: the Windows accent color (e.g. red) no longer shows in the progress bar and tables
• 'Save folder' in the download window shows only the folder; the file name is set automatically

## 1.4.0
• IDM-style download window: connections and segmented progress bar in the lower section (Hide/Show details)
• New tab 'Speed limiter': a per-download speed limit that can be changed while downloading
• New tab 'When done': shut down / sleep / exit TurboDM (30 s countdown, can be cancelled)
• Scheduler: shut down / sleep / exit when the queue finishes

## 1.3.1
• Choosing a quality in the browser menu opens the save location window (quality and extension preselected; Download Later / Start Download is up to you)

## 1.3.0
• On YouTube the 'Download this video' button opens the quality menu on the page; the chosen quality downloads without further questions (like IDM)
• TurboDM's windows and alerts (download, completed, error) come to the front
• A front alert with a 'Retry' button on download errors

## 1.2.0
• YouTube downloads 2–3× faster: video and audio at the same time with 24 connections (IDM method)
• Fix: videos with special characters such as ™ in the title failed with "yt-dlp exit code 0"
• Expired stream addresses are refreshed automatically and the download continues where it left off
• Videos that were mistaken for errors in the previous version but actually downloaded are completed with "Resume" without downloading again
• The program name appears as "TurboDM" in Windows notifications
• Fix: Resume right after Pause could corrupt the file while a speed limit was on
• Fix: single-part downloads whose connection dropped early were counted as "completed" while incomplete

## 1.1.0
• Video downloads from YouTube and other sites (1080p/4K, audio only) — with the button over the video in the browser
• Help → Check for updates: TurboDM and the YouTube engine are updated from one window
• New TurboDM-themed setup wizard; installed version check and update mode
• Uninstall options: settings, unfinished downloads and downloaded files can be chosen separately

## 1.0.0
• First release: multi-connection downloads, FTP, HLS video, BitTorrent, browser extension

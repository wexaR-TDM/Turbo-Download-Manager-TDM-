"""libtorrent tabanlı BitTorrent motoru (magnet bağlantıları ve .torrent dosyaları)."""
import os

try:
    import libtorrent as lt
except ImportError:  # torrent desteği isteğe bağlı
    lt = None

AVAILABLE = lt is not None

STATE_TEXT = {
    "checking_files": "Dosyalar denetleniyor",
    "downloading_metadata": "Meta veri alınıyor",
    "downloading": "İndiriliyor",
    "finished": "Tamamlandı",
    "seeding": "Paylaşılıyor (seed)",
    "checking_resume_data": "Devam verisi denetleniyor",
}


def file_list(ti):
    """[(yol, boyut, dolgu_mu), ...] — dizin sırası libtorrent dosya indeksleriyle aynıdır.
    v2/hibrit torrentlerdeki '.pad' dolgu dosyaları kullanıcıya gösterilmez."""
    fs = ti.layout() if hasattr(ti, "layout") else ti.files()
    pad = lt.file_storage.flag_pad_file
    return [(fs.file_path(i), fs.file_size(i), bool(fs.file_flags(i) & pad))
            for i in range(fs.num_files())]


def performance_settings():
    """libtorrent'in varsayılanları temkinli; hızlı hatlarda indirmenin tam hıza çıkması için:"""
    cpu = os.cpu_count() or 4
    return {
        "connections_limit": 500,           # varsayılan 200: kalabalık torrentlerde daha çok eş
        "connection_speed": 100,            # saniyede açılan bağlantı (varsayılan 30): hıza daha çabuk çıkar
        "torrent_connect_boost": 60,        # yeni torrent eklenince ilk bağlantı patlaması
        "max_out_request_queue": 1500,      # bir eşten aynı anda istenen parça (yüksek hız × gecikme)
        "max_allowed_in_request_queue": 2000,
        "request_queue_time": 4,
        "hashing_threads": max(2, min(8, cpu // 2)),   # parça doğrulaması saniyede yüzlerce MB'a yetişsin
        "aio_threads": max(4, min(16, cpu)),
        "piece_extent_affinity": True,      # komşu parçaları aynı eşten: disk yazımı sıralı olur
        "mixed_mode_algorithm": 1,          # peer_proportional: TCP eşleri uTP eşlerini boğmasın
        # Şifreli bağlantı tercih edilir: bazı servis sağlayıcılar şifresiz BitTorrent trafiğini yavaşlatır
        "out_enc_policy": 1, "in_enc_policy": 1,   # pe_enabled (şifreli dene, olmazsa şifresiz)
        "allowed_enc_level": 3,             # rc4 + düz
        "prefer_rc4": True,
    }


class TorrentEngine:
    def __init__(self, port=6881, dl_limit=0, ul_limit=0):
        if not AVAILABLE:
            raise RuntimeError("libtorrent yüklü değil (pip install libtorrent)")
        settings = {
            "listen_interfaces": f"0.0.0.0:{port},[::]:{port}",
            "alert_mask": (lt.alert_category.error | lt.alert_category.status
                           | lt.alert_category.storage),
            "enable_dht": True, "enable_lsd": True,
            "enable_upnp": True, "enable_natpmp": True,
            "user_agent": "TurboDM/1.0 libtorrent/" + lt.__version__,
            "download_rate_limit": dl_limit, "upload_rate_limit": ul_limit,
        }
        settings.update(performance_settings())
        self.ses = lt.session(settings)
        self.handles = {}       # item_id -> torrent_handle
        self.probes = {}        # dosya seçimi bekleyen magnet'ler
        self.resume_cb = None   # (item_id, bytes) -> None
        self.error_cb = None    # (item_id, str) -> None

    def set_limits(self, dl=0, ul=0):
        self.ses.apply_settings({"download_rate_limit": int(dl), "upload_rate_limit": int(ul)})

    # ------------------------------------------------ magnet meta veri ön alımı (dosya seçimi için)
    def probe_start(self, magnet, save_path):
        """Magnet'i 'upload_mode'da ekler: meta veri (dosya listesi) iner ama hiçbir dosya parçası
        indirilmez. Kullanıcı dosyaları seçince probe_adopt ile gerçek indirmeye dönüşür."""
        atp = lt.parse_magnet_uri(magnet)
        atp.save_path = save_path
        atp.flags |= lt.torrent_flags.upload_mode
        atp.flags &= ~lt.torrent_flags.auto_managed
        atp.flags &= ~lt.torrent_flags.paused
        if self.ses.find_torrent(atp.info_hashes.get_best()).is_valid():
            raise RuntimeError("Bu torrent zaten listede")
        key = "probe-" + str(atp.info_hashes.get_best())
        self.probes[key] = self.ses.add_torrent(atp)
        return key

    def probe_info(self, key):
        """Meta veri geldiyse torrent_info, gelmediyse None."""
        h = self.probes.get(key)
        if h and h.is_valid() and h.status().has_metadata:
            return h.torrent_file()
        return None

    def probe_save_torrent(self, key, out_path):
        ti = self.probe_info(key)
        if not ti:
            return False
        h = self.probes[key]
        ct = lt.create_torrent(ti)
        known = {t.url for t in ti.trackers()}
        for t in h.trackers():
            if t["url"] not in known:
                ct.add_tracker(t["url"], t.get("tier", 0))
        with open(out_path, "wb") as f:
            f.write(lt.bencode(ct.generate()))
        return True

    def probe_adopt(self, key, item_id, save_path, priorities=None):
        h = self.probes.pop(key)
        h.pause()
        if h.status().save_path != save_path:
            h.move_storage(save_path)
        if priorities and h.status().has_metadata:
            h.prioritize_files(list(priorities))
        h.unset_flags(lt.torrent_flags.upload_mode)
        self.handles[item_id] = h

    def probe_cancel(self, key):
        h = self.probes.pop(key, None)
        if h and h.is_valid():
            self.ses.remove_torrent(h)

    def set_priorities(self, item_id, priorities):
        h = self.handles.get(item_id)
        if h and h.is_valid() and h.status().has_metadata:
            h.prioritize_files(list(priorities))

    def add(self, item_id, source, save_path, resume_file=None, paused=False, priorities=None):
        atp = None
        if resume_file and os.path.exists(resume_file):
            try:
                with open(resume_file, "rb") as f:
                    atp = lt.read_resume_data(f.read())
            except Exception:  # noqa: BLE001
                atp = None
        if atp is None:
            if source.startswith("magnet:"):
                atp = lt.parse_magnet_uri(source)
            else:
                atp = lt.add_torrent_params()
                atp.ti = lt.torrent_info(source)
        atp.save_path = save_path
        if priorities and atp.ti is not None and len(priorities) == atp.ti.num_files():
            atp.file_priorities = list(priorities)
        if self.ses.find_torrent(atp.info_hashes.get_best() if atp.ti is None
                                 else atp.ti.info_hashes().get_best()).is_valid():
            raise RuntimeError("Bu torrent zaten listede")
        if paused:
            atp.flags |= lt.torrent_flags.paused
            atp.flags &= ~lt.torrent_flags.auto_managed
        h = self.ses.add_torrent(atp)
        self.handles[item_id] = h
        return h

    def pause(self, item_id):
        h = self.handles.get(item_id)
        if h:
            h.unset_flags(lt.torrent_flags.auto_managed)
            h.pause()
            self.request_resume_data(item_id)

    def resume(self, item_id):
        h = self.handles.get(item_id)
        if h:
            h.resume()

    def remove(self, item_id, delete_files=False):
        h = self.handles.pop(item_id, None)
        if h:
            if delete_files:
                self.ses.remove_torrent(h, lt.options_t.delete_files)
            else:
                self.ses.remove_torrent(h)

    def request_resume_data(self, item_id=None):
        flags = getattr(lt.save_resume_flags_t, "save_info_dict", 0)
        targets = [item_id] if item_id else list(self.handles)
        for iid in targets:
            h = self.handles.get(iid)
            if h and h.is_valid() and h.need_save_resume_data():
                h.save_resume_data(flags)

    def _id_of(self, handle):
        for iid, h in self.handles.items():
            if h == handle:
                return iid
        return None

    def pump_alerts(self):
        for a in self.ses.pop_alerts():
            if isinstance(a, lt.save_resume_data_alert):
                iid = self._id_of(a.handle)
                if iid and self.resume_cb:
                    self.resume_cb(iid, lt.write_resume_data_buf(a.params))
            elif isinstance(a, lt.metadata_received_alert):
                iid = self._id_of(a.handle)
                if iid:
                    self.request_resume_data(iid)
            elif isinstance(a, (lt.torrent_error_alert, lt.file_error_alert)):
                iid = self._id_of(a.handle)
                if iid and self.error_cb:
                    self.error_cb(iid, a.message())

    def status(self, item_id):
        h = self.handles.get(item_id)
        if not h or not h.is_valid():
            return None
        s = h.status()
        state = str(s.state).split(".")[-1]
        paused = bool(s.flags & lt.torrent_flags.paused)
        return {
            "name": s.name,
            "has_metadata": s.has_metadata,
            "size": s.total_wanted if s.has_metadata else None,
            "done": s.total_wanted_done,
            "progress": s.progress,
            "dl_rate": s.download_rate,
            "ul_rate": s.upload_rate,
            "peers": s.num_peers,
            "seeds": s.num_seeds,
            "uploaded": s.all_time_upload,
            "state": state,
            "state_text": STATE_TEXT.get(state, state),
            "paused": paused,
            "finished": s.is_finished or s.is_seeding,
            "error": s.errc.message() if s.errc.value() else None,
        }

    def files(self, item_id):
        h = self.handles.get(item_id)
        if not h or not h.is_valid() or not h.status().has_metadata:
            return []
        prog = h.file_progress()
        return [(p, s, pad, prog[i]) for i, (p, s, pad) in enumerate(file_list(h.torrent_file()))]

    def shutdown(self):
        self.ses.pause()

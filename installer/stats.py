"""TurboDM kullanım istatistikleri — kimseden veri toplamadan, yalnızca GitHub'ın anonim indirme sayaçlarından.

  * Kurulum dosyası indirme sayısı  → kaç kez indirildi
  * latest.json indirme sayısı      → kurulu TurboDM'ler günde en çok bir kez güncelleme denetler ve bu dosyayı
                                      indirir; günlük artışı yaklaşık "günlük aktif bilgisayar" sayısıdır.

Eski sürümler yayımlamada silindiği için sayaçları kaybolur; bu araç sayaçları stats/sayac.json'a kaydeder
(publish.ps1 silmeden önce çalıştırır) ve günlük anlık görüntüler tutar.

Kullanım:  python installer/stats.py            → özet
           python installer/stats.py --kaydet   → yalnızca sayaçları kaydet (sessiz)
"""
import json
import os
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STORE = os.path.join(ROOT, "stats", "sayac.json")
sys.path.insert(0, ROOT)


def releases(repo):
    r = subprocess.run(["gh", "api", f"repos/{repo}/releases?per_page=100"], capture_output=True, text=True,
                       encoding="utf-8")
    if r.returncode:
        raise SystemExit("GitHub'dan okunamadı: " + r.stderr.strip())
    out = {}
    for rel in json.loads(r.stdout):
        setup = sum(a["download_count"] for a in rel["assets"] if a["name"].lower().endswith(".exe"))
        checks = sum(a["download_count"] for a in rel["assets"] if a["name"] == "latest.json")
        out[rel["tag_name"]] = {"setup": setup, "checks": checks}
    return out


def load():
    try:
        with open(STORE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"surumler": {}, "gunluk": []}


def save(data):
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    tmp = STORE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STORE)


def update(repo):
    data = load()
    now = releases(repo)
    for tag, c in now.items():  # sayaçlar yalnızca artar: en büyük değer saklanır
        old = data["surumler"].get(tag, {"setup": 0, "checks": 0})
        data["surumler"][tag] = {k: max(old.get(k, 0), c[k]) for k in ("setup", "checks")}
    total_checks = sum(v["checks"] for v in data["surumler"].values())
    day = time.strftime("%Y-%m-%d")
    data["gunluk"] = [g for g in data["gunluk"] if g["gun"] != day] + [{"gun": day, "denetim": total_checks}]
    data["gunluk"] = data["gunluk"][-400:]
    save(data)
    return data


def main():
    from turbodm.appinfo import UPDATE_REPO
    data = update(UPDATE_REPO)
    if "--kaydet" in sys.argv:
        return
    s = data["surumler"]
    print(f"Toplam kurulum dosyası indirme : {sum(v['setup'] for v in s.values())}")
    for tag in sorted(s, key=lambda t: [int(x) for x in t.lstrip('v').split('.') if x.isdigit()]):
        print(f"   {tag:>8}: {s[tag]['setup']:>6} indirme   ·   {s[tag]['checks']:>6} güncelleme denetimi")
    g = data["gunluk"]
    if len(g) >= 2:
        a, b = g[-2], g[-1]
        days = max(1, (time.mktime(time.strptime(b["gun"], "%Y-%m-%d"))
                       - time.mktime(time.strptime(a["gun"], "%Y-%m-%d"))) / 86400)
        print(f"Yaklaşık günlük aktif bilgisayar: {round((b['denetim'] - a['denetim']) / days)}"
              f"   ({a['gun']} → {b['gun']} arası güncelleme denetimi artışı)")
    else:
        print("Günlük aktif bilgisayar tahmini için en az iki farklı günde ölçüm gerekir (yarın tekrar çalıştırın).")
    print("Not: sayılar yaklaşıktır (aynı kişi birden çok indirebilir; tarayıcıdan açılan bağlantılar da sayılır).")


if __name__ == "__main__":
    main()

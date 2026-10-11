"""Writes review lists for the site owner: import/stale-year-titles.csv and import/alt-text-added.csv."""
import csv, json, pathlib, re, sys

sys.stdout.reconfigure(encoding="utf-8")
root = pathlib.Path(__file__).resolve().parent.parent

# ---- titles that contain a year (titles are NOT changed automatically)
PROPOSALS = {
    "allt-du-behover-veta-om-ditt-fondsparande": ("Allt du behöver veta om ditt fondsparande", "Ta bort året, eller uppdatera texten och skriv 2026."),
    "rarewine-invest-tjana-pengar-pa-vin": ("RareWine Invest – investera i vin (omdöme)", "Året i parentesen är inaktuellt."),
    "hedgefondforvaltare-och-kanda-investerare-deras-kop-2022": ("Hedgefondförvaltare och kända investerare – deras senaste köp", "Spannet 2022–2024 beskriver vilken period datan gäller. Behåll om innehållet inte uppdateras, annars byt mot ett nytt spann."),
    "vad-du-maste-gora-for-att-spara-pengar-2022": ("Vad du måste göra för att spara pengar", "Slugen innehåller 2022 men titeln säger 2024. Slugen behålls (URL-stabilitet)."),
    "en-recension-om-kameo-2022": ("En recension av Kameo", "Slugen innehåller 2022 men titeln säger 2023. Slugen behålls."),
    "tradingview-recension-omdome-2022": ("TradingView – recension & omdöme", "Slugen innehåller 2022 men titeln säger 2024. Slugen behålls."),
    "recension-omdome-av-savelend-2022": ("Savelend – omdöme och recension", "Nuvarande titel är mycket säljande (\"Din biljett till framtida framgång!\") och har ett inaktuellt år. Slugen behålls."),
    "basta-etferna": ("Bästa ETF:erna", "Eller \"Bästa ETF:erna 2026\" om listan granskas och uppdateras."),
    "ai-investeringar": ("AI-investeringar: guide till att välja de bästa AI-aktierna", "Titeln är över 60 tecken; kortare titel visas hela i sökresultaten. Eller uppdatera till 2026."),
    "basta-fonderna-2023": ("Bästa fonderna", "Slugen innehåller 2023 men titeln säger 2024. Eller \"Bästa fonderna 2026\" efter uppdatering. Slugen behålls."),
}
KEEP = {  # year in the title is a deliberate reference to a past period: no change needed
    "borsaret-2023-vinnare-och-forlorare": "Retrospektiv om 2023: året är en del av ämnet.",
    "hur-du-valjer-ratt-konto-for-ditt-sparande-2026": "Aktuell (2026).",
}
posts = {}
for f in (root / "src/content/posts").glob("*.mdx"):
    fm = f.read_text(encoding="utf-8").split("\n---\n", 1)[0]
    g = lambda k: (re.search(rf'^{k}: "?(.*?)"?$', fm, re.M) or [None, ""])[1]
    posts[f.stem] = {"title": json.loads('"' + g("title") + '"') if g("title") else "", "updated": g("updatedDate")[:10], "pub": g("pubDate")[:10]}

rows = []
for slug, p in sorted(posts.items(), key=lambda kv: kv[1]["pub"]):
    if re.search(r"20(1|2)\d", p["title"]):
        prop, note = PROPOSALS.get(slug, ("", KEEP.get(slug, "")))
        rows.append([slug, p["title"], p["pub"], p["updated"], prop or "(behåll)", note])
with open(root / "import/stale-year-titles.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["slug (unchanged)", "current title", "published", "last modified", "proposed title", "note"])
    w.writerows(rows)
print("stale-year titles:", len(rows))

# ---- alt texts that were missing in WordPress and that I wrote
alts = json.loads((root / "scripts/alt-text.json").read_text(encoding="utf-8"))
miss = json.loads((root / "import/missing-alt.json").read_text(encoding="utf-8"))
with open(root / "import/alt-text-added.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["image", "used in", "section", "alt text added"])
    for k in sorted(alts):
        m = miss.get(k, {})
        w.writerow([k, " ".join(m.get("posts", [])), m.get("heading", ""), alts[k]])
print("alt texts:", len(alts))

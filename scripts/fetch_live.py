"""Stage (a): snapshot the rendered HTML of every post/page from the live site."""
import csv, sys, time, pathlib, urllib.request
root = pathlib.Path(__file__).resolve().parent.parent
out = root / "import" / "live"
out.mkdir(parents=True, exist_ok=True)
rows = list(csv.DictReader(open(root / "import" / "slugs.csv", encoding="utf-8-sig")))
fails = []
for r in rows:
    dest = out / f"{r['slug']}.html"
    if dest.exists() and dest.stat().st_size > 1000:
        continue
    url = f"https://investeringskunskap.se/{r['slug']}/"
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (migration snapshot)"})
            dest.write_bytes(urllib.request.urlopen(req, timeout=30).read())
            break
        except Exception as e:
            err = str(e); time.sleep(2)
    else:
        fails.append((url, err))
    time.sleep(0.3)
print("fetched", len(list(out.glob("*.html"))), "failures", fails)

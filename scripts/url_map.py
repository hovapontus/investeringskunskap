"""Old URL -> new URL map with a live status check against a locally served build.

  python -I scripts/url_map.py http://localhost:8788

Old URLs = every <loc> in the live Yoast sitemaps + root + feed + tag archives + category/tag
pagination pages discovered on the live site. Output: import/url-map.csv
"""
import csv, pathlib, re, sys, time, urllib.request, urllib.error
from urllib.parse import urlparse

sys.stdout.reconfigure(encoding="utf-8")
root = pathlib.Path(__file__).resolve().parent.parent
LOCAL = sys.argv[1].rstrip("/")
LIVE = "https://investeringskunskap.se"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def get(url, follow=True):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    if follow:
        r = urllib.request.urlopen(req, timeout=40)
        return r.status, r.read().decode("utf-8", "replace"), r.geturl()

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    opener = urllib.request.build_opener(NoRedirect)
    try:
        r = opener.open(req, timeout=40)
        return r.status, "", r.headers.get("Location")
    except urllib.error.HTTPError as e:
        return e.code, "", e.headers.get("Location")


# ---- old URLs from the live site
cache = root / "import" / "live-urls.txt"
if cache.exists():
    old = cache.read_text(encoding="utf-8").split()
else:
    old = []
    _, idx, _ = get(f"{LIVE}/sitemap_index.xml")
    for sm in re.findall(r"<loc>([^<]+)</loc>", idx):
        _, body, _ = get(sm)
        old += re.findall(r"<loc>([^<]+)</loc>", body)
        time.sleep(0.3)
    old += [f"{LIVE}/", f"{LIVE}/feed/"]
    tax = __import__("json").loads((root / "src/data/taxonomy.json").read_text(encoding="utf-8"))
    old += [f"{LIVE}/tag/{t}/" for t in tax["tags"]]
    # follow pagination on category + tag archives
    seen = set(old)
    queue = [u for u in old if "/category/" in u or "/tag/" in u]
    while queue:
        u = queue.pop()
        try:
            status, body, _ = get(u)
        except urllib.error.HTTPError:
            continue
        base = u.split("/page/")[0].rstrip("/")
        for n in set(re.findall(re.escape(base) + r"/page/(\d+)/", body)):
            nu = f"{base}/page/{n}/"
            if nu not in seen:
                seen.add(nu); old.append(nu); queue.append(nu)
        time.sleep(0.2)
    old = list(dict.fromkeys(old))
    cache.write_text("\n".join(old) + "\n", encoding="utf-8")

# ---- mapping rules (same path unless listed)
REDIRECTS = {"/hem/": "/"}
# Pages that exist only in the new site (never on live WordPress) and the redirects for removed ones
EXTRA = [("/om-sajten/", 200, "new"), ("/kontakt/", 200, "new"), ("/om-oss/", 301, "removed -> /om-sajten/"),
         ("/annonspolicy/", 301, "removed -> /om-sajten/"), ("/disclaimer/", 301, "removed -> /om-sajten/")]


def classify(path):
    if path == "/":
        return "home"
    if path == "/feed/":
        return "feed"
    if path.startswith("/category/"):
        return "category-page" if "/page/" in path else "category"
    if path.startswith("/tag/"):
        return "tag-page" if "/page/" in path else "tag"
    return "post/page"


rows, failures = [], 0
for u in sorted(set(old)):
    path = urlparse(u).path
    new_path = REDIRECTS.get(path, path)
    expected = 301 if path in REDIRECTS else 200
    status, _, loc = get(LOCAL + path, follow=False)
    ok = status == expected and (expected != 301 or (loc or "").rstrip("/").endswith(new_path.rstrip("/")))
    failures += not ok
    rows.append({"old_url": u, "type": classify(path), "new_url": "https://investeringskunskap.se" + new_path,
                 "expected_status": expected, "local_status": status, "redirect_to": loc or "", "ok": "yes" if ok else "NO"})
for path, expected, kind in EXTRA:
    status, _, loc = get(LOCAL + path, follow=False)
    ok = status == expected and (expected != 301 or (loc or "").rstrip("/").endswith("/om-sajten"))
    failures += not ok
    rows.append({"old_url": "(not on live site)", "type": kind, "new_url": "https://investeringskunskap.se" + path,
                 "expected_status": expected, "local_status": status, "redirect_to": loc or "", "ok": "yes" if ok else "NO"})
with open(root / "import" / "url-map.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
print(f"{len(rows)} old URLs, {failures} failures")
for r in rows:
    if r["ok"] != "yes":
        print("  ", r["old_url"], r["expected_status"], "->", r["local_status"], r["redirect_to"])

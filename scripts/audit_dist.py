"""Post-build audit of dist/: sitemap contents, JSON-LD validity, per-page SEO basics.
   python -I scripts/audit_dist.py"""
import collections, glob, json, pathlib, re, sys

sys.stdout.reconfigure(encoding="utf-8")
root = pathlib.Path(__file__).resolve().parent.parent
dist = root / "dist"
SITE = "https://investeringskunskap.se"

x = (dist / "sitemap-0.xml").read_text(encoding="utf-8")
paths = [u.replace(SITE, "") for u in re.findall(r"<loc>([^<]+)</loc>", x)]
print("sitemap urls:", len(paths))
print("  removed/utility pages present (should be []):", [p for p in paths if p in ("/om-oss/", "/disclaimer/", "/annonspolicy/", "/sok/", "/404/", "/hem/")])
thin = ["/tag/tesla/", "/tag/vin/", "/tag/fire/", "/tag/guld/", "/tag/podd/", "/tag/ekonomipolitik/"]
print("  one-post tags present (should be []):", [p for p in paths if p in thin])
print("  kinds:", dict(collections.Counter("tag" if p.startswith("/tag/") else "category" if p.startswith("/category/") else "root" for p in paths)))

bad, types = 0, collections.Counter()
issues = []
noindex = []
for f in sorted(glob.glob(str(dist / "**" / "index.html"), recursive=True)):
    p = "/" + pathlib.Path(f).relative_to(dist).parent.as_posix().replace(".", "")
    h = pathlib.Path(f).read_text(encoding="utf-8")
    if h.lstrip().startswith("<?xml"):
        continue  # /feed/
    for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S):
        try:
            d = json.loads(m)
            for n in d.get("@graph") or [d]:
                types[n.get("@type")] += 1
        except Exception as e:
            bad += 1
            print("bad json-ld", p, e)
    if len(re.findall(r"<h1[ >]", h)) != 1:
        issues.append((p, "h1 count", len(re.findall(r"<h1[ >]", h))))
    if not re.search(r'<meta name="description" content="[^"]{40,}', h):
        issues.append((p, "description short/missing"))
    if not re.search(r'<link rel="canonical" href="https://investeringskunskap\.se/', h):
        issues.append((p, "canonical missing"))
    t = re.search(r"<title>([^<]*)</title>", h)
    if not t or len(t.group(1)) > 75:
        issues.append((p, "title length", len(t.group(1)) if t else 0))
    if 'content="noindex' in h:
        noindex.append(p)
    for img in re.findall(r"<img\b[^>]*>", h):
        if not re.search(r"\salt(=|\s|>)", img):
            issues.append((p, "img without alt attribute"))
            break
print("json-ld types:", dict(types), "invalid:", bad)
print("noindex pages:", noindex)
print("issues:", len(issues))
for i in issues[:40]:
    print("  ", i)

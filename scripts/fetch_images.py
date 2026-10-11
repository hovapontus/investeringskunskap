"""Stage (a): download every image that is actually used (post/page content, featured images,
reusable ad blocks, live-page content areas, site logo) from the live site into src/assets/uploads/.
Prefers the full-size original (WordPress '-WxH' suffix stripped); falls back to the URL as referenced.
Writes import/images-manifest.json (url -> local file, used_by, alt, status).
"""
import json, re, sys, pathlib, time, glob, hashlib, concurrent.futures as cf
import urllib.request, urllib.error
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, unquote
from bs4 import BeautifulSoup

root = pathlib.Path(__file__).resolve().parent.parent
xml = next((root / "import").glob("*.xml"))
out = root / "src" / "assets" / "uploads"
out.mkdir(exist_ok=True)
HOST = "https://investeringskunskap.se"
UP = re.compile(r"https?://(?:www\.)?investeringskunskap\.se(/wp-content/uploads/[^\s\"'<>)]+)", re.I)


def txt(el, tag):
    for c in el:
        if c.tag.split("}")[-1] == tag:
            return c.text or ""
    return ""


def base(path):
    return re.sub(r"-\d+x\d+(?=\.\w+$)", "", path)


refs = {}  # canonical upload path -> {"used_by": set, "alts": set, "as_ref": set}


def add(path, slug, alt=None):
    path = unquote(path.split("?")[0]).replace("&amp;", "&")
    b = base(path)
    r = refs.setdefault(b, {"used_by": set(), "alts": set(), "as_ref": set()})
    r["used_by"].add(slug)
    r["as_ref"].add(path)
    if alt:
        r["alts"].add(alt)


ch = ET.parse(xml).getroot().find("channel")
items = [i for i in ch if i.tag == "item"]
by_id = {txt(i, "post_id"): i for i in items}
for it in items:
    typ, slug = txt(it, "post_type"), txt(it, "post_name")
    if typ not in ("post", "page", "wp_block"):
        continue
    enc = [c for c in it if c.tag.endswith("}encoded")]
    content = (enc[0].text or "") if enc else ""
    for tag in re.findall(r"<img\b[^>]*>", content, re.I):
        m = UP.search(tag)
        if m:
            alt = re.search(r'alt="([^"]*)"', tag)
            add(m.group(1), slug, alt.group(1) if alt else None)
    for m in re.finditer(r'href="' + UP.pattern + r'"', content, re.I):
        add(m.group(1), slug)
    # featured image
    for m in it:
        if m.tag.endswith("}postmeta") and txt(m, "meta_key") == "_thumbnail_id":
            att = by_id.get(txt(m, "meta_value"))
            if att is not None:
                mm = UP.search(txt(att, "attachment_url"))
                if mm:
                    add(mm.group(1), slug)
                    refs[base(unquote(mm.group(1)))]["featured"] = True
    # WPBakery vc_single_image image="ID"
    for att_id in re.findall(r'vc_single_image image="(\d+)"', content):
        att = by_id.get(att_id)
        if att is not None:
            mm = UP.search(txt(att, "attachment_url"))
            if mm:
                add(mm.group(1), slug)

# images that only appear in the rendered pages (content area), plus site chrome
chrome = set()
for f in glob.glob(str(root / "import" / "live" / "*.html")):
    slug = pathlib.Path(f).stem
    soup = BeautifulSoup(open(f, encoding="utf-8").read(), "lxml")
    area = soup.select_one(".entry-content, .content-inner")
    if area:
        for m in UP.finditer(str(area)):
            add(m.group(1), slug)
    if slug == "hem":
        for img in soup.select("header img, .jeg_logo img, .jeg_nav_icon img, link[rel~=icon]"):
            u = img.get("src") or img.get("data-src") or img.get("href") or ""
            m = UP.search(u)
            if m:
                chrome.add(m.group(1))
                add(m.group(1), "_site")
for m in UP.finditer(open(root / "import" / "live" / "hem.html", encoding="utf-8").read()):
    pass

print("distinct images referenced:", len(refs))


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (migration)"})
    return urllib.request.urlopen(req, timeout=60).read()


def fetch(item):
    b, info = item
    dest = out / b.replace("/wp-content/uploads/", "").lstrip("/")
    dest.parent.mkdir(parents=True, exist_ok=True)
    rec = {"file": str(dest.relative_to(root)).replace("\\", "/"), "used_by": sorted(info["used_by"]),
           "alts": sorted(info["alts"]), "featured": bool(info.get("featured")), "status": "ok", "source": None}
    if dest.exists() and dest.stat().st_size > 0:
        rec["source"] = "cache"
        return b, rec
    candidates = [b] + sorted(info["as_ref"] - {b}, key=len, reverse=True)
    err = ""
    for cand in candidates:
        for attempt in range(3):
            try:
                data = get(HOST + urllib.request.quote(cand, safe="/%:@-._~"))
                if len(data) < 100:
                    raise ValueError("tiny response")
                dest.write_bytes(data)
                rec["source"] = cand
                rec["bytes"] = len(data)
                return b, rec
            except urllib.error.HTTPError as e:
                err = f"HTTP {e.code} {cand}"
                if e.code == 404:
                    break
            except Exception as e:
                err = f"{e} {cand}"
                time.sleep(1.5)
    rec["status"] = "FAILED: " + err
    return b, rec


manifest = {}
with cf.ThreadPoolExecutor(6) as ex:
    for b, rec in ex.map(fetch, sorted(refs.items())):
        manifest[b] = rec
(root / "import" / "images-manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
ok = [k for k, v in manifest.items() if v["status"] == "ok"]
bad = {k: v["status"] for k, v in manifest.items() if v["status"] != "ok"}
print("downloaded ok:", len(ok), "failed:", len(bad))
for k, v in bad.items():
    print("  FAIL", k, v)
fallback = [k for k, v in manifest.items() if v["source"] not in (None, "cache", k)]
print("fell back to a resized variant (original missing):", fallback)

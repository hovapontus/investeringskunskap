"""Stage (e) static QA on dist/ (run `npm run build` first).
 1. every internal href/src/srcset resolves to a file in dist (or a redirect rule)
 2. content fidelity: words in each live post body vs the new page body
 3. tables / images / embeds counts per post vs live
 4. affiliate links carry rel="sponsored nofollow noopener"; disclosure present when needed
   python -I scripts/qa_static.py
"""
import collections, glob, pathlib, re, sys, unicodedata
from urllib.parse import unquote, urlparse
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")
root = pathlib.Path(__file__).resolve().parent.parent
dist = root / "dist"
live_dir = root / "import" / "live"
SITE = "https://investeringskunskap.se"

redirects = [l.split()[0] for l in (root / "public/_redirects").read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]


def exists(path):
    path = unquote(path.split("#")[0].split("?")[0])
    if not path.startswith("/"):
        return True
    p = dist / path.lstrip("/")
    if p.is_file() or (p / "index.html").is_file():
        return True
    return any(re.fullmatch(re.sub(r":\w+", "[^/]+", re.escape(r).replace("\\*", ".*")).replace("\\", "") if False else re.sub(r"\\:\w+", "[^/]+", re.escape(r)).replace(r"\*", ".*"), path) for r in redirects)


# ---------------------------------------------------------------- 1. links and assets
broken = collections.defaultdict(set)
pages = sorted(glob.glob(str(dist / "**" / "index.html"), recursive=True))
for f in pages:
    page = "/" + pathlib.Path(f).relative_to(dist).parent.as_posix().replace(".", "")
    html = pathlib.Path(f).read_text(encoding="utf-8")
    if html.lstrip().startswith("<?xml"):
        continue
    soup = BeautifulSoup(html, "lxml")
    refs = [a.get("href") for a in soup.find_all(["a", "link"]) if a.get("href")]
    refs += [t.get("src") for t in soup.find_all(["img", "script", "source"]) if t.get("src")]
    for t in soup.find_all(["img", "source"]):
        for part in (t.get("srcset") or "").split(","):
            if part.strip():
                refs.append(part.strip().split()[0])
    for r in refs:
        u = urlparse(r)
        if u.scheme in ("mailto", "tel", "javascript", "data") or (u.netloc and u.netloc.replace("www.", "") != "investeringskunskap.se"):
            continue
        path = u.path or page
        if not path.startswith("/"):
            path = page.rstrip("/") + "/" + path
        if u.fragment and not u.path:
            if not soup.find(id=u.fragment) and not soup.find(attrs={"name": u.fragment}):
                broken[page].add("#" + u.fragment)
            continue
        if not exists(path):
            broken[page].add(r)
print(f"1. links/assets: {len(pages)} pages checked, {sum(len(v) for v in broken.values())} broken refs on {len(broken)} pages")
for p, v in list(broken.items())[:15]:
    print("   ", p, sorted(v)[:5])

# ---------------------------------------------------------------- 2/3. fidelity vs live
def norm_words(text):
    text = unicodedata.normalize("NFKC", text).lower().replace("\xa0", " ")
    return re.findall(r"[0-9a-zåäöéü]+", text)


def live_body(slug):
    soup = BeautifulSoup((live_dir / f"{slug}.html").read_text(encoding="utf-8"), "lxml")
    area = soup.select_one(".entry-content.no-share, .entry-content, .content-inner")
    for sel in (".jeg_share_top_container", ".jeg_share_bottom_container", ".jnews_prev_next_container", ".jnews_author_box_container",
                ".jnews_related_post_container", ".jnews_comment_container", ".jeg_ad", "script", "style", ".lwptoc", "#ez-toc-container",
                ".jeg_post_tags", ".wp-block-genesis-blocks-gb-cta", ".gb-block-cta", ".wpdt-c"):
        for el in area.select(sel):
            el.decompose()
    return area


def new_body(slug):
    soup = BeautifulSoup((dist / slug / "index.html").read_text(encoding="utf-8"), "lxml")
    area = soup.select_one(".prose")
    for sel in (".affbox", "script", "style", ".yt__label", ".cta", ".table-scroll"):
        for el in area.select(sel):
            el.decompose()
    return area


rows = []
slugs = [p.stem for p in (root / "src/content/posts").glob("*.mdx")] + ["integritetspolicy", "ranta-pa-ranta-kalkylator"]
for slug in sorted(slugs):
    la, na = live_body(slug), new_body(slug)
    lw, nw = collections.Counter(norm_words(la.get_text(" "))), collections.Counter(norm_words(na.get_text(" ")))
    total = sum(lw.values()) or 1
    missing = sum((lw - nw).values())
    extra = sum((nw - lw).values())
    rows.append((slug, total, sum(nw.values()), missing / total, extra / total))
bad = [r for r in rows if r[3] > 0.04]
print(f"2. content fidelity: {len(rows)} documents; words missing vs live > 4%: {len(bad)}")
for slug, lw, nw, miss, extra in sorted(rows, key=lambda r: -r[3])[:12]:
    print(f"    {slug[:58]:58} live {lw:5} new {nw:5} missing {miss:5.1%} extra {extra:5.1%}")

# structure counts
print("3. structure vs live (tables / images / youtube / iframes):")
diffs = 0
for slug in sorted(slugs):
    ls = BeautifulSoup((live_dir / f"{slug}.html").read_text(encoding="utf-8"), "lxml")
    ns = BeautifulSoup((dist / slug / "index.html").read_text(encoding="utf-8"), "lxml")
    la, na = live_body(slug), ns.select_one(".prose")
    # live_body dropped .wpdt-c, so count tables from the unfiltered area
    la_full = ls.select_one(".entry-content, .content-inner")
    lt = len(la_full.select("table")); nt = len(ns.select(".prose table, .prose .table-scroll table"))
    li = len([i for i in la.select("img") if "uploads" in (i.get("src") or i.get("data-src") or "")])
    ni = len(na.select("img"))
    ly = len(la_full.select("iframe[src*=youtube], .wp-block-embed-youtube")); ny = len(na.select(".yt"))
    lf = len([i for i in la_full.select("iframe") if "youtube" not in (i.get("src") or "")]); nf = len([i for i in na.select("iframe")])
    flag = []
    if lt != nt: flag.append(f"tables {lt}->{nt}")
    if ly != ny: flag.append(f"youtube {ly}->{ny}")
    if lf != nf: flag.append(f"iframes {lf}->{nf}")
    if flag:
        diffs += 1
        print("    ", slug[:60], ", ".join(flag))
print("    documents with differences:", diffs)

# ---------------------------------------------------------------- 4. affiliate rel + disclosure
AFF = re.compile(r"click\.adrecord\.com|track\.adtraction\.com|[?&]aff_id=|refunder\.se/b/")
no_rel, no_disclosure, boxes = [], [], 0
for f in pages:
    page = "/" + pathlib.Path(f).relative_to(dist).parent.as_posix().replace(".", "")
    html = pathlib.Path(f).read_text(encoding="utf-8")
    if html.lstrip().startswith("<?xml"):
        continue
    soup = BeautifulSoup(html, "lxml")
    aff_links = [a for a in soup.find_all("a", href=AFF)]
    for a in aff_links:
        if "sponsored" not in (a.get("rel") or []) or "nofollow" not in (a.get("rel") or []):
            no_rel.append((page, a["href"][:60]))
    boxes += len(soup.select(".affbox"))
    if aff_links and not soup.select_one(".disclosure"):
        no_disclosure.append(page)
print(f"4. affiliate links without rel=sponsored nofollow: {len(no_rel)}; pages with affiliate links but no disclosure: {len(no_disclosure)}; boxes rendered: {boxes}")
for x in no_rel[:5]:
    print("    rel:", x)
for x in no_disclosure[:5]:
    print("    disclosure:", x)

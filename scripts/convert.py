"""Stage (b): convert the WordPress export into MDX content collections.

  python -I scripts/convert.py

Inputs : import/*.xml, import/tables/, import/images-manifest.json, import/seo_live.json,
         scripts/alt-text.json (hand-written alt text for images that had none)
Outputs: src/content/posts/*.mdx, src/content/pages/*.mdx, src/data/affiliate-boxes.json,
         import/conversion-report.json
Body conventions (MDX components are mapped in src/lib/mdx-components.ts):
  <Figure src alt caption/>, <HtmlTable html/>, <AffiliateBox id/>, <CtaButton/>, <ProsCons/>,
  <YouTube id/>, <Embed src/>, <CompoundCalculator/>
"""
import json, re, sys, pathlib, html as htmllib, collections
import xml.etree.ElementTree as ET
from urllib.parse import unquote, urlparse
from bs4 import BeautifulSoup, NavigableString, Comment, Tag

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = "investeringskunskap.se"
xml_path = next((ROOT / "import").glob("*.xml"))
TABLES = json.loads((ROOT / "import/tables/index.json").read_text(encoding="utf-8"))
MANIFEST = json.loads((ROOT / "import/images-manifest.json").read_text(encoding="utf-8"))
MANIFEST_KEYS = {k.replace("/wp-content/uploads/", "") for k in MANIFEST}
SEO = json.loads((ROOT / "import/seo_live.json").read_text(encoding="utf-8"))
ALT_FILE = ROOT / "scripts/alt-text.json"
ALT = json.loads(ALT_FILE.read_text(encoding="utf-8")) if ALT_FILE.exists() else {}
STALE_SLUGS = {"starta-eget-sparande": "borja-investera-vagen-till-rikedom", "kopa-guld-en-guide": "investera-i-guld"}

# ---------------------------------------------------------------- XML
ch = ET.parse(xml_path).getroot().find("channel")


def txt(el, tag):
    for c in el:
        if c.tag.split("}")[-1] == tag:
            return c.text or ""
    return ""


ITEMS = {}
for it in ch:
    if it.tag != "item":
        continue
    enc = [c for c in it if c.tag.endswith("}encoded")]
    d = {k: txt(it, k) for k in ("post_id", "post_type", "post_name", "title", "status", "post_date", "post_date_gmt",
                                  "post_modified_gmt", "creator", "attachment_url")}
    d["content"] = (enc[0].text or "") if enc else ""
    d["meta"] = {txt(m, "meta_key"): txt(m, "meta_value") for m in it if m.tag.endswith("}postmeta")}
    d["cats"] = [(c.get("nicename"), c.text) for c in it if c.tag == "category" and c.get("domain") == "category"]
    d["tags"] = [(c.get("nicename"), c.text) for c in it if c.tag == "category" and c.get("domain") == "post_tag"]
    ITEMS[d["post_id"]] = d
CAT_ID = {txt(c, "term_id"): txt(c, "category_nicename") for c in ch if c.tag.endswith("}category")}
TAG_ID = {txt(c, "term_id"): txt(c, "tag_slug") for c in ch if c.tag.endswith("}tag")}

report = collections.defaultdict(list)

# ---------------------------------------------------------------- helpers
UP = re.compile(r"https?://(?:www\.)?" + re.escape(SITE) + r"(/wp-content/uploads/[^\s\"'<>)]+)", re.I)


def upload_key(url):
    """'https://…/wp-content/uploads/2022/09/x-300x200.jpg' -> '2022/09/x.jpg' (manifest key without prefix)."""
    m = UP.search(url or "")
    if not m:
        return None
    p = unquote(m.group(1).split("?")[0])
    p = re.sub(r"-\d+x\d+(?=\.\w+$)", "", p)
    return p.replace("/wp-content/uploads/", "")


def escape_text(s):
    s = s.replace("\xa0", " ").replace("​", "")
    s = re.sub(r"\s+", " ", s)
    s = s.replace("\\", "\\\\")
    s = re.sub(r"([*_`\[\]<>{}~|])", r"\\\1", s)
    s = re.sub(r"&(?=[#\w]+;)", r"\\&", s)
    return s


def line_start_escape(s):
    s = re.sub(r"^(\s*)([#>+\-])(?=\s|$)", lambda m: m.group(1) + "\\" + m.group(2), s)
    return re.sub(r"^(\s*\d+)([.)])(?=\s|$)", lambda m: m.group(1) + "\\" + m.group(2), s)


def norm_href(href):
    href = (href or "").strip().replace("&amp;", "&")
    m = re.match(r"https?://(?:www\.)?" + re.escape(SITE) + r"(/[^?#]*)?(\?[^#]*)?(#.*)?$", href, re.I)
    if m:
        path = m.group(1) or "/"
        if "/wp-content/uploads/" in path:
            return None  # link to a media file: drop the link
        parts = path.strip("/").split("/")
        if parts and parts[-1] in STALE_SLUGS:
            path = "/" + STALE_SLUGS[parts[-1]] + "/"
            report["stale_internal_links_rewritten"].append(href)
        return path + (m.group(3) or "")
    return href


def md_link(text, href):
    if href is None:
        return text
    if re.search(r"[\s()<>]", href):
        href = "<" + href.replace("<", "%3C").replace(">", "%3E") + ">"
    return f"[{text}]({href})"


def style_px(el, prop="width"):
    m = re.search(prop + r":\s*(\d+)px", el.get("style", "") if el else "")
    return int(m.group(1)) if m else None


BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "blockquote", "figure", "table", "hr",
              "iframe", "section", "header", "article", "details", "pre", "figcaption", "img", "script", "style",
              "wpx-table", "wpx-box", "wpx-calc"}


class Ctx:
    def __init__(self, slug):
        self.slug = slug
        self.boxes = {}      # id -> box dict created while converting this document
        self.cta_n = 0
        self.has_affiliate = False
        self.images = []


BOXES = {}  # global affiliate box registry (written to src/data/affiliate-boxes.json)


# ---------------------------------------------------------------- inline
def inline(node, ctx, in_heading=False):
    out = []
    for ch_ in node.children:
        if isinstance(ch_, Comment):
            continue
        if isinstance(ch_, NavigableString):
            out.append(escape_text(str(ch_)))
            continue
        n = ch_.name
        if n in ("script", "style"):
            continue
        if n == "br":
            out.append("<br />")
        elif n in ("strong", "b", "em", "i"):
            inner = inline(ch_, ctx, in_heading)
            if in_heading or not inner.strip():
                out.append(inner)
                continue
            mark = "**" if n in ("strong", "b") else "*"
            lead = inner[: len(inner) - len(inner.lstrip())]
            trail = inner[len(inner.rstrip()):]
            core = inner.strip()
            out.append(f"{lead}{mark}{core}{mark}{trail}")
        elif n in ("del", "s", "strike"):
            inner = inline(ch_, ctx, in_heading)
            out.append(f"~~{inner.strip()}~~" if inner.strip() else "")
        elif n == "code":
            out.append("`" + ch_.get_text().replace("`", "'") + "`")
        elif n in ("sup", "sub"):
            out.append(f"<{n}>{inline(ch_, ctx, in_heading)}</{n}>")
        elif n == "a":
            text = inline(ch_, ctx, in_heading)
            if not text.strip():
                continue
            href = norm_href(ch_.get("href", ""))
            if href and ctx is not None:
                pass
            lead = text[: len(text) - len(text.lstrip())]
            trail = text[len(text.rstrip()):]
            out.append(lead + md_link(text.strip(), href) + trail)
        elif n == "img":
            out.append("")  # block-level handler deals with images
        elif n in ("wpx-table", "wpx-box", "wpx-calc"):
            out.append("")
        else:  # span, mark, u, small, font ...
            out.append(inline(ch_, ctx, in_heading))
    return "".join(out)


# ---------------------------------------------------------------- components
def jsx_s(v):
    """String prop as a JS expression: attr={"..."} (JSX attribute strings have no escape sequences)."""
    return "{" + json.dumps(v, ensure_ascii=False) + "}"


def jsx_str(v):
    return json.dumps(v, ensure_ascii=False)


def figure(img, ctx, caption="", href=None, caption_href=None):
    src = img.get("src") or img.get("data-src") or img.get("data-nitro-lazy-src") or ""
    key = upload_key(src)
    if not key or key not in MANIFEST_KEYS:
        report["image_not_in_manifest"].append((ctx.slug, src))
        return ""
    alt = (img.get("alt") or "").strip()
    if not alt:
        alt = ALT.get(key, "")
        if not alt:
            report["missing_alt"].append((key, ctx.slug))
        else:
            report["alt_filled"].append((key, ctx.slug))
    ctx.images.append(key)
    w = img.get("width") or style_px(img, "width")
    props = f"src={jsx_s(key)} alt={jsx_s(alt)}"
    if caption:
        props += f" caption={jsx_s(caption)}"
        if caption_href and norm_href(caption_href):
            props += f" captionHref={jsx_s(norm_href(caption_href))}"
    if w and str(w).isdigit():
        props += f" displayWidth={{{w}}}"
    if href and not href.startswith("/wp-content") and norm_href(href):
        props += f" href={jsx_s(norm_href(href))}"
    return f"<Figure {props} />"


def parse_cta(el, ctx):
    """Genesis CTA / cover+buttons affiliate box -> dict."""
    h = str(el)
    img = el.find("img")
    box = {"logo": upload_key(img.get("src")) if img else None,
           "logoWidth": style_px(img, "width") if img else None,
           "logoAlt": (img.get("alt") or "").strip() if img else ""}
    a = el.select_one("a.gb-button, a.wp-block-button__link, .gb-cta-button a")
    if a is None:
        cand = [x for x in el.find_all("a") if x.get_text(strip=True)]
        a = cand[-1] if cand else None
    box["href"] = (a.get("href") or "").replace("&amp;", "&") if a else ""
    box["label"] = a.get_text(" ", strip=True) if a else "Läs mer"
    m = re.search(r"background-color:\s*(#[0-9a-fA-F]{3,8})", str(a) if a else "")
    box["color"] = m.group(1) if m else "#3373dc"
    bullets = []
    for p in el.find_all("p"):
        if a is not None and a in p.find_all("a") and p.get_text(strip=True) == a.get_text(strip=True):
            continue
        html = str(p).replace("<br>", "\n").replace("<br/>", "\n")
        for line in BeautifulSoup(html, "lxml").get_text().split("\n"):
            line = re.sub(r"^[\s ✅•·\-–✔️]+", "", line).strip()
            if line:
                bullets.append(line)
    box["bullets"] = bullets
    title = ""
    hd = el.find(["h2", "h3", "h4"])
    if hd is not None and not hd.find("img"):
        title = hd.get_text(" ", strip=True)
    box["title"] = title
    return box


def register_box(box, ctx, preferred_id=None):
    sig = json.dumps(box, sort_keys=True, ensure_ascii=False)
    for bid, b in BOXES.items():
        if json.dumps(b, sort_keys=True, ensure_ascii=False) == sig:
            return bid
    if preferred_id and preferred_id not in BOXES:
        bid = preferred_id
    else:
        ctx.cta_n += 1
        bid = f"{ctx.slug}-cta-{ctx.cta_n}"[:80]
    BOXES[bid] = box
    return bid


def table_component(key):
    rec = TABLES.get(key)
    if not rec:
        return None
    h = (ROOT / "import/tables" / rec["file"]).read_text(encoding="utf-8")
    return f"<HtmlTable html={{{jsx_str(h)}}} />"


# ---------------------------------------------------------------- blocks
def flow(node, ctx, depth=0):
    """Walk the children of a container; yield MDX block strings."""
    buf = []

    def flush():
        if not buf:
            return []
        wrapper = BeautifulSoup("<div></div>", "lxml").div
        for b in buf:
            wrapper.append(b.extract() if isinstance(b, Tag) else NavigableString(str(b)))
        buf.clear()
        s = inline(wrapper, ctx).strip()
        s = re.sub(r"(<br />\s*)+$", "", s).strip()
        s = re.sub(r"^(<br />\s*)+", "", s).strip()
        return [line_start_escape(s)] if s and s != "\\" else []

    for c in list(node.children):
        if isinstance(c, Comment):
            continue
        if isinstance(c, NavigableString):
            buf.append(str(c))
            continue
        n = c.name
        if n in ("script", "style"):
            continue
        if n == "p":
            yield from flush()
            yield from flow(c, ctx, depth)
        elif n in BLOCK_TAGS or n.startswith("wpx-"):
            yield from flush()
            yield from block(c, ctx, depth)
        else:
            buf.append(c)
    yield from flush()


def cls(el):
    return " ".join(el.get("class", []))


def block(el, ctx, depth):
    n, c = el.name, cls(el)
    if n == "wpx-table":
        t = table_component(el["key"])
        if t is None:
            report["table_missing"].append((ctx.slug, el["key"]))
        else:
            yield t
    elif n == "wpx-box":
        ctx.has_affiliate = True
        yield f'<AffiliateBox id="{el["id"]}" />'
    elif n == "wpx-calc":
        yield "<CompoundCalculator />"
    elif re.fullmatch(r"h[1-6]", n):
        level = max(2, int(n[1]))
        text = inline(el, ctx, in_heading=True).strip()
        text = re.sub(r"(<br />\s*)+$", "", text).strip()
        if text:
            yield "#" * level + " " + line_start_escape(text)
    elif n in ("ul", "ol"):
        if "affiliate-block-advanced-list" in c:
            return
        yield from lst(el, ctx, depth)
    elif n == "blockquote":
        inner = list(flow_q(el, ctx))
        if inner:
            yield "\n".join("> " + l if l else ">" for l in "\n\n".join(inner).split("\n"))
    elif n == "hr":
        yield "---"
    elif n == "img":
        f = figure(el, ctx)
        if f:
            yield f
    elif n == "iframe":
        src = el.get("src", "")
        if src:
            yield embed(src, el, ctx)
    elif n == "figure":
        yield from fig(el, ctx, depth)
    elif n == "table":
        yield f"<HtmlTable html={{{jsx_str(clean_native_table(el))}}} />"
    elif n == "li":
        yield from flow(el, ctx, depth)
    elif n == "figcaption":
        return
    elif n == "div" or n in ("section", "header", "article"):
        if "wp-block-spacer" in c or "wpb_wrapper" in c and not el.get_text(strip=True):
            return
        if "wp-block-affiliate-booster-propsandcons" in c:
            yield pros_cons(el)
            return
        if "gb-block-cta" in c and ("wp-block-cover" in c or "wp-block-genesis-blocks-gb-cta" in c):
            box = parse_cta(el, ctx)
            if box["href"]:
                ctx.has_affiliate = True
                yield f'<AffiliateBox id="{register_box(box, ctx)}" />'
            return
        if "wp-block-buttons" in c:
            for a in el.find_all("a"):
                href = (a.get("href") or "").replace("&amp;", "&")
                m = re.search(r"background-color:\s*(#[0-9a-fA-F]{3,8})", a.get("style", ""))
                yield f'<CtaButton href={jsx_s(norm_href(href))} label={jsx_s(a.get_text(" ", strip=True))} color={jsx_s(m.group(1) if m else "#3373dc")} />'
            return
        if "wp-block-embed" in c:
            yield from fig(el, ctx, depth)
            return
        if "entry-title" in c:
            return
        yield from flow(el, ctx, depth)
    elif n == "pre":
        yield "```\n" + el.get_text() + "\n```"
    else:
        yield from flow(el, ctx, depth)


def flow_q(el, ctx):
    cite = el.find("cite")
    if cite is not None:
        cite.extract()
    yield from flow(el, ctx)
    if cite is not None:
        yield "— " + inline(cite, ctx).strip()


def lst(el, ctx, depth):
    ordered = el.name == "ol"
    start = int(el.get("start", 1)) if ordered and str(el.get("start", "1")).isdigit() else 1
    lines = []
    i = start
    for li in el.find_all("li", recursive=False):
        blocks = list(flow(li, ctx, depth + 1))
        if not blocks:
            continue
        marker = f"{i}. " if ordered else "- "
        pad = " " * len(marker)
        first = blocks[0].split("\n")
        body = [marker + first[0]] + [pad + l if l else l for l in first[1:]]
        for b in blocks[1:]:
            body.append("")
            body += [pad + l if l else l for l in b.split("\n")]
        lines.append("\n".join(body))
        i += 1
    if lines:
        yield "\n".join(lines)


def embed(src, el, ctx):
    m = re.search(r"(?:youtube\.com/(?:watch\?v=|embed/)|youtu\.be/)([\w-]{11})", src)
    if m:
        return f'<YouTube id="{m.group(1)}" />'
    props = f"src={jsx_s(src.replace('&amp;', '&'))}"
    h = el.get("height")
    wrap = el.find_parent("div")
    pt = re.search(r"padding-top:\s*([\d.]+)%", wrap.get("style", "")) if wrap else None
    if pt and float(pt.group(1)) > 0:  # responsive wrapper from Canva: padding-top = height/width
        props += f" ratio={{{round(100 / float(pt.group(1)), 4)}}}"
    elif h and str(h).isdigit():
        props += f" height={{{h}}}"
    elif style_px(el, "height"):
        props += f" height={{{style_px(el, 'height')}}}"
    return f"<Embed {props} />"


def fig(el, ctx, depth):
    c = cls(el)
    if "wp-block-embed" in c:
        t = el.get_text(" ", strip=True)
        m = re.search(r"(?:youtube\.com/(?:watch\?v=|embed/)|youtu\.be/)([\w-]{11})", t)
        if m:
            yield f'<YouTube id="{m.group(1)}" />'
        else:
            url = re.search(r"https?://\S+", t)
            if url:
                yield md_link(escape_text(url.group(0)), url.group(0))
        return
    if el.find("table"):
        t = el.find("table")
        yield f"<HtmlTable html={{{jsx_str(clean_native_table(t))}}} />"
        return
    img = el.find("img")
    cap_el = el.find("figcaption")
    caption = re.sub(r"\s+", " ", cap_el.get_text(" ", strip=True).replace(" ", " ")) if cap_el else ""
    cap_link = cap_el.find("a") if cap_el else None
    if img is None:
        yield from flow(el, ctx, depth)
        return
    a = img.find_parent("a")
    f = figure(img, ctx, caption, a.get("href") if a else None, cap_link.get("href") if cap_link else None)
    if f:
        yield f


def clean_native_table(t):
    import copy
    t = BeautifulSoup(str(t), "lxml").table
    t.attrs = {}
    for tag in t.find_all(True):
        if tag.name in ("thead", "tbody", "tr", "th", "td"):
            tag.attrs = {k: v for k, v in tag.attrs.items() if k in ("colspan", "rowspan") and v != "1"}
        elif tag.name in ("a", "strong", "em", "br", "sup"):
            tag.attrs = {k: v for k, v in tag.attrs.items() if k == "href"}
        else:
            tag.unwrap()
    return re.sub(r"\s+", " ", str(t).replace("\xa0", " "))


def pros_cons(el):
    def items(sel):
        box = el.select_one(sel)
        if box is None:
            return [], ""
        title = box.select_one("p").get_text(" ", strip=True) if box.select_one("p") else ""
        return [li.get_text(" ", strip=True) for li in box.find_all("li")], title
    pros, pt = items(".affiliate-props-list")
    cons, ct = items(".affiliate-cons-list")
    return f"<ProsCons pros={{{jsx_str(pros)}}} cons={{{jsx_str(cons)}}} prosTitle={jsx_s(pt or 'Fördelar')} consTitle={jsx_s(ct or 'Nackdelar')} />"


# ---------------------------------------------------------------- shortcode / block prep
def prep(content, slug):
    c = content
    # reusable blocks (affiliate boxes) -> marker element
    def blk(m):
        ref = json.loads(m.group(1))["ref"]
        b = ITEMS.get(str(ref))
        return f'<wpx-box id="{b["post_name"]}"></wpx-box>' if b else ""
    c = re.sub(r"<!-- wp:block (\{[^}]*\}) /-->", blk, c)
    # wpDataTables / WP Table Builder
    wptb_i = [0]

    def tab(m):
        kind, tid = m.group(1), m.group(2)
        if kind == "wpdatatable":
            return f'<wpx-table key="{slug}:wpdt:{tid}"></wpx-table>'
        wptb_i[0] += 1
        return f'<wpx-table key="{slug}:wptb:{[k for k in TABLES if k.startswith(slug + ":wptb:")][wptb_i[0]-1].split(":")[2]}"></wpx-table>'
    c = re.sub(r"\[(wpdatatable|wptb) id=(\d+)\]", tab, c)
    c = re.sub(r"\[Calculator id='?\d+'?\]", "<wpx-calc></wpx-calc>", c)
    c = re.sub(r"\[rtoc_mokuji[^\]]*\]", "", c)
    c = re.sub(r"<!-- wp:luckywp/tableofcontents /-->", "", c)
    return c


def convert_body(content, slug):
    ctx = Ctx(slug)
    soup = BeautifulSoup(prep(content, slug), "lxml")
    root = soup.body or soup
    blocks = [b for b in flow(root, ctx) if b and b.strip()]
    return "\n\n".join(blocks) + "\n", ctx


# ---------------------------------------------------------------- affiliate blocks from wp_block items
for it in ITEMS.values():
    if it["post_type"] == "wp_block":
        ctx = Ctx(it["post_name"])
        soup = BeautifulSoup(it["content"], "lxml")
        el = soup.select_one(".gb-block-cta") or soup.body
        box = parse_cta(el, ctx)
        BOXES[it["post_name"]] = box
        box["source"] = it["title"]

# ---------------------------------------------------------------- front matter
def yaml_val(v):
    return json.dumps(v, ensure_ascii=False)


def front_matter(d):
    lines = ["---"]
    for k, v in d.items():
        if v is None or v == "" or v == []:
            continue
        lines.append(f"{k}: {yaml_val(v)}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def iso(s):
    return s.replace(" ", "T") + "Z" if s and not s.startswith("0000") else None


def featured_alt(it):
    tid = it["meta"].get("_thumbnail_id")
    att = ITEMS.get(tid) if tid else None
    return (att["meta"].get("_wp_attachment_image_alt") or "").strip() if att else ""


def featured(it):
    tid = it["meta"].get("_thumbnail_id")
    att = ITEMS.get(tid) if tid else None
    key = upload_key(att["attachment_url"]) if att else None
    if key and key.lower().endswith(".pdf"):  # WordPress shows the generated preview image of a PDF attachment
        preview = key[:-4] + "-pdf.jpg"
        if preview in MANIFEST_KEYS:
            report["featured_pdf_replaced_with_preview"].append((key, preview))
            return preview
    return key


def resolve_title(slug, wp_title):
    live = SEO.get(slug, {}).get("title")
    default = f"{wp_title} | Investeringskunskap"
    live = htmllib.unescape(live or "")
    norm = lambda s: re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()
    if not live or norm(live) == norm(default):
        return None
    return norm(live)


OUT_POSTS = ROOT / "src/content/posts"
OUT_PAGES = ROOT / "src/content/pages"
OUT_POSTS.mkdir(parents=True, exist_ok=True)
OUT_PAGES.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- posts
n_posts = 0
for it in sorted(ITEMS.values(), key=lambda x: x["post_date"]):
    if it["post_type"] != "post" or it["status"] != "publish":
        continue
    slug = it["post_name"]
    body, ctx = convert_body(it["content"], slug)
    live = SEO.get(slug, {})
    author = re.sub(r"^Av\s+", "", live.get("author") or "") or it["creator"]
    if it["creator"] != author:
        report["author_differs_xml_vs_live"].append((slug, it["creator"], author))
    desc = htmllib.unescape(live.get("desc") or it["meta"].get("_yoast_wpseo_metadesc") or "")
    if not desc:
        report["no_description"].append(slug)
    prim = CAT_ID.get(it["meta"].get("_yoast_wpseo_primary_category", ""), None)
    cats = [s for s, _ in it["cats"]]
    if prim == "okategoriserat" and len(cats) > 1:  # "Uncategorized" makes a poor breadcrumb/primary category
        prim = next(c for c in cats if c != "okategoriserat")
    d = {
        "title": htmllib.unescape(it["title"]).replace("\xa0", " ").strip(),
        "description": desc.strip(),
        "pubDate": iso(it["post_date_gmt"]),
        "updatedDate": iso(it["post_modified_gmt"]),
        "author": author,
        "categories": cats,
        "primaryCategory": prim if prim in cats else (cats[0] if cats else None),
        "tags": [s for s, _ in it["tags"]],
        "image": featured(it),
        "imageAlt": featured_alt(it) or htmllib.unescape(it["title"]).replace(" ", " ").strip(),
        "seoTitle": resolve_title(slug, htmllib.unescape(it["title"]).replace("\xa0", " ").strip()),
        "focusKeyword": it["meta"].get("_yoast_wpseo_focuskw") or None,
        "wpId": int(it["post_id"]),
    }
    if d["image"] is None:
        report["post_without_featured_image"].append(slug)
    (OUT_POSTS / f"{slug}.mdx").write_text(front_matter(d) + body, encoding="utf-8")
    n_posts += 1
    if ctx.has_affiliate:
        report["posts_with_affiliate_boxes"].append(slug)

# ---------------------------------------------------------------- pages
HANDWRITTEN = {"samarbetspartners"}  # rewritten by hand; the converter must not overwrite them
PAGE_LAYOUT = {"aktier": ("landing", "aktier", None), "fonder": ("landing", "fonder", None),
               "kryptovaluta": ("landing", "krypto", None), "privatekonomi": ("landing", "privatekonomi", None),
               "alternativa-investeringar": ("landing", "alternativa-investeringar", None),
               "tips": ("landing", "tips", None), "guld-och-ravaror": ("landing", None, "guld"),
               "nyborjarguider": ("landing", None, None), "senaste-inlaggen": ("latest", None, None),
               "hem": ("home", None, None)}
for it in sorted(ITEMS.values(), key=lambda x: x["post_name"]):
    if it["post_type"] != "page" or it["status"] != "publish":
        continue
    slug = it["post_name"]
    if slug in HANDWRITTEN:
        continue
    live = SEO.get(slug, {})
    c = it["content"]
    layout, cat, tag = PAGE_LAYOUT.get(slug, ("default", None, None))
    d = {"title": htmllib.unescape(it["title"]).strip(), "description": htmllib.unescape(live.get("desc") or "").strip(),
         "template": layout, "category": cat, "tag": tag, "wpId": int(it["post_id"]),
         "seoTitle": resolve_title(slug, htmllib.unescape(it["title"]).strip()),
         "updatedDate": iso(it["post_modified_gmt"])}
    if layout in ("landing", "home", "latest") or slug in ("samarbetspartners",):
        hero = re.search(r'vc_single_image image="(\d+)"', c)
        if hero and ITEMS.get(hero.group(1)):
            d["heroImage"] = upload_key(ITEMS[hero.group(1)]["attachment_url"])
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", c, re.S)
        if h1:
            d["heading"] = BeautifulSoup(h1.group(1), "lxml").get_text().strip()
        m = re.search(r'include_category="([\d,]+)"', c)
        mt = re.search(r'include_tag="([\d,]+)"', c)
    c2 = re.sub(r"\[/?(?:vc_|jnews_)[^\]]*\]", "", c)
    if layout in ("landing", "home", "latest"):
        c2 = re.sub(r"<h1[^>]*>.*?</h1>", "", c2, flags=re.S)
    if slug == "ranta-pa-ranta-kalkylator":
        d["template"] = "calculator"
    body, ctx = convert_body(c2, slug)
    (OUT_PAGES / f"{slug}.mdx").write_text(front_matter({k: v for k, v in d.items() if v is not None}) + body, encoding="utf-8")

# ---------------------------------------------------------------- data + report
(ROOT / "src/data").mkdir(parents=True, exist_ok=True)
(ROOT / "src/data/affiliate-boxes.json").write_text(json.dumps(BOXES, indent=1, ensure_ascii=False), encoding="utf-8")
# taxonomy names/counts for the site (categories, tags)
cat_count, tag_count = collections.Counter(), collections.Counter()
for it in ITEMS.values():
    if it["post_type"] == "post" and it["status"] == "publish":
        cat_count.update(s_ for s_, _ in it["cats"])
        tag_count.update(s_ for s_, _ in it["tags"])
tax = {"categories": {}, "tags": {}}
for c in ch:
    if c.tag.endswith("}category"):
        slug = txt(c, "category_nicename")
        tax["categories"][slug] = {"name": txt(c, "cat_name"), "parent": txt(c, "category_parent") or None, "count": cat_count[slug]}
    elif c.tag.endswith("}tag"):
        slug = txt(c, "tag_slug")
        tax["tags"][slug] = {"name": txt(c, "tag_name"), "count": tag_count[slug]}
(ROOT / "src/data/taxonomy.json").write_text(json.dumps(tax, indent=1, ensure_ascii=False), encoding="utf-8")

rep = {k: v for k, v in report.items()}
rep["posts_converted"] = n_posts
rep["affiliate_boxes"] = len(BOXES)
(ROOT / "import/conversion-report.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False, default=list), encoding="utf-8")
for k, v in rep.items():
    print(k, len(v) if isinstance(v, list) else v)

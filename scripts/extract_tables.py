"""Stage (a): pull the plugin-rendered tables (wpDataTables / WP Table Builder / native)
out of the live snapshots and save them as clean semantic HTML under import/tables/.
Index: import/tables/index.json maps "<slug>:<kind>:<id>" -> file.
"""
import json, pathlib, re, glob
from bs4 import BeautifulSoup

root = pathlib.Path(__file__).resolve().parent.parent
out = root / "import" / "tables"
out.mkdir(exist_ok=True)
for old in out.glob("*.html"):  # regenerate cleanly
    old.unlink()
index, report = {}, []


def clean(table):
    """Semantic table HTML: thead/tbody, th/td, inline formatting + links only."""
    table = BeautifulSoup(str(table), "lxml").table
    table.attrs = {}
    for tag in table.find_all(True):
        if tag.name in ("table", "thead", "tbody", "tr", "th", "td"):
            tag.attrs = {k: v for k, v in tag.attrs.items() if k in ("colspan", "rowspan") and v != "1"}
        elif tag.name in ("a", "strong", "b", "em", "i", "br", "img", "sup"):
            tag.attrs = {k: v for k, v in tag.attrs.items() if k in ("href", "src", "alt", "rel", "target")}
        else:
            tag.unwrap()
    for tag in table.find_all(["b", "i"]):
        tag.name = "strong" if tag.name == "b" else "em"
    html = re.sub(r"\s+", " ", str(table).replace("\xa0", " "))
    html = re.sub(r"<br/>\s*(?=</t[dh]>)", "", html)
    html = re.sub(r"(<t[dh][^>]*>) +| +(</t[dh]>)", lambda m: m.group(1) or m.group(2), html)
    return html.replace("</tr>", "</tr>\n").replace("<tbody>", "<tbody>\n").replace("</thead>", "</thead>\n")


for f in sorted(glob.glob(str(root / "import" / "live" / "*.html"))):
    slug = pathlib.Path(f).stem
    soup = BeautifulSoup(open(f, encoding="utf-8").read(), "lxml")
    scope = soup.select_one(".entry-content, .content-inner, article") or soup
    seen, n_wptb = set(), 0
    for i, tb in enumerate(scope.find_all("table")):
        cls = " ".join(tb.get("class", []))
        m = re.search(r"wpdtSimpleTable-(\d+)", tb.get("id", ""))
        w = re.search(r"table_setting-(\d+)", cls)
        kind, sid = ("wpdt", m.group(1)) if m else (("wptb", w.group(1)) if w else ("native", str(i)))
        html = clean(tb)
        if html in seen:
            report.append(f"{slug}: duplicate {kind}-{sid} skipped")
            continue
        seen.add(html)
        if kind == "wptb":
            n_wptb += 1
            sid = f"{sid}-{n_wptb}"
        fn = f"{slug}__{kind}-{sid}.html"
        (out / fn).write_text(html, encoding="utf-8")
        index[f"{slug}:{kind}:{sid}"] = {"file": fn, "rows": len(tb.find_all("tr"))}
(out / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")
print(len(index), "tables")
print("\n".join(report))

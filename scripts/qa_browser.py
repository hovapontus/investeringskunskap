"""Stage (e) browser QA against a running build (wrangler dev or astro preview).
   python scripts/qa_browser.py http://localhost:8788
Per page and viewport (390 / 1366): console errors, failed requests, horizontal overflow,
images that did not load; axe-core accessibility violations (serious/critical) on all pages at 1366."""
import collections, json, pathlib, re, sys
from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
root = pathlib.Path(__file__).resolve().parent.parent
sitemap = (root / "dist" / "sitemap-0.xml").read_text(encoding="utf-8")
paths = [u.replace("https://investeringskunskap.se", "") for u in re.findall(r"<loc>([^<]+)</loc>", sitemap)]
paths += ["/sok/", "/om-oss/", "/kontakt/", "/disclaimer/", "/annonspolicy/", "/tag/tesla/"]
axe_src = (root / "node_modules/axe-core/axe.min.js").read_text(encoding="utf-8")

problems = collections.defaultdict(list)
axe_hits = collections.defaultdict(lambda: collections.Counter())
with sync_playwright() as p:
    b = p.chromium.launch()
    for vw, vh in ((390, 844), (1366, 900)):
        ctx = b.new_context(viewport={"width": vw, "height": vh}, locale="sv-SE")
        pg = ctx.new_page()
        bad_req, errs = [], []
        pg.on("response", lambda r: bad_req.append((r.status, r.url)) if r.status >= 400 else None)
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errs.append(str(e)))
        for path in paths:
            bad_req.clear(); errs.clear()
            pg.goto(BASE + path, wait_until="networkidle", timeout=60000)
            # scroll to trigger lazy images, then check they decoded
            pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            pg.wait_for_timeout(250)
            ov = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            broken_imgs = pg.evaluate("[...document.images].filter(i => i.complete && i.naturalWidth === 0 && i.currentSrc).map(i => i.currentSrc)")
            if ov > 1: problems[path].append(f"{vw}px horizontal overflow {ov}px")
            if bad_req: problems[path].append(f"{vw}px failed requests {bad_req[:3]}")
            if errs: problems[path].append(f"{vw}px console errors {errs[:2]}")
            if broken_imgs: problems[path].append(f"{vw}px broken images {broken_imgs[:2]}")
            if vw == 1366:
                pg.add_script_tag(content=axe_src)
                res = pg.evaluate("axe.run(document, {runOnly: ['wcag2a','wcag2aa','wcag21aa','best-practice']}).then(r => r.violations.map(v => ({id: v.id, impact: v.impact, n: v.nodes.length, sample: v.nodes[0].target.join(' ')})))")
                for v in res:
                    if v["impact"] in ("serious", "critical"):
                        axe_hits[v["id"]][path] = (v["n"], v["sample"])
        ctx.close()
    b.close()

print(f"{len(paths)} pages x 2 viewports")
print("runtime problems:", len(problems))
for path, items in list(problems.items())[:25]:
    print("  ", path, items)
print("axe serious/critical rules:", {k: len(v) for k, v in axe_hits.items()})
for rule, pages in axe_hits.items():
    for path, (n, sample) in list(pages.items())[:3]:
        print(f"   {rule}: {path} ({n} nodes) e.g. {sample}")

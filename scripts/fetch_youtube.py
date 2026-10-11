"""Save thumbnails + titles of the embedded YouTube videos locally (click-to-load facade).
Writes src/assets/youtube/<id>.jpg and src/data/youtube.json."""
import glob, json, pathlib, re, sys, urllib.request, urllib.parse

sys.stdout.reconfigure(encoding="utf-8")
root = pathlib.Path(__file__).resolve().parent.parent
out = root / "src/assets/youtube"
out.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
ids = {}
for f in glob.glob(str(root / "src/content/**/*.mdx"), recursive=True):
    for m in re.finditer(r'<YouTube id="([\w-]{11})"', pathlib.Path(f).read_text(encoding="utf-8")):
        ids.setdefault(m.group(1), set()).add(pathlib.Path(f).stem)


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30).read()


meta = {}
for vid in sorted(ids):
    rec = {"title": "YouTube-video", "posts": sorted(ids[vid])}
    try:
        rec["title"] = json.loads(get("https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(f"https://www.youtube.com/watch?v={vid}", safe="")))["title"]
    except Exception as e:
        print("no oembed title for", vid, e)
    dest = out / f"{vid}.jpg"
    for name in ("maxresdefault", "hqdefault"):
        try:
            data = get(f"https://i.ytimg.com/vi/{vid}/{name}.jpg")
            if len(data) > 5000:
                dest.write_bytes(data)
                break
        except Exception as e:
            rec["thumb_error"] = str(e)
    rec["thumb"] = dest.exists()
    meta[vid] = rec
    print(vid, rec["thumb"], rec["title"][:70], rec["posts"])
(root / "src/data/youtube.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")

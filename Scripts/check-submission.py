"""Check a plugin submission (sandbox plan §7 "Submission") and print a Markdown report.

Usage: check-submission.py submissions/<id>.json [--out plugin.json]
A submission is {"repo": "https://github.com/<owner>/<name>", "tag": "<tag>"}. The release at that tag
must carry plugin.json; every layer it lists must be an asset of the same release, and match its
size and SHA-256. Its `icon`, an SVG asset of the same release, is copied in as `iconSvg` so the signed
index carries it. The rules mirror the helper's (PluginManifest.validateForStore): change both together.
Exit 0 when every check passes; --out writes the checked plugin.json for prepare-index.py --add.
"""
import hashlib, json, os, re, sys, urllib.request, xml.etree.ElementTree

API = 1
PERMISSIONS = {"clipboard", "shared", "ssh-agent"}
MAX_LAYER = 4 << 30
MAX_ICON = 64 << 10
WORD = re.compile(r"^[0-9A-Za-z.-]{1,64}$")
ENV_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
BASES = os.path.join(os.path.dirname(__file__), "..", "bases.json")

def problems(manifest, release, bases):
    """Everything wrong with a manifest that needs no download."""
    out = []
    m = manifest
    if not isinstance(m.get("api"), int) or not 1 <= m["api"] <= API: out.append(f"`api` must be 1..{API}")
    if not isinstance(m.get("id"), str) or not WORD.match(m["id"]) or m["id"].startswith("."): out.append("`id` must be letters, digits, `.` and `-`")
    if not isinstance(m.get("name"), str) or not 0 < len(m["name"]) <= 64: out.append("`name` must be 1–64 characters")
    if not isinstance(m.get("version"), str) or not m["version"]: out.append("`version` is missing")
    if m.get("display") not in ("pty", "gui"): out.append("`display` must be `pty` or `gui`")
    launch = m.get("launch") or {}
    cmd = launch.get("cmd")
    if not isinstance(cmd, list) or not cmd or not all(isinstance(c, str) and "\0" not in c for c in cmd): out.append("`launch.cmd` must be a non-empty list of strings")
    for k, v in (launch.get("env") or {}).items():
        if not ENV_KEY.match(k) or not isinstance(v, str) or any(c in v for c in "\r\n\0"): out.append(f"bad environment variable `{k}`")
    extra = set(m.get("permissions") or []) - PERMISSIONS
    if extra: out.append(f"unknown permissions: {', '.join(sorted(extra))}")
    if m.get("from") not in bases: out.append("`from` is not a released base image digest (bases.json)")
    src = m.get("source") or {}
    if not src.get("repo") or not src.get("commit"): out.append("`source.repo` and `source.commit` are required")
    layers = m.get("layers")
    if not isinstance(layers, list) or not 1 <= len(layers) <= 64: out.append("`layers` must list 1–64 layers")
    for layer in layers or []:
        if not str(layer.get("url", "")).startswith(release): out.append(f"layer {layer.get('url')} is not an asset of this release")
        if not re.match(r"^[0-9a-f]{64}$", str(layer.get("sha256", ""))): out.append("layer `sha256` must be 64 lowercase hex")
        if not isinstance(layer.get("size"), int) or not 1 <= layer["size"] <= MAX_LAYER: out.append("layer `size` must be 1 B – 4 GB")
    return out

SVG = "{http://www.w3.org/2000/svg}"
ICON_TAGS = {"svg", "g", "defs", "title", "desc", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon",
             "linearGradient", "radialGradient", "stop", "clipPath", "mask"}

def icon_problem(svg):
    """An icon must be a small, self-contained SVG of plain shapes: parsed, at most 1000 elements on an
    allowlist (no `use`, so nothing multiplies), no event handlers, and references only as `url(#id)`."""
    if len(svg.encode()) > MAX_ICON: return "larger than 64 KB"
    if re.search(r"<!|<\?(?!xml\s)", svg): return "has a DOCTYPE, entity, CDATA or processing instruction"
    try: root = xml.etree.ElementTree.fromstring(svg)
    except xml.etree.ElementTree.ParseError: return "not valid XML"
    if root.tag != SVG + "svg": return "not an SVG"
    if sum(1 for _ in root.iter()) > 1000: return "more than 1000 elements"
    for el in root.iter():
        if not el.tag.startswith(SVG) or el.tag[len(SVG):] not in ICON_TAGS: return f"element {el.tag} is not allowed"
        for name, value in el.attrib.items():
            local = name.rsplit("}", 1)[-1].lower()
            if local.startswith("on") or local in ("style", "base", "href", "src", "cursor", "filter"): return f"attribute {local} is not allowed"
            if "\\" in value or "/*" in value: return "has escapes or comments in an attribute"
            if re.sub(r"url\(\s*#[A-Za-z_][\w.-]*\s*\)", "", value).lower().count("url("): return "refers outside the file"
    return None

def fetch(url, limit):
    req = urllib.request.Request(url, headers={"User-Agent": "v2mac-store-check"})
    return urllib.request.urlopen(req, timeout=60)

def check_layer(layer):
    h, n = hashlib.sha256(), 0
    with fetch(layer["url"], MAX_LAYER) as r:
        while chunk := r.read(1 << 20):
            n += len(chunk)
            if n > MAX_LAYER: return "larger than 4 GB"
            h.update(chunk)
    if n != layer["size"]: return f"size {n}, listed {layer['size']}"
    if h.hexdigest() != layer["sha256"]: return f"SHA-256 {h.hexdigest()}, listed {layer['sha256']}"
    return None

def main(path, out_path):
    sub = json.load(open(path))
    repo, tag = sub["repo"].rstrip("/"), sub["tag"]
    owner_name = re.match(r"^https://github\.com/([\w.-]+/[\w.-]+)$", repo)
    report, ok = [f"## Check: {repo} @ {tag}", ""], True
    if not owner_name or not WORD.match(tag):
        print("\n".join(report + ["- ❌ `repo` must be https://github.com/<owner>/<name> and `tag` a plain tag"])); return 1
    release = f"{repo}/releases/download/{tag}/"
    manifest = json.load(fetch(release + "plugin.json", 1 << 20))
    manifest.pop("iconSvg", None)  # only ever this check's copy of the release's icon
    bases = set(json.load(open(BASES))["allowed"])
    found = problems(manifest, release, bases)
    commit = json.load(fetch(f"https://api.github.com/repos/{owner_name.group(1)}/commits/{tag}", 1 << 20))["sha"]
    if (manifest.get("source") or {}).get("commit") != commit: found.append(f"`source.commit` is not the tag's commit {commit}")
    if (manifest.get("source") or {}).get("repo") != repo: found.append("`source.repo` is not the submitted repo")
    if not found:
        for layer in manifest["layers"]:
            err = check_layer(layer)
            if err: found.append(f"layer {layer['url']}: {err}")
    icon = manifest.get("icon")
    if not found and icon:
        if not isinstance(icon, str) or not WORD.match(icon): found.append("`icon` must be a plain release asset filename")
        else:
            with fetch(release + icon, MAX_ICON) as r: data = r.read(MAX_ICON + 1)
            try: svg = data.decode()
            except UnicodeDecodeError: svg = ""
            err = icon_problem(svg)
            if err: found.append(f"icon {icon}: {err}")
            else: manifest["iconSvg"] = svg
    report.append(f"- id `{manifest.get('id')}`, version `{manifest.get('version')}`, display `{manifest.get('display')}`, commit `{commit}`")
    report.append(f"- permissions: {', '.join(manifest.get('permissions') or []) or 'none'}")
    report += [f"- ❌ {p}" for p in found] or ["- ✅ every automatic check passed. Review it with REVIEW.md before merging."]
    print("\n".join(report))
    if not found and out_path:
        with open(out_path, "w") as f: json.dump(manifest, f, indent=1, ensure_ascii=False)
    return 1 if found else 0

def selftest():
    rel = "https://github.com/a/b/releases/download/v1/"
    good = {"api": 1, "id": "hello-pty", "name": "Hello", "version": "1", "display": "pty", "from": "base-cli@sha256:x",
            "launch": {"cmd": ["bash"], "env": {"A": "b"}}, "permissions": ["ssh-agent"], "source": {"repo": "https://github.com/a/b", "commit": "c"},
            "layers": [{"url": rel + "l.tar", "sha256": "a" * 64, "size": 10}]}
    assert problems(good, rel, {"base-cli@sha256:x"}) == []
    for key, bad in [("api", 2), ("id", "a;b"), ("display", "web"), ("permissions", ["camera"]), ("from", "debian"),
                     ("layers", [{"url": "https://evil/l", "sha256": "a" * 64, "size": 10}]), ("launch", {"cmd": []})]:
        assert problems({**good, key: bad}, rel, {"base-cli@sha256:x"}), key
    ns = "xmlns='http://www.w3.org/2000/svg'"
    assert icon_problem(f"<?xml version='1.0'?><svg {ns}><rect fill='url(#g)' clip-path='url( #c )'/></svg>") is None
    for bad in [f"<svg {ns}><script>x</script></svg>", f"<svg {ns}><image href='https://e/x.png'/></svg>", f"<svg {ns} onload='x'/>",
                f"<svg {ns}><rect fill='url(https://e)'/></svg>", f"<svg {ns}><style>*{{}}</style></svg>", f"<svg {ns} style='x'/>",
                f"<svg {ns}><foreignObject/></svg>", f"<svg {ns} xmlns:x='http://www.w3.org/1999/xlink'><use x:href='https://e'/></svg>",
                f"<svg {ns}><s:script xmlns:s='http://www.w3.org/2000/svg'/></svg>", "<!DOCTYPE svg [<!ENTITY a 'b'>]><svg/>",
                f"<svg {ns}><![CDATA[x]]></svg>", "<svg><rect/></svg>", "<png/>", f"<svg {ns}><use href='#a'/></svg>", f"<svg {ns} xml:base='https://e/'/>",
                f"<svg {ns}><rect fill='u\\72l(https://e)'/></svg>", f"<svg {ns}><rect fill='url(#a) url(https://e)'/></svg>",
                f"<svg {ns}><rect fill='URL(x)'/></svg>", f"<svg {ns}>" + "<g/>" * 1001 + "</svg>", f"<svg {ns}>" + " " * MAX_ICON + "</svg>"]:
        assert icon_problem(bad), bad
    import contextlib, io, runpy, tempfile
    from unittest.mock import patch
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "submission.json")
        with open(path, "w") as f: json.dump({"repo": "https://github.com/a/b", "tag": "v1"}, f)
        output = io.StringIO()
        with patch.object(sys, "argv", [__file__, path]), patch("urllib.request.urlopen", side_effect=OSError("offline")), contextlib.redirect_stdout(output):
            try: runpy.run_path(__file__, run_name="__main__")
            except SystemExit as error: assert error.code == 1
            else: raise AssertionError("failed download must fail the check")
        assert "offline" in output.getvalue(), "CI needs a non-empty report even when a release cannot be fetched"
    print("selftest ok")

if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]: selftest(); sys.exit(0)
    if len(sys.argv) not in (2, 4): sys.exit(__doc__)
    try:
        status = main(sys.argv[1], sys.argv[3] if len(sys.argv) == 4 else None)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(f"- ❌ Submission check failed: {error}")
        status = 1
    sys.exit(status)

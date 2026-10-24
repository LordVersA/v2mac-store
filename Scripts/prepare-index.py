"""Prepare the next unsigned index.json (sandbox plan §7): version + 1, expires in 90 days.

Usage: prepare-index.py [--add plugin.json ...] [--revoke ID VERSION REASON ...] [--template ID NAME PLUGIN,PLUGIN ...]
--add takes a plugin.json that passed Scripts/check-submission.py (its layers and source pinned).
Then sign it on the maintainer's Mac: swift Scripts/sign.swift sign index.json
"""
import datetime, json, os, sys

INDEX = os.path.join(os.path.dirname(__file__), "..", "index.json")

def prepare(index, args, now):
    i = 0
    while i < len(args):
        if args[i] == "--add":
            plugin = json.load(open(args[i + 1]))
            index["plugins"] = [p for p in index["plugins"] if p["id"] != plugin["id"]] + [plugin]
            i += 2
        elif args[i] == "--revoke":
            index["revoked"].append({"id": args[i + 1], "version": args[i + 2], "reason": args[i + 3]})
            i += 4
        elif args[i] == "--template":
            index["templates"] = [t for t in index["templates"] if t["id"] != args[i + 1]]
            index["templates"].append({"id": args[i + 1], "name": args[i + 2], "plugins": args[i + 3].split(",")})
            i += 4
        else:
            sys.exit(__doc__)
    index["version"] += 1
    index["expires"] = (now + datetime.timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return index

def selftest():
    now = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    out = prepare({"version": 4, "expires": "", "minApi": 1, "plugins": [{"id": "a", "version": "1"}], "templates": [], "revoked": []},
                  ["--revoke", "a", "1", "leaks", "--template", "t", "T", "a,b"], now)
    assert out["version"] == 5 and out["expires"] == "2026-04-01T00:00:00Z"
    assert out["revoked"] == [{"id": "a", "version": "1", "reason": "leaks"}]
    assert out["templates"] == [{"id": "t", "name": "T", "plugins": ["a", "b"]}]
    print("selftest ok")

if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        selftest()
    else:
        index = prepare(json.load(open(INDEX)), sys.argv[1:], datetime.datetime.now(datetime.timezone.utc))
        with open(INDEX, "w") as f:
            json.dump(index, f, indent=1, ensure_ascii=False)
            f.write("\n")
        if os.path.exists(INDEX + ".sig"):
            os.remove(INDEX + ".sig")  # the old signature no longer matches
        print(f"index.json version {index['version']}, expires {index['expires']}. Now sign it: swift Scripts/sign.swift sign index.json")

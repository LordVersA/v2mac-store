# Review checklist

For a submission whose automatic check passed. "Verified" in the sandbox means *unchanged since
published*, not *safe*: this review is what stands behind the store.

1. **Source at the pinned commit.** Read the repo at `source.commit`, not at the branch head.
2. **Containerfile**: `FROM` the listed base digest only; packages from Debian's signed archive or
   pinned by hash; no `curl | sh`, no binaries without a source.
3. **Build is the release.** The layers came from the repo's release CI at that tag (workflow run
   visible), not uploaded by hand.
4. **Permissions** are the fewest it needs: `ssh-agent` only for SSH tools, `shared` only to exchange
   files, `clipboard` only where copy/paste is the point. The reason is in `securityNotes`.
5. **Launch**: `launch.cmd` starts the app itself; no shell tricks that fetch code at runtime.
6. **No network or VM setup** in the plugin (no vsock, iptables, mounts, setuid): the runtime owns those.
7. **Name and icon** don't impersonate another app or V2Mac.
8. **Changelog** describes this version; for an update, read the diff since the listed version.

Then merge, `python3 Scripts/prepare-index.py --add <checked plugin.json>`, `swift Scripts/sign.swift sign index.json`, push.

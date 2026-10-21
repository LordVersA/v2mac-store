# CLAUDE.md (store)

The Secure Sandbox plugin store: one `index.json` and its offline Ed25519 signature
`index.json.sig`, served from GitHub. Plan: `../app/docs/SANDBOX.md` §5 and §6, milestone M5.

- `index.json` holds `version` (only ever goes up), `expires`, `minApi`, `plugins[]` (full manifests
  with pinned commit and every layer's SHA-256) and `templates[]` (name + plugin ids).
- The signing key never enters this repo or CI. The maintainer signs on their own Mac; Claude
  prepares the unsigned index and the user signs it.
- Accepting a plugin = reviewing that plugin repo at one commit, then copying its manifest and hashes.
- The app's `StoreIndex` reads this format: change both together.
- Not on GitHub yet: no remote, no pushing until the user asks.

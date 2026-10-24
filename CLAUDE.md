# CLAUDE.md (store)

The Secure Sandbox plugin store: `index.json` and its signature `index.json.sig`, served from
GitHub. Plan: `../sandbox/docs/PLAN.md` §7, milestone M5.

- `index.json`: `version` (only ever goes up), `expires` (90 days from signing), `minApi`,
  `plugins[]` (full manifests with pinned commit and every layer's SHA-256), `templates[]`,
  `revoked[]` (`{id, version, reason}`).
- Signed only on the maintainer's Mac: `index.json.sig` is the base64 Ed25519 signature over
  SHA-256(index.json), made by `swift Scripts/sign.swift sign index.json` with the key in the login
  Keychain (item `v2mac-store`, no trusted apps; paper backup of it is the recovery). `key.pub` is the
  key the helper pins. No private key ever enters this repo or CI. Claude prepares the unsigned index (`Scripts/prepare-index.py`); the user signs.
- Submissions are PRs adding `submissions/<id>.json` (repo URL + tag). CI (`Scripts/check-submission.py`)
  checks hashes, schema, `api`, the `from` base digest (`bases.json`) and permissions, and comments a
  report. Merge only after `REVIEW.md`. `Scripts/*.py --selftest` and `swift Scripts/sign.swift selftest` check the scripts.
- The helper's index checks read this format: change both together.
- Public repo: `LordVersA/v2mac-store`. Push when the user asks or CI needs to see it; index signatures still need the maintainer's Mac.

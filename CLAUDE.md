# CLAUDE.md (store)

The Secure Sandbox plugin store: `index.json` and its signature `index.json.sig`, served from
GitHub. Plan: `../sandbox/docs/PLAN.md` §7, milestone M5.

- `index.json`: `version` (only ever goes up), `expires` (90 days from signing), `minApi`,
  `plugins[]` (full manifests with pinned commit and every layer's SHA-256), `templates[]`,
  `revoked[]` (`{id, version, reason}`).
- Signed only on the maintainer's Ledger (Ed25519, SSH/PGP Agent app, `ssh-keygen -Y sign`, SSHSIG).
  No private key ever enters this repo or CI. Claude prepares the unsigned index; the user signs.
- Submissions are PRs adding a plugin repo URL + tag. CI checks hashes, schema, `api`, the `from`
  base digest and permissions, and comments a report. Merge only after the checklist review.
- The helper's index checks read this format: change both together.
- Not on GitHub yet: no remote, no pushing until the user asks.

# Agent instructions

## Off-limits: `local/`

Never read, open, list, search, grep, cat, copy, or index anything under `local/`, and never read `inventory.yml`.
These paths are gitignored and hold private notes, including wallet recovery phrases and keys.

- Exclude them from every search: `git grep` (tracked files only) or `grep -r --exclude-dir=local --exclude=inventory.yml`.
  Never run a recursive search, `find`, or `ls -R` from the repo root without that exclusion.
- If you need something that might only exist there (validator or wallet addresses, chain notes), ask the user.
  For addresses, use tracked files (`vars/`, git history) or look the validator up on-chain by its moniker
  ("CosmosSpaces" / "Cosmos Spaces").
- If such content shows up in tool output anyway, stop, don't repeat it, don't save it anywhere, and tell the user.
- Never print, log, or store mnemonics, private keys, or `priv_validator_key.json` contents from any source.

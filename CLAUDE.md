# CLAUDE.md

@AGENTS.md

## Hard rule: never read `local/` or `inventory.yml`

These are gitignored and hold private notes, including wallet recovery phrases. Do not use Read, Grep, Glob, or
Bash (`cat`, `sed`, `head`, `grep -r`, `find`, `ls -R`, ...) on them, directly or through a recursive search from
the repo root. Use `git grep` or `--exclude-dir=local --exclude=inventory.yml`. Subagents you start must be told
the same. If the information might only live there, ask the user instead.

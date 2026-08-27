# Repo Audit — Findings and Suggestions

Audit date: 2026-08-21. Scope: full repo (roles, playbooks, vars, inventory structure) — purpose, operation, and operator-facing intuitiveness. All CRITICAL/HIGH items below were independently verified against the actual repo/inventory after initial discovery (not just reported as-is).

## Most critical finding — Horcrux testnet/mainnet inventory collision

`inventory.yml:156-184` defines both `horcrux_cluster_testnet` and `horcrux_cluster_mainnet` with **identical hostnames** (`cosigner1`, `cosigner2`, `cosigner3`) but different IPs. Ansible inventory hostnames are global keys — verified with `ansible-inventory --list` that `cosigner1` resolves to `10.10.0.154` (the mainnet box) **regardless of which group is queried**. The mainnet block is declared after the testnet block, so it silently wins.

Practical effect: the testnet cosigner IPs are currently unreachable through this inventory — dead config. Anything run against `-e target=horcrux_cluster_testnet` actually connects to the **production mainnet signers**. Worse, `roles/horcrux_install/tasks/main.yml:42` hardcodes `hostvars["cosigner1"|"cosigner2"|"cosigner3"]` (not `groups[target]`, unlike the port-opening task three lines below it, which does this correctly) — so `horcrux config init` always embeds the mainnet cosigner IPs into the peer list, even when configuring testnet. Both confirmed directly.

Compounding this: no horcrux playbook uses `serial:`, so any run against a `horcrux_cluster_*` group hits all 3 cosigners concurrently — and `roles/horcrux_install/tasks/main.yml` stops the horcrux service (line 37) with **no restart task anywhere in the role** (confirmed — only one `state:` in the whole file). A routine `horcrux_version` bump run against the full cluster would take 2-3 of 3 signers offline at once with no automated way back, breaking quorum for every mainnet chain in `nodes:`.

**Fix this first, before touching horcrux config again for any reason.**

## Other critical findings

- **`cosmovisor/current` symlink is never managed anywhere in the pre-existing roles** (confirmed by repo-wide grep — only the new `node_service_check` role touches it). `node_upgrade`'s hotfix branch (`upgrade_folder` undefined) copies into `genesis/bin` and restarts, but if `current` already points at a prior `upgrades/<name>` folder, the restart just relaunches the same old binary. Compounding it: **38 of 42 chain vars files hardcode `upgrade_folder` permanently**, so that hotfix branch is effectively unreachable without hand-editing a committed vars file first.
- **`roles/support_prune/templates/prune.sh.j2:3,7`** — `sudo service {{ chain }} stop` targets a unit name that doesn't exist (real unit is `cosmovisor-{{ service_prefix }}`). Confirmed. The stop silently fails (no `set -e` in the script) and `cosmprund prune` runs against a live, still-writing database.
- **`roles/support_sync_snapshot/tasks/main.yml`** — confirmed the destructive `unsafe-reset-all` happens *before* the snapshot archive is extracted/verified, with an unpipefail'd `lz4 | tar` pipe that can mask a decompression failure as success.
- **`roles/support_resync/templates/recover.sh.j2` and `resync.sh.j2`** — confirmed: `rm -rf` on live data with no existence/success check on the backup, no `set -e` anywhere, and `resync.sh.j2` has no post-restart health check at all (unlike its siblings).

## High-severity findings

- **`type` variable collision**: `state_sync.sh.j2`/`genesis.sh.j2` branch on `type == 'test'` to pick testnet vs mainnet RPC endpoints, but `type` is the same variable used for host role (`sentry`/`relayer`/`validator`) everywhere else, and no chain vars file ever sets it to `'test'`. Confirmed via grep — every testnet host silently gets mainnet RPC config unless the operator manually passes `-e type=test`.
- **`support_remove_node`**: no confirmation, no dry-run, `target` accepts a whole group (not just one host) and deletes `{{ user_dir }}/{{ folder }}`. Plus two more bugs in the same role: a duplicate no-op delete task (`main.yml:9-17`), and a binary-cleanup task pointing at the wrong path (`main.yml:27`, missing `/go/bin/`) so the real binary is never removed.
- **Missing `become: true`** on the `apt: unzip` task for zip-packaged binary installs (`roles/node_install/tasks/binary_zip.yml`, `roles/node_upgrade/tasks/binary_zip.yml`) — confirmed the main play (`main.yml`) has no play-level `become` (only the separate Prometheus play does), so this fails outright the first time any chain needs zip binaries.
- **Secrets with no `mode`/`no_log`**: confirmed zero `no_log` uses repo-wide. Telegram bot token (alertmanager), price-feeder keyring passwords, and Cloudflare API key are all rendered without `no_log`, and the alertmanager config file (`roles/node_alertmanager/tasks/main.yml:61-68`) has no explicit mode (likely world-readable) while the unit file three tasks later is correctly `0600`.
- **No TLS anywhere** for public RPC/API endpoints (confirmed no `listen 443` in `roles/support_public_endpoints/templates/*.j2`) — Basic Auth credentials for partner RPC access travel in cleartext to origin.
- **Port 80/443 never opened by ufw anywhere**, despite `default: deny incoming` in `roles/setup/tasks/firewall.yml` — either public endpoints are unreachable as coded, or the firewall was hand-patched outside this repo (drift risk).
- **`roles/setup/tasks/nginx.yml:8-14`** deletes the entire `/etc/nginx/sites-available` *directory*, not just the `default` file inside it — almost certainly meant to be `sites-available/default`. Confirmed as written.
- **`vars/mainnet/sei.yml:16`** — literal typo `rregexp:` instead of `regexp:` — confirmed, will hard-fail `node_configure` for sei with an undefined-attribute error.
- **`node_upgrade`'s version validation is print-only** (`roles/node_upgrade/tasks/main.yml:75-83`) — confirmed no `assert`/`failed_when`, so a bad build/download that produces the wrong version still reports the play as green.

## Medium-severity findings

- Unconditional service restarts even when nothing changed: `support_update_min_gas/tasks/main.yml:9-15`, `support_chain_horcrux/tasks/main.yml:12-18`, `support_price_feeder/tasks/main.yml:33-39`, `node_tenderduty/tasks/main.yml:10-16`, `support_tenderduty/tasks/main.yml:71-77` — all confirmed spot-checked, none gated on whether the preceding config change actually happened.
- Shared, non-chain-scoped `/tmp` filenames (`/tmp/binary.zip`, `/tmp/binary.tar.gz`, `/tmp/genesis.json` etc. in `node_install`/`node_initialize`/`node_upgrade`) create a cross-run clobber risk on hosts running multiple chains concurrently.
- Horcrux/price-feeder/tenderduty services run as `ansible_user`, the same account granted passwordless sudo (`support_admin_user/tasks/main.yml:14-18`) — unlike `promtail`, which correctly uses a dedicated unprivileged `nologin` service account.
- SSH is reconfigured/restarted before its firewall rule exists (`roles/setup/tasks/main.yml` runs `ssh.yml` before `firewall.yml`) — a window on a port change or re-run.
- `roles/support_horcrux_config/tasks/main.yml:2-5` — "Ensure config file exists" uses `file: state: file`, which fails rather than creates, on a fresh/out-of-order run.
- `roles/support_price_feeder/tasks/main.yml` — service file templating is conditional on `price_feeder_password`, but the restart three tasks later isn't, so an unconfigured host fails outright.
- `roles/setup/tasks/firewall.yml:55-66` — horcrux `priv_validator_laddr` port range (`22110:22160`) is a hardcoded magic window not derived from `custom_port_prefix`; a future chain's prefix falling outside it fails closed with a confusing signing outage.
- Alerting gaps: no alert consumes the horcrux Prometheus port that's opened, and no alert consumes `cosmos-watcher` metrics that `support_cosmos_watcher` deploys.

## Low / cosmetic findings

- `node_debug` role is dead code, referenced nowhere in any playbook (confirmed via grep).
- `support_backup_node.yml` doesn't actually back up anything (only installs cron scripts for later use) and its play name is copy-pasted verbatim from `support_state_sync.yml`/`support_resync.yml`. Repo-wide, **no role ever backs up `priv_validator_key.json`**.
- `roles/support_remove_node/tasks/main.yml:35` — snapshot-script cleanup path doesn't match where `support_snapshot` actually installs it (currently harmless only because the whole folder tree is already deleted earlier in the same task file).
- `roles/support_admin_user/tasks/main.yml:8-13` — `authorized_key` with `exclusive: yes` and a default fallback key; a misconfigured var could wipe other keys for that user.
- `inventory.yml:64-70` — `testnet-ger-sentry02` (with a `network: testnet` override) lives inside the `mainnet` hosts group — confusing to a reader unfamiliar with the per-host override convention.

## What's well-designed — leave alone

- Firewall scoping in `roles/setup/tasks/firewall.yml`: default-deny, SSH restricted to bastion, Prometheus scoped to telemetry server, horcrux cosigner-to-cosigner ports scoped per-peer IP via a `hostvars` loop.
- `roles/setup/tasks/ssh.yml`'s hardening: no root login, no password auth, restricted `AllowUsers`.
- The horcrux 2-of-3 threshold signing design itself — the risks found here are operational/tooling risks around it, not the protocol design.
- `support_sync_snapshot`'s instinct to preserve `priv_validator_state.json` across a reset (just needs step reordering, see Critical findings).
- `promtail`'s dedicated unprivileged service account — the right pattern, just not applied consistently elsewhere (Horcrux/tenderduty/price-feeder).
- `roles/node_configure/vars/main.yml`'s centralized port/pruning dicts, keeping many `lineinfile` tasks DRY and consistent per node type.
- `snapshot.sh.j2` restarts the service before the slow upload/cleanup step, minimizing downtime — good ordering choice, worth reusing as the model for fixing `support_sync_snapshot`'s ordering problem.
- `resync.sh.j2`'s wasm-chain-aware data preservation during reset (terra/teritori/nibiru/mars/xpla) — thoughtful, chain-specific handling.

## Suggested priority order

1. Fix the horcrux inventory collision and the hardcoded cosigner aliases — this is a live footgun, not a hypothetical one.
2. Add `serial: 1` (or similar) plus a real restart-after-stop to `horcrux_install`, before next touching that role.
3. Fix `prune.sh.j2`'s service name and add basic `set -e`/checks to the resync/recover/snapshot bash templates — the data-loss-risk cluster.
4. Decide how to explicitly manage `cosmovisor/current` going forward, and consider a dedicated `hotfix: true` flag instead of overloading `upgrade_folder`'s presence/absence.
5. Work through the remaining medium/low findings opportunistically.

# Feature comparison vs. Polkachu's public cosmos-validators template

Date: 2026-08-22. This repo is structurally derived from Polkachu's own public Ansible template (`github.com/polkachu/cosmos-validators`) — same role names, same conventions, same per-chain vars pattern. This is a direct feature-parity check against that upstream project, not a generic industry comparison. All findings below were verified directly (file listings and raw task file contents fetched from the upstream repo, cross-checked against this repo's actual files).

## Capabilities we're missing

**1. `support_halt` / `support_halt_upgrade` — no graceful halt-height workflow at all.**
Polkachu has a dedicated mechanism: set `halt-height` in `app.toml`, flip the systemd unit to `Restart=no` (so it doesn't auto-restart into a busy-halt loop), then restart deliberately. `support_halt_upgrade` combines that with the same binary-swap logic our `node_upgrade` uses. We have zero equivalent — no way to stop a node cleanly at a specific height for a state export, a manually-coordinated upgrade outside cosmovisor's auto-upgrade path, or planned maintenance. Confirmed absent via repo-wide grep for "halt". Fairly small lift to add given `node_upgrade` already has most of the plumbing.

**2. `support_pigeon` — no support for Pigeon as a relayer option.**
Pigeon is a lightweight IBC relayer service Polkachu deploys as a systemd unit with its own config template (`~/.pigeon/config.yaml`, `pigeon.service`). We have nothing under this name — confirmed absent via repo-wide grep. Whether this matters depends on whether any relayer host would benefit from it vs. whatever's running today; worth checking what's actually installed on the current relayer hosts, since neither repo appears to automate Hermes/rly installation either.

**3. Newer per-chain `support_public_endpoints` quirk-handlers we don't have.**
Their role has 19 per-chain task files: `ada`, `agor`, `comp`, `crcl`, `cube`, `dydx`, `init`, `mainnet`, `nbl`, `newt`, `osmo`, `skip`, `skip_extra`, `strd`, `testnet`, `trp`, `tw`, `yx`, `zm`. We have 9 of those (`agor`, `comp`, `dydx`, `mainnet`, `skip`, `skip_extra`, `strd`, `testnet`, `zm`) — confirmed by directly listing both role directories. Missing: `ada`, `crcl`, `cube`, `init`, `nbl`, `newt`, `osmo`, `trp`, `tw`, `yx`. This only matters if public RPC/API endpoints ever get stood up for one of those specific chains and a config quirk they've already solved upstream is hit.

**4. No `test.yml` scratch playbook.** Trivial — theirs is just `hosts: target, become: true, roles: [test]`, a reusable template for ad hoc role development. Minor convenience, not a real capability.

## Not a gap — already at parity

`support_scripts` (bank_balances/bank_send/gov_vote/distribution_withdrawal) is the same pattern in both repos — confirmed by reading our own role directly. Core node lifecycle, the port-prefix system, and the monitoring stack are equivalent.

**Important reframe of an earlier audit finding:** the `cosmovisor/current`-symlink limitation found in `AUDIT_FINDINGS.md` is **present in Polkachu's upstream template too** — their `node_upgrade`/`support_halt_upgrade` use the identical genesis-vs-upgrades-folder copy pattern with no explicit symlink management (confirmed by reading their `node_upgrade/tasks/main.yml`). This isn't a bug unique to this fork; it's a shared gap across this whole family of cosmovisor-Ansible tooling upstream too, which lowers the priority of trying to fix it here relative to the horcrux inventory issue.

## Where we exceed the upstream template

- **Horcrux remote-signing integration** (`horcrux_install`, `support_chain_horcrux`, `support_horcrux_config`) — confirmed completely absent from Polkachu's public repo (searched for horcrux/signer/cosigner/tmkms across the full tree, zero matches). Double-sign protection via a 2-of-3 threshold signer is a real security capability we have that their published template doesn't.
- **`upgrade_fleet.yml` + `node_service_check`** — the presence/enabled/running detection, chain-id cross-verification, and canary rollout built in this repo has no upstream equivalent; their upgrade tooling is still purely per-host/manual-target, same as our older `upgrade.yml`.

## Sources

- https://github.com/polkachu/cosmos-validators
- https://polkachu.com/service_overview
- https://polkachu.com/blogs/holy-trinity-a-system-approach-to-tendermint-based-chain-validation

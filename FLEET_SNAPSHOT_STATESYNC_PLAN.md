# Fleet-internal snapshot restore and state-sync

## Context

Nodes in this fleet currently sync from external sources only: `support_sync_snapshot` downloads from an external `snapshot_url` (Polkachu/R2), and `support_state_sync` (`state_sync.sh.j2`) always queries `https://{{ chain }}-{testnet-}rpc.polkachu.com`. When multiple fleet hosts run the same chain, that's wasted external bandwidth and reliance on a third party for something the fleet can already do internally — one already-synced fleet node can seed the others directly over the private network, reducing per-host storage growth and external dependency.

This plan adds two new playbooks: `fleet_snapshot_restore.yml` (one healthy fleet node produces a snapshot, others restore from it) and `fleet_state_sync.yml` (one healthy fleet node's RPC becomes the state-sync witness for others). Both reuse `roles/node_service_check` (built for `upgrade_fleet.yml`) to verify source and target hosts are genuinely live, healthy participants of the named chain before touching anything — this is not for onboarding brand-new nodes, it's for refreshing existing fleet members from an internal source instead of an external one.

**Two corrections made while designing this, both from catching my own initial mistakes:**
1. My first instinct for fixing `support_sync_snapshot`'s destructive-before-verified bug (audit finding) was to extract to a staging directory before touching live data. That's wrong — it needs ~2x disk headroom, and the existing reset-then-extract ordering exists specifically to free space before writing the new data, which is the whole point of this feature. The corrected fix (already applied, see below) instead adds a cheap integrity check (`lz4 -t`) before the destructive reset, and `set -o pipefail` on the extraction pipe so a real decompression failure actually halts the play instead of silently succeeding — same disk profile as today, genuinely safer.
2. I initially assumed a state-sync source needs no disruption (RPC is read-only, no stop required). Wrong — RPC's `laddr` defaults to `tcp://localhost:...` (`roles/node_configure/vars/main.yml:4`) unless `publicrpc: true`; a remote fleet host can't reach it at all without rebinding to `0.0.0.0` and restarting. So a state-sync source needs the same brief-restart risk as a snapshot source, and should be restricted the same way.

## Confirmed via investigation (not re-derived here)

- No host-to-host SSH trust exists — only the Ansible control machine holds per-host SSH credentials (confirmed via full-repo search for `authorized_key`/`synchronize`/`rsync`). Transfer between fleet hosts must go over HTTP/RPC, not SSH.
- P2P port (`custom_port_prefix+56`) is already open with no `src` restriction. RPC port (`+57`) has no firewall rule anywhere and is `localhost`-bound by default.
- `private_network_cidr` (`10.10.0.0/16`) is defined but used exactly once today (horcrux's port range, `roles/setup/tasks/firewall.yml:55-66`) — that's the pattern to follow for any new fleet-internal firewall rule.
- `directory.yaml` is stale/unreliable (5 chains with vars files are missing from its map entirely) — do not use it as a source of truth here; live detection via `node_service_check` is the reliable path.
- `roles/support_sync_snapshot` already accepts an arbitrary `snapshot_url` with no origin restriction, so pointing it at an internal host is a drop-in change, not a rewrite.

## Approach

### 1. Small, already-applied fix: `roles/support_sync_snapshot/tasks/main.yml`

Adds (in place, preserving the existing reset-before-extract ordering):
- `lz4 -t {{ ... }}.tar.gz` integrity check immediately after download, before the service is stopped or anything destructive happens.
- `set -o pipefail` on the `lz4 -c -d ... | tar -x ...` extraction shell task, so a real failure there properly fails the Ansible task (halting the play with the node left stopped) instead of the pipe silently reporting `tar`'s exit code.

This is currently uncommitted on the `audit-findings` branch (unrelated to that branch's topic) — move it to its own commit on a dedicated branch as the first step of implementation, since it stands alone as a bug fix independent of the new feature.

### 2. Extend `roles/node_service_check` with a "genuinely synced" signal

`node_service_check` already queries the host's own `/status` RPC to verify chain-id (`roles/node_service_check/tasks/main.yml`, the `chain_id_verified` logic). Reuse that same response to also expose `chain_synced: "{{ not (rpc_status.json.result.sync_info.catching_up | default(true)) }}"` — no new RPC call needed. A host that's present/enabled/running/chain-id-correct but still catching up should never be usable as a source for seeding others.

Also rename `chain_upgrade_eligible` → `chain_host_healthy` throughout (`roles/node_service_check/tasks/main.yml` and its three references in `upgrade_fleet.yml`) — the name was upgrade-specific, but the fact itself (present+enabled+running+chain-id-verified) is exactly the generic "is this a legitimate live participant of chain X" check both new playbooks need. Re-run the existing local dry-run regression test against `upgrade_fleet.yml` afterward to confirm nothing broke.

### 3. New role: `roles/fleet_snapshot_prepare` (runs on the source host only)

- Stop cosmovisor, `tar -cf - data [wasm] | lz4 > {{ chain }}_fleet.tar.lz4` into a dedicated serve directory, restart cosmovisor immediately (get the source back up before the slow part — matches `snapshot.sh.j2`'s existing "restart before the slow step" ordering).
- Open an ufw rule for a serve port (`{{ custom_port_prefix }}80`, following the existing per-chain port-prefix convention) scoped to `src: '{{ private_network_cidr }}'`, matching the horcrux precedent exactly.
- Start a **self-expiring** background file server: `nohup timeout {{ snapshot_serve_timeout_seconds | default(1800) }} python3 -m http.server {{ port }} --directory {{ serve_dir }} >/tmp/... 2>&1 &`, detached via `nohup`/`setsid` so it survives the SSH session ending. The timeout is a safety net independent of whether the explicit cleanup play below actually runs.
- `set_fact` the serve URL (`http://{{ ansible_host }}:{{ port }}/{{ chain }}_fleet.tar.lz4` — `ansible_host` is already the private IP for fleet hosts, same assumption horcrux's existing config already relies on) and the captured block height, for later plays to read via `hostvars`.

### 4. New role: `roles/fleet_snapshot_cleanup` (runs on the source host, always)

Kills the file-server process, removes the ufw rule, deletes the served tarball. Every task tolerant of "there was nothing to clean up" (e.g. server already self-expired) so this is safe to run unconditionally.

### 5. New playbook: `fleet_snapshot_restore.yml`

```
Play 1 (hosts: "{{ source_host }},{{ target }}"): scan — node_service_check per host,
        with the same rescued include_vars pattern as upgrade_fleet.yml for hosts whose
        resolved network has no vars file for this chain.
Play 2 (hosts: localhost): validate + confirm
  - assert source_host and target (explicit comma list, required — no "everyone else" default)
  - assert hostvars[source_host].chain_host_healthy and .chain_synced
  - assert hostvars[source_host].type in ['archive','snapshot'] unless -e allow_sentry_source=true
    (validator is never allowed as a source, no override)
  - assert chain_host_healthy for every host in target (already-running fleet members only,
    not for onboarding new nodes)
  - pause for confirmation (skipped if dry_run, same as upgrade_fleet.yml), broadcast the
    yes/no decision via delegate_facts to [source_host] + target hosts specifically
Play 3 (hosts: "{{ source_host }}"): fleet_snapshot_prepare, gated on the broadcasted confirmation
Play 4 (hosts: "{{ target }}", serial: "{{ target_serial | default(1) }}"): 
  - end_host if not confirmed / dry_run
  - snapshot_url = hostvars[source_host].fleet_snapshot_url
  - include_role: support_sync_snapshot (the fixed version)
  - sanity-check: post-restore block height is non-zero and within a generous window of the
    source's captured height
Play 5 (hosts: "{{ source_host }}"): fleet_snapshot_cleanup — runs regardless of Play 4's
  outcome (a play-level failure in Play 4 doesn't skip a later play targeting a different host)
```

Default `serial: 1` (not upgrade's canary-then-100%) — target lists here are expected to be small and deliberately curated, so full one-at-a-time is the safer default; overridable via `-e target_serial=`.

### 6. New role: `roles/fleet_state_sync_prepare` (runs on the source host)

- `lineinfile` to rebind RPC `laddr` to `tcp://0.0.0.0:{{ custom_port_prefix }}57` if not already public (register the change).
- Restart cosmovisor **only if that actually changed** something (fixes the same "unconditional restart" anti-pattern flagged in the audit, applied here from the start).
- Add a **persistent** (not ephemeral) ufw rule for the RPC port scoped to `private_network_cidr` — idempotent, safe to leave, since the point is reuse as an ongoing internal witness rather than a one-off transfer.

### 7. New role: `roles/fleet_state_sync_apply` (runs on target hosts)

Fetch `trust_height`/`trust_hash` from the source's internal RPC (not Polkachu), rewrite the `[statesync]` block in `config.toml` via `lineinfile` per field (matching `node_configure`'s existing per-field convention rather than the raw `sed` one-liner `state_sync.sh.j2` uses), stop, `unsafe-reset-all --keep-addr-book` (preserving peers, consistent with existing convention), restart, then verify: health check, plus two block-height samples a short time apart to confirm the node is actively advancing (full state-sync completion isn't waited on synchronously — that can take a while; this just confirms it started successfully).

### 8. New playbook: `fleet_state_sync.yml`

Same shape as `fleet_snapshot_restore.yml` Plays 1-2 (scan, validate, confirm — same source type-restriction, same explicit-target requirement, plus the same `chain_synced` requirement on the source), then Play 3 (source) `fleet_state_sync_prepare`, Play 4 (targets, `serial: 1` default) `fleet_state_sync_apply`. No cleanup play — the RPC exposure is intentionally persistent.

## Verification

- Syntax-check both new playbooks (`ansible-playbook <file> --syntax-check`), same as done for `upgrade_fleet.yml`.
- Re-run the existing local dry-run regression test against `upgrade_fleet.yml` after the `chain_host_healthy` rename to confirm nothing broke.
- Isolated Jinja/logic tests (same technique used throughout this session) for: the confirm/broadcast reuse, the source type-restriction assertions, the height-sanity-check comparison, and the `lineinfile`-changed-gates-restart logic — these don't need real cosmovisor infra.
- What cannot be tested locally and needs the real bastion: the actual tar/lz4/http.server round trip end-to-end, the actual state-sync completion, and the RPC rebind+restart on a real node. Flag this clearly rather than claiming false confidence, same as with `upgrade_fleet.yml`.
- Recommend the user's first real test use a low-stakes chain/host pair (not a validator, not anything consensus-critical) before relying on this for anything that matters.

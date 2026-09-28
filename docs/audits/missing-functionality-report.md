# MCP-OpenStack-Ops — Missing Functionality & Defect Report

**Date:** 2026-09-28
**Baseline:** `main` @ `2891879` (post neutron-merge)
**Method:** source read + live `openstacksdk` introspection on **both** ends of the pinned range (locked `4.9.0` and `4.20.0`). Every SDK claim below was executed, not recalled.
**Scope:** Compute (Nova), Block Storage (Cinder), Network (Neutron), Identity (Keystone), Image (Glance), plus the cross-cutting tool layer.

> **No live OpenStack cloud was available.** All findings are from source and SDK
> introspection. "Will fail at runtime" means the code path reaches a call the SDK
> proxy does not define — verified by `hasattr` on both versions, not by executing
> against a cloud.

---

## 0. The finding that reframes everything else

**One headline claim fails, one holds, one is untested.**

The project advertises *"production-safe"*, *"project-scoped"* and *"read-only by
default"*. I verified each rather than taking the README's word:

| Claim | Status | Evidence |
|---|---|---|
| Read-only by default | **Holds — verified** | Measured, not assumed. `ALLOW_MODIFY_OPERATIONS` unset → 41 tools registered, 0 with a mutating verb. `=true` → 94 tools, 53 mutating. See §4.1 |
| Project-scoped | **Unverified** | No global enforcement; the only test requires a live cloud. See §4.3 |
| Production-safe | **Not substantiated** | One test file in the entire repo, no CI, and six verified P0 defects sitting on `main` |
| Tools register reliably | **Holds** | `tools/__init__.py` auto-registers via `pkgutil.iter_modules`; no manual registry to desync |

The single most consequential structural fact: **because tools auto-register,
there is no registry to fall out of sync — so the failure mode is not
"unreachable tool", it is "tool the model can see that lies".** A manually
registered tool that was never wired up is invisible and harmless. An
auto-registered one is advertised to the LLM and fails at call time. The
neutron work in `main` removed exactly this class of lie; the rest of the
codebase still has it.

---

## 1. P0 — Defects that fail at runtime

Six confirmed on `main` @ `2891879`. Each verified by grepping the cited line
**and** probing the SDK on both pinned versions.

### D1 — Server force-delete calls a method that does not exist

- **Site:** `services/compute.py:594` → `conn.compute.force_delete_server(server)`
- **SDK truth:** `force_delete_server` is **absent from both 4.9.0 and 4.20.0**. The real signature is
  `delete_server(self, server, ignore_missing=True, force=False)`.
- **Impact:** `force=True` on the `set_instance` delete action raises `AttributeError`, swallowed by the outer handler into a generic failure. Force-delete is 100% non-functional and presents as functional.
- **Fix:** `conn.compute.delete_server(server, force=True)`

### D2 — Server backup calls a method that does not exist

- **Site:** `services/compute.py:2261` → `conn.compute.create_server_backup(...)`
- **SDK truth:** absent from both versions. Real method is `backup_server(self, server, name, backup_type, rotation)` — a *different* parameter set than the surrounding code assumes.
- **Impact:** `set_server_backup` always raises `AttributeError`.
- **Fix:** `conn.compute.backup_server(...)`, and re-derive the parameters from the real signature rather than the invented set.

### D3 — Compute agent lookup uses a non-existent method

- **Site:** `functions.py:830` → `conn.compute.get_service(agent_id)`
- **SDK truth:** only `find_service(...)` exists (both versions).
- **Impact:** `set_compute_agents(show, agent_id=…)` fails; the `host=` fallback path works. Half-broken is worse than broken — it looks supported.
- **Fix:** `conn.compute.find_service(agent_id)`

### D4 — Volume-attachment arguments reversed at 3 of 4 call sites

- **SDK signature:** `create_volume_attachment(self, server, volume=None, **attrs)` — **server first**.
- **Sites:** `storage.py:244`, `storage.py:276`, `storage.py:991` all pass `volume.id` first. Only `storage.py:934` is correct.
- **Impact:** at `:244` the `server_id` kwarg collides with the proxy's own `server_id=` → `TypeError`. The two `delete` sites are rescued only by a deprecation shim that emits a `RemovedInSDK50Warning` and breaks in SDK 5.0.
- **Fix:** `(server, volume)` at every site; drop the non-body `instance_uuid`.

### D5 — Server-migration arguments reversed at all three sites

- **SDK signature:** `get_server_migration(self, server_migration, server, ignore_missing=True)` — **migration first**.
- **Sites:** `compute.py:2020` (get), `:2050` (abort), `:2070` (force_complete) all pass `(server.id, migration_id)`.
- **The IDs swap.** I traced `_get_uri_attribute` in both versions; its body is `return resource.Resource._get_id(parent)` — the **second** argument. So passing `server.id` as the child and `migration_id` as the parent yields:
  - `server_id` in the URI = the **migration** ID
  - the resource ID = the **server** ID
  - final URI: `/servers/<MIGRATION_ID>/os-server-migrations/<SERVER_ID>`
- **Impact:** the request 404s. `get_server_migration` has `ignore_missing=True` by default, so it returns `None` rather than raising — and `compute.py:2025` then falls back to `getattr(migration, 'id', 'unknown')` on `None`, so the tool returns `success: True` with a migration whose every field reads `unknown`. `force_complete_server_migration` uses `_get_resource`, which raises instead — that one fails loudly.
- **Correction to an earlier draft of this report:** I initially wrote that this produced a "no-op masked by `ignore_missing`" and ranked it above D1–D4 on destructive-potential grounds. That was wrong. The IDs swap, so the URI names a migration belonging to the *wrong* server, and the only two paths that matter either return a fabricated success dict or raise. It is a **silent-wrong-answer** defect, not a silent-wrong-destruction one. It stays P0, but it does not outrank D1–D4 on blast radius.
- **Fix:** `(migration_id, server.id)` at all three sites.

### D6 — `volume.qos_specs()` does not exist on the **locked** SDK

- **Site:** `storage.py:729` → `conn.volume.qos_specs()`
- **SDK truth:** present in **4.20.0 only**. I verified `hasattr == False` on the repo's own locked **4.9.0** — the audit originally reported this as a 4.1.0 issue; it is in fact broken on the version the repo actually ships with.
- **Impact:** crashes on every install below 4.20.0. Masked by a broad `except` returning `'QoS specs not supported or available'`, so a missing API is indistinguishable from "Cinder has no QoS".
- **Fix:** either raise the floor to `>=4.20.0`, or guard with `hasattr`.

> **The version trap underneath all of this:** `pyproject.toml` pins
> `openstacksdk>=4.1.0,<=4.20.0`, but `uv.lock` resolves to **4.9.0**. Code
> written against the top of the range breaks on the locked install. This is
> now documented in `CONTRIBUTING.md` on `dev`.

---

## 2. P1 — Advertised in the tool schema, not implemented

Tool docstrings are the model's only contract. These over-promise, so the model
builds plans on capabilities that do not exist.

Each row below was verified by extracting the service function body and comparing
its `action.lower() == '...'` dispatch chain against the tool's advertised list —
not by reading the docstring alone.

| Tool | Advertises | Actually dispatches on | Fake actions | P |
|---|---|---|---|---|
| `set_volume` | `create, delete, list, extend, backup, snapshot, clone, transfer, migrate` | `attach, create, delete, detach, extend, list, snapshot` | **`backup, clone, transfer, migrate`** | **P1** |
| `set_volume_groups` | `list, create, delete, show` | **`list`** | **`create, delete, show`** | **P1** |
| `set_volume_qos` | `list, create, delete, show, set` | **`list`** | **`create, delete, show, set`** | **P1** |
| `set_volume_backups` | `list, show, delete, restore` | `create, list` | **`show, delete, restore`** | **P1** |
| `set_flavor` | `create, delete, show, list, set` | `create, delete, list, set_extra_specs` | **`show`**; `set` is really `set_extra_specs` | P2 |
| `set_keypair` | `create, delete, import` | `create, delete, list, show` | **`import`** | P2 |
| `set_metrics` | `list, show, summary` | all three are **stubs returning hardcoded zeros** | all | P2 |
| `set_service_logs` | `list, show` | `show` returns a synthesized dict; never reads logs | `show` | P2 |
| `set_server_dump` | — | honestly returns "not supported"; degrades correctly | none | not a defect |

`set_volume_qos` and `set_volume_groups` are the most serious: **four of five**
and **three of four** advertised actions respectively do not exist. A model
planning a storage strategy against these will produce a coherent plan that
fails at every step.

`set_volume` is next worst: `transfer_name` and `host` are fully declared in the
tool signature, so the model produces a well-formed call that the service rejects
with `Unknown action`.

**This is a trust problem, not a completeness problem.** A capability that is
visible but fake is worse than one that is absent — the model will not fall back
from something it believes exists.

---

## 3. Missing functionality, by service

**Verification basis for this section:** for each SDK method named below I
confirmed (a) it exists in the `openstack.compute.v2.Proxy` on both 4.9.0 and
4.20.0, and (b) it has **zero references** anywhere in `src/`. Both halves matter
— (a) alone would just list the SDK's whole surface, and (b) alone would not
prove the capability is reachable. Gaps in this section are verified absences,
not inferences from reading docstrings.

### Nova — the placement story stops at "create a server"

| # | Gap | Why it matters | P |
|---|---|---|---|
| N1 | **Aggregates** — `create_aggregate`, `add_host_to_aggregate`, `remove_host_from_aggregate`, `set_aggregate_metadata`, `aggregate_precache_images` | Primary placement mechanism for dedicated hosts / GPU / NUMA pools. **Completely absent.** | **P0** |
| N2 | **Flavor extra-specs read/delete** — `fetch_flavor_extra_specs`, `update_flavor_extra_specs_property`, `delete_flavor_extra_specs_property` | Extra specs are currently **write-only**. No read-back means you cannot verify what you set. | **P0** |
| N3 | **NUMA / CPU pinning** (via N1+N2) | Zero occurrences of `numa`/`cpu_pin` in the codebase. Without N1+N2 this is inexpressible. | **P0** |
| N4 | Per-event detail: `get_server_action` | Only bulk `server_actions` is exposed | P1 |
| N5 | **Server metadata** — `get/set/delete_server_metadata` | Existing `set_server_properties` uses general `update_server`, not the `/metadata` sub-resource. Different endpoint entirely. | P1 |
| N6 | `get_server_diagnostics` | absent | P1 |
| N7 | `get_server_console_output`, `create_console` | only `get_server_console_url` exists | P1 |
| N8 | Quota **defaults**, **quota classes**, **revert** | only `get/update_quota_set` | P1 |
| N10 | `server_ips` | IPs can be added/removed but never listed | P2 |
| N11 | Flavor access (tenant sharing) | absent | P2 |
| N12 | Service admin: `enable/disable/update_service` | `set_services` is list-only | P2 |
| N14 | Recovery ops: `reset_server_state`, `restore_server`, `change/clear_server_password` | **no way to recover an instance stuck in ERROR** | P2 |
| N15 | `shelve_offload_server` | shelved volumes never released | P2 |
| N16 | Server tags | `create_server` accepts tags, no management | P2 |
| N18 | `find_*` / `wait_for_*` helpers | the project re-implements find-by-name by **listing every resource and scanning in Python** — O(N) API calls per invocation, the dominant latency cost in the codebase | P1 |

**N1 + N2 + N3 are one coherent feature.** They are the single highest-value
addition: without them no topology-aware placement is expressible at all.

### Cinder

| # | Gap | P |
|---|---|---|
| C1 | **Volume type lifecycle** — `create_type`, `update_type`, `delete_type` (list-only today) | P1 |
| C2 | **Volume type extra-specs** — `update_type_extra_specs`, `delete_type_extra_specs` | P1 |
| C4 | **Volume group lifecycle** — create/get/update/delete/reset + group types & snapshots | P1 |
| C5 | **QoS spec lifecycle** — create/update/delete/associate/disassociate | P1 |
| C6 | Volume metadata | P1 |
| C7 | `retype_volume` — no way to move a volume between types | P1 |
| C8 | Volume transfers (`create_transfer`/`accept_transfer`) | P1 |
| C9 | `migrate_volume` / `complete_volume_migration` | P1 |
| C10 | `revert_volume_to_snapshot` — `restore` creates a *new* volume; true in-place revert is a different operation | P1 |
| C18 | Backup delete / restore | P1 |
| C13 | **Cinder-side attach/detach** — project does attachment *exclusively* through Nova. Cinder-side is what actually manipulates connection info in `attach_mode=none` deployments | P2 |
| C15 | Volume encryption key management | P2 |
| C16 | manage/unmanage, bootable, readonly, `upload_volume_to_image` | P2 |
| C19 | Cinder service admin | P2 |
| C22 | **No readiness polling anywhere** — the project returns immediately after every mutating call; `wait_for_status` is never used | P2 |

### Neutron

Largely remediated by `main` @ `2891879` (PR #12). Remaining known gaps:
trunks, port-forwarding lifecycle, `tap_flow`, VPN/IPsec, RBAC policies, BGPVPN,
address scopes, segment/subnet ranges, availability-zone network topology.

### Identity / Image / Orchestration

See §6 — audit in progress at time of writing.

---

## 4. Cross-cutting

### 4.1 The mutation guard — verified, and stronger than the docstrings suggest

I tested the read-only claim by actually enumerating the registered tool set
under each setting, rather than reading the decorator:

| `ALLOW_MODIFY_OPERATIONS` | Tools registered | With a mutating verb (`set_`/`delete_`/`create_`/`update_`/`add_`/`remove_`) |
|---|---|---|
| unset (default) | **41** | **0** |
| `false` | 41 | 0 |
| `1` / `yes` | 41 | 0 |
| `true` / `TRUE` | 94 | 53 |

The guard is **fail-closed and enforced at registration time**, not at call time.
`conditional_tool()` in `mcp_main.py` simply does not register a mutating tool
unless the flag parses as exactly `true` (case-insensitive, after `.lower()` and
no `.strip()` — note `'True '` with a trailing space correctly fails closed).
An unrecognised value like `1` or `yes` leaves the server read-only.

**This is the strongest part of the codebase and it is well designed.** I checked
the obvious hole — a mutating tool that ships without the decorator and is
therefore registered even in the default read-only configuration — and it is
closed:

- AST scan of all 94 tool files: **53 carry `@conditional_tool`, 41 do not.**
- 53 is exactly the count of mutating-verb tools, and exactly the delta between
  the enabled (94) and default (41) registration sets. The decorator set and the
  mutating set are the same set.
- The 41 undecorated files were scanned for mutation-like calls. Three matched
  and all three are false positives: two `list.extend()` calls and one
  `list(set(...))` comprehension.

So the guard is complete as written. The residual risk is not a gap but the
absence of a test: nothing asserts that the decorator set stays equal to the
mutating set, so the invariant is maintained by convention. That belongs in
§4.2's test recommendation.

### 4.2 Test coverage

**One test file exists in the entire repository:** `test_project_isolation.py`
(6,150 bytes). It requires `OS_PROJECT_NAME` and a live cloud, so it cannot run
in CI-less isolation and is not part of any local gate. There is no unit test
suite, no mocking infrastructure, and no CI workflow.

Consequence: every defect in §1 was reachable in a released `main` because
nothing would have caught it. The neutron remediation in `main` added six
suites; they live outside the repo and should be moved in.

### 4.3 Project scoping

`find_resource_by_name_or_id` and similar helpers pass a project filter where
convenient, but there is no global enforcement. A lookup can match a resource
outside the configured project. `test_project_isolation.py` exists to test
exactly this and cannot be executed without a cloud — so the claim is
**unverified, not disproven**. Treat as P1 until a mocked test proves otherwise.

### 4.4 Error handling

- 352 `except Exception` handlers across `src/`
- 368 occurrences of `str(e)` being returned to the caller

Exceptions are converted to strings and returned to the LLM. Where the underlying
error carries a full API response, internal hostname, or auth detail, that detail
reaches the model. Some of this is intentional (honest degradation is what
`set_server_dump` does correctly), but the volume means there is no systematic
review of what leaks.

This is also the mechanism that hides the P0 defects: D1, D2, D3 and D6 all
manifest as `AttributeError` inside a broad handler and surface to the caller as
`{'success': False, 'message': 'Failed to ...'}`. A wrong SDK call is
indistinguishable from a transient network error.

### 4.5 Duplication

- 94 tool files, 7,278 lines
- 9,594 lines across 9 service modules
- 21,651 lines of Python in `src/` across 117 files

The per-tool boilerplate is highly repetitive. That is the mechanism by which the
docstring/service action drift in §2 happened — the same wiring is retyped 94
times, so it drifts 94 ways. This is a P2 maintainability issue whose *symptoms*
are the P1 trust defects.

---

## 5. Recommended order

1. **D1–D5 as one PR.** All are one-line fixes against verified SDK truth.
   D5 is the only one that can return a fabricated `success: True` rather than
   an error, so it goes first within the PR — but none of them is a
   wrong-destruction defect, so they are all the same severity class.
2. **D6 needs a decision, not just a patch:** raise the floor to
   `openstacksdk>=4.20.0`, or guard the call. The repo currently ships 4.9.0 and
   the code already assumes 4.20.0.
3. **Fix the advertised-action lies (§2).** Either implement the actions or delete
   them from the docstrings and signatures. Leaving them is the actively harmful
   option.
4. **N1+N2+N3 — aggregates, extra-specs read/delete, NUMA.** One coherent
   feature, highest operational value.
5. **Add a real test suite and CI.** Move the six neutron suites into the repo.
   Every item above is a test that does not exist.
6. **Prove or drop the project-scoping claim (§4.3).** It is a headline
   security property currently resting on a test nobody can run.
7. **Assert the mutation-guard invariant (§4.1) in CI.** 53 decorated tools ==
   53 mutating tools today, by convention rather than by test. One assertion
   locks it in.

---

## Appendix: verification method

Every P0 was confirmed twice — by reading the cited source line, and by
`hasattr`/`inspect.signature` against both SDK versions:

| Symbol | 4.9.0 (locked) | 4.20.0 |
|---|---|---|
| `compute.force_delete_server` | absent | absent |
| `compute.create_server_backup` | absent | absent |
| `compute.backup_server` | present | present |
| `compute.get_service` | absent | absent |
| `compute.create_volume_attachment` | `(server, volume=None, **attrs)` | same |
| `compute.get_server_migration` | `(server_migration, server, ignore_missing=True)` | same |
| `volume.qos_specs` | **absent** | present |
| `compute.create_aggregate` | present | present |
| `compute.update_flavor_extra_specs_property` | present | present |

Gaps in this report are omissions, not verified absences. Where a subagent
asserted SDK behaviour it was not re-probed, it is marked accordingly rather than
presented as fact.

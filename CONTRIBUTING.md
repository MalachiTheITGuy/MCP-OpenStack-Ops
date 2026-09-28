# Contributing

## Branch model

This repo has two long-lived branches and everything else is short-lived.

| Branch | Purpose | How it changes |
|---|---|---|
| `main` | Released code. The only branch that ships. | **Pull requests only.** Protected: 1 approving review, no force-push, no deletions, linear history, conversations must be resolved. |
| `dev` | Integration / staging. Work accumulates here from several PRs before any of it is proven together. | **Direct pushes allowed** — that is the point. No force-push, no deletions. |
| `feature/*` | One change, one branch, one PR. | Lives minutes to days. |

### Why `dev` exists

A single PR can be green on its own and still break the next one. `dev` is where
several independently-merged PRs sit together and get exercised as a combined
state before any of them reaches `main`. It answers "do these five fixes
actually coexist?" before `main` has to.

### The flow

```
feature/thing  ──PR──▶  dev   ──PR──▶  main
                       ▲
   other PRs land here first, staged together
```

1. Branch `feature/thing` from `dev`, not from `main`.
2. Open the PR against **`dev`**, not `main`.
3. Review and merge into `dev`. It is now staged alongside the other in-flight work.
4. Open a `dev` → `main` PR when the staged batch is coherent and tested as a unit.
5. Merge that into `main`.

**Step 4 is not optional per-PR merging.** If you merge a `feature` PR straight
into `main`, the integration check it was supposed to participate in never runs.

### Practical commands

```bash
git fetch origin
git checkout dev && git pull            # start from the latest staged state
git checkout -b feature/my-change       # branch off dev
# ... work, test ...
git push -u origin feature/my-change
# open PR: feature/my-change -> dev

# when the batch is ready
git checkout dev && git pull
# open PR: dev -> main
```

### Rules that matter

- **Never branch a feature off `main`.** You will miss everything already staged in
  `dev`, and your PR will go stale the moment the next change lands.
- **Rebase `dev` onto `main` after a `main` release**, then let `dev` PRs re-verify.
- **Before opening `dev` → `main`, run the full test suite on the merged state**,
  not on individual branches. This is the only check that catches cross-PR conflicts.
- **No force-push on `main` or `dev`.** Both are protected; the server will reject it.

## Verifying changes

There is no CI configured on this repo, so the gate is local and manual. Run
these before requesting review:

```bash
# 1. Import smoke test — catches broken re-exports
python -c "import mcp_openstack_ops.functions"

# 2. Every tool module still imports and registers
python -c "
import mcp_openstack_ops.tools as t, pkgutil, importlib
n=0
for m in pkgutil.iter_modules(t.__path__):
    if not m.name.startswith('_'):
        importlib.import_module('mcp_openstack_ops.tools.'+m.name); n+=1
print(f'{n} tools OK')
"
```

`test_project_isolation.py` additionally requires `OS_PROJECT_NAME` and a live
OpenStack cloud, so it is not part of the local gate.

**If your change touches a service, check the SDK signature.** A recurring class
of bug in this project is calling a proxy method or sending a body field that
does not exist in the pinned `openstacksdk` version. See "Verifying SDK claims"
below.

## Verifying SDK claims

`pyproject.toml` pins `openstacksdk>=4.1.0,<=4.20.0`. The API is not stable across
that range, and several methods exist in only one end of it.

Before writing code that calls a proxy method or sets a resource field, confirm it
against the installed SDK rather than against documentation or memory:

```bash
python -c "
import inspect
from openstack.network.v2._proxy import Proxy
print(inspect.signature(Proxy.create_router))
print([m for m in dir(Proxy) if 'gateway' in m])
"
```

For body fields, check the resource's mapping rather than guessing the name:

```bash
python -c "
from openstack.network.v2.router import Router
print(sorted(Router._body_mapping().keys()))
"
```

A field that is not in `_body_mapping()` is not sent on the wire. Passing it
produces a silent no-op that still reports success — the failure mode this repo
has shipped most often.

### Check the version you are actually running

The pin is a **range**, and the repo's own `uv.lock` currently resolves to
**4.9.0**, while a fresh install can land on **4.20.0**. These differ in real ways:

| Symbol | 4.9.0 | 4.20.0 |
|---|---|---|
| `volume.qos_specs()` | absent | present |
| `volume.create_qos_spec()` | absent | present |
| `compute.force_delete_server()` | absent | absent |
| `compute.backup_server()` | present | present |

Code written against 4.20.0 can crash on the locked 4.9.0. Check the version
before assuming a method exists:

```bash
python -c "from importlib.metadata import version; print(version('openstacksdk'))"
python -c "
from openstack.block_storage.v3._proxy import Proxy
print(hasattr(Proxy, 'qos_specs'))
"
```

If a call is version-dependent, guard it with `hasattr` and return an honest
"not supported by the installed SDK" rather than letting it raise, and say which
versions support it.

## Code style

Follow the surrounding code. Concretely:

- Services return `(result_dict, status_bool)`; tools JSON-encode and use
  `handle_operation_result`.
- Tools use `@conditional_tool` and rely on `pkgutil` auto-registration in
  `tools/__init__.py`. There is no manual registry to update.
- Action names in the tool docstring must match the action strings the service
  actually dispatches on. These have drifted before and it makes the model
  generate calls guaranteed to fail.
- Public tool parameters must map to what the service reads. A tool that sends
  `ethertype` to a service reading `ether_type` fails silently.

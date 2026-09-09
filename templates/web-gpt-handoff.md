---
bridge_version: 1
handoff_id: <YYYYMMDD-HHMM-workspace-topic>
workspace: <workspace-slug>
from: web-gpt
to: codex
type: implementation
status: ready
parent: <source-codex-handoff-id>
source_commit: <commit-read-before-editing-or-null>
target_commit: <full-implementation-commit-sha>
created_at: <ISO-8601-with-timezone>
---

# GPT Web Handoff — <short title>

## Source handoff

`<handoffs/codex/...md>`

## Implementation summary

Describe what was actually implemented. Focus on concrete behavior, not intention.

## Changed files

- `<path>` — <what changed and why>
- `<path>` — <what changed and why>

## Key implementation decisions

### DECISION

- <implementation decision and rationale>

### ASSUMPTION

- <assumption still requiring real-world confirmation>

## Behavior / interface notes

Document any important API, CLI, config, file-format, lifecycle, compatibility or error-handling behavior.

## How to run

```bash
<commands>
```

## Checks performed by GPT Web

Only list checks that were actually performed.

- [ ] <static/logic check>
- [ ] <unit test>
- [ ] <other check>

If no executable environment was available, say so explicitly rather than claiming a test passed.

## Not verified

List anything that still requires Codex, target hardware, real services, external credentials, a specific OS, driver, compiler, network, or other unavailable environment.

- <item>

## Known limitations / risks

- <risk or limitation>

## Acceptance criteria mapping

| Criterion from source handoff | Implementation status | Needs Codex verification? |
|---|---|---|
| <criterion> | implemented / partial / not implemented | yes / no |

## Target commit

```text
<full commit SHA>
```

This is the revision Codex should inspect and verify. If later commits supersede it, create/update the next handoff rather than silently assuming `main`.

## Requested Codex verification

Describe any especially important real-world checks Codex should perform.

## Next actor

`codex`

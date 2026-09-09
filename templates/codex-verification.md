---
bridge_version: 1
handoff_id: <YYYYMMDD-HHMM-workspace-topic>
workspace: <workspace-slug>
from: codex
to: <end-or-web-gpt>
type: verification
status: <pass-or-fail>
parent: <web-gpt-handoff-id>
source_commit: <full-tested-commit-sha>
target_commit: <full-tested-commit-sha>
created_at: <ISO-8601-with-timezone>
---

# Codex Verification — <short title>

## Source

- GPT Web handoff: `<handoffs/web-gpt/...md>`
- Tested commit: `<full commit SHA>`

## Environment

Record only fields relevant to this verification.

```text
OS:
CPU:
GPU:
Driver:
Runtime / SDK:
Language runtime:
Dependencies:
External services / devices:
Other relevant environment details:
```

## Test conditions

Describe inputs, configuration, dataset/sample, permissions, network conditions, hardware state, warmup/repetition count, or other conditions needed to interpret the result.

## Commands executed

```bash
<actual commands>
```

## Acceptance results

| Criterion | Result | Evidence |
|---|---|---|
| <criterion> | PASS / FAIL / NOT TESTED | <observation or artifact path> |

## Measurements

If relevant, report units and methodology, not isolated numbers.

```text
Metric:
Method:
Result:
```

## FACT

- <directly observed fact>

## Failure details

Complete this section when `status: fail`.

### Expected

<expected behavior>

### Actual

<actual behavior>

### Error / log

```text
<key error/log excerpt>
```

### Reproducibility

`always | intermittent | once | unknown`

### Narrowed scope

Describe what has already been ruled in or ruled out.

## Artifacts

- `analysis-output/<...>` — <description>

## Conclusion

`PASS` or `FAIL`

If PASS:

```text
NEXT_ACTOR: end
```

If FAIL:

```text
NEXT_ACTOR: web-gpt
```

For FAIL, preserve this verification and create a new evidence-backed Codex handoff instead of rewriting the failure into success later.

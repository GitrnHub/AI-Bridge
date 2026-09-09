---
bridge_version: 1
handoff_id: <YYYYMMDD-HHMM-workspace-topic>
workspace: <workspace-slug>
from: <codex-or-web-gpt>
to: <codex-or-web-gpt>
type: context
status: ready
parent: <handoff-id-or-null>
source_commit: <full-sha-or-null>
target_commit: null
created_at: <ISO-8601-with-timezone>
---

# Context Snapshot — <short title>

Use this template when the main purpose is to transfer durable context rather than request an immediate code change.

## Scope

What area of work this snapshot describes.

## Why this snapshot matters

Explain what future decisions or implementations depend on this context.

## FACT

Only directly observed, verified, or authoritative facts.

- <fact>

## DECISION

Choices already accepted by the user or architecture.

- <decision>

## ASSUMPTION

Important assumptions that remain unverified.

- <assumption>

## PROPOSAL

Options still under consideration.

- <proposal>

## Environment / external state

Record relevant hardware, software, services, versions, paths, interfaces, limitations, or other external state.

## Relevant repository locations

- `<path>` — <why it matters>

## External artifacts / references

For anything not stored directly in Git, record enough identity information to find the exact item again.

```text
Name:
Version:
Source:
SHA256 (if available):
Notes:
```

## Open questions

- <question>

## What this snapshot supersedes

List older assumptions/context that should no longer be treated as current.

## Next actor / use

Describe who should consume this context and what they should do with it, if anything.

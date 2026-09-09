# Handoff Index

This file is the **routing table** for AI-Bridge.

It is intentionally short. Detailed context belongs in individual handoff documents; implementation belongs in source files; raw evidence belongs in `analysis-output/`.

## Active workspaces

| Workspace | Current handoff | State | Next actor | Target commit | Note |
|---|---|---|---|---|---|
| _none_ | — | — | — | — | No active workspace has been registered under the v1 bridge protocol yet. |

## How to update this table

When a new handoff is created:

1. Add or replace the row for its `workspace`.
2. Set `Current handoff` to the newest actionable handoff ID/path.
3. Set `State` from the handoff metadata.
4. Set `Next actor` to `codex`, `web-gpt`, or `end`.
5. Record a commit when the next action is tied to a specific revision.
6. Keep the note short; put details in the handoff itself.

Multiple rows may be active simultaneously.

Do **not** infer that the newest filename in the repository is globally current.

## History / legacy records

The repository contains an older pre-v1 demonstration handoff chain:

| Legacy chain | GPT Web result | Codex verification | Final state |
|---|---|---|---|
| `001` | `handoffs/web-gpt/001-result.md` | `handoffs/codex/001-verification.md` | PASS |

These files remain valid historical evidence. They do not define the current protocol or imply that AI-Bridge is dedicated to that example.

## Recovery rule

If this index is stale or conflicts with a specific handoff:

1. Prefer the user's latest explicit instruction.
2. Prefer the newer, specific handoff document and its referenced commit/evidence.
3. Repair this index after resolving the discrepancy.

The index is a navigation cache, not the ultimate source of technical truth.
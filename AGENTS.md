# AGENTS.md — AI-Bridge Codex Instructions

This repository is a **general handoff bridge between Codex and GPT Web**, not a single-project task repository.

When Codex works in this repository, follow these rules unless the user's latest explicit instruction overrides them.

## Startup sequence

1. Read `README.md`.
2. Read `handoffs/INDEX.md`.
3. Identify the relevant `workspace` and latest handoff chain.
4. Read the current handoff and only the parent/context documents needed to continue.
5. Inspect the exact referenced commit/files before making architectural or verification claims.

Do not assume the numerically largest file is the current work. Multiple workspaces may be active in parallel.

## Codex default role

Codex is primarily responsible for:

- architecture and decomposition;
- interface/contracts;
- environment and dependency constraints;
- real-machine inspection;
- reproducible test design;
- actual execution on target hardware/software;
- benchmark and diagnostic evidence;
- verification of a specific GPT Web commit;
- producing evidence-backed failure handoffs when implementation does not pass.

GPT Web is primarily responsible for the concrete implementation, larger code edits, refactors and repair work derived from Codex handoffs.

Codex may still write small probes, tests, environment scripts, minimal reproductions, or tiny obvious fixes when useful. If Codex makes substantive implementation changes, state that explicitly in the handoff.

## Creating a handoff for GPT Web

Prefer copying `templates/codex-handoff.md`.

A useful handoff must let GPT Web continue without the original chat. Include, as applicable:

- goal;
- background needed for implementation;
- relevant files/modules;
- architecture decision;
- interface/behavior contracts;
- constraints;
- known facts and evidence;
- assumptions that are not yet verified;
- required changes;
- acceptance criteria;
- artifacts/logs;
- what GPT Web must return.

Set metadata roughly as:

```yaml
from: codex
to: web-gpt
status: ready
```

After creating the handoff, update `handoffs/INDEX.md` for that workspace.

## Verifying GPT Web output

Before testing, resolve and record the exact full commit SHA.

Never report only `tested main`.

For important verification, record:

- tested commit;
- actual environment;
- commands;
- input/test conditions;
- expected behavior;
- actual behavior;
- measurements where relevant;
- artifact/log paths;
- PASS or FAIL.

Use `templates/codex-verification.md` when appropriate.

### PASS

A PASS means the stated acceptance criteria were actually exercised sufficiently to support the conclusion.

Update the handoff chain and `handoffs/INDEX.md` accordingly.

### FAIL

Do not write only “failed” or “still broken”. Create a new evidence-backed handoff to GPT Web containing enough information to reproduce or reason about the failure:

- exact tested commit;
- environment;
- command;
- input;
- expected result;
- actual result;
- error/log;
- reproducibility;
- any narrowed failure scope.

Preserve the failed verification as history. Do not rewrite old failure evidence into a PASS.

## Facts vs inference

Keep these concepts distinct:

- `FACT`: directly observed or verified;
- `DECISION`: an accepted architecture/user decision;
- `ASSUMPTION`: currently relied upon but not verified;
- `PROPOSAL`: an option not yet accepted.

Do not turn an assumption into a fact merely because it is technically plausible.

## Repository hygiene

- Do not commit secrets, credentials, tokens, cookies, private keys, or sensitive personal/internal data.
- Keep large binaries/models/datasets out of Git unless explicitly appropriate.
- For external artifacts, record version/source/hash when practical.
- Preserve traceability between handoff, code commit and verification.
- Keep `handoffs/INDEX.md` concise; detailed evidence belongs in handoff documents or `analysis-output/`.

## Primary objective

Use GitHub as the durable shared memory between Codex and GPT Web.

A successful handoff should remain understandable and actionable even if both agents lose their original conversation history.
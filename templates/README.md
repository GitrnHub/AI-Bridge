# AI-Bridge Templates

These templates implement the protocol defined in the repository root `README.md`.

Use the smallest template that accurately represents the handoff.

| Template | Use when |
|---|---|
| `codex-handoff.md` | Codex is giving GPT Web requirements, architecture, failure evidence, constraints, or an implementation request. |
| `web-gpt-handoff.md` | GPT Web has produced or repaired code and is handing a specific implementation commit to Codex. |
| `codex-verification.md` | Codex has actually tested a specific commit in a relevant real environment and is recording PASS/FAIL evidence. |
| `context-snapshot.md` | The main goal is to preserve durable context, environment facts, decisions, assumptions, or external state without necessarily requesting immediate code changes. |

## Rules

1. Copy a template into the appropriate `handoffs/codex/` or `handoffs/web-gpt/` directory; do not edit the template itself for each job.
2. Replace placeholders with real values or `null`; do not leave ambiguous fake values that look real.
3. Use a unique `handoff_id` and stable `workspace` slug.
4. Link handoffs using `parent` rather than repeating all prior history.
5. Record exact commit SHAs whenever implementation or verification depends on a repository revision.
6. Update `handoffs/INDEX.md` after creating an actionable handoff.
7. Preserve previous PASS/FAIL evidence; create the next handoff instead of rewriting history.

The templates are guidance, not a rigid schema. Add domain-specific sections when they materially improve reproducibility or implementation clarity.
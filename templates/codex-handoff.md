---
bridge_version: 1
handoff_id: <YYYYMMDD-HHMM-workspace-topic>
workspace: <workspace-slug>
from: codex
to: web-gpt
type: request
status: ready
parent: <handoff-id-or-null>
source_commit: <full-sha-or-null>
target_commit: null
created_at: <ISO-8601-with-timezone>
---

# Codex Handoff — <short title>

## Goal

Describe the concrete outcome GPT Web should produce.

## Background

Only include context needed to understand the implementation. Do not paste the entire prior conversation.

## Current state

Describe what exists now and what is already known.

### FACT

- <directly observed or verified fact>

### DECISION

- <accepted user/architecture decision>

### ASSUMPTION

- <important unverified assumption, if any>

## Relevant files / modules

- `<path>` — <why it matters>

## Architecture / intended design

Describe module boundaries, data flow, lifecycle, interfaces and important design constraints.

## Required changes

1. <change>
2. <change>

## Contracts

Document required inputs, outputs, types, formats, errors, side effects and backwards-compatibility behavior.

## Constraints

- <compatibility>
- <performance/resource limit>
- <dependency restriction>
- <behavior that must not regress>

## Evidence / observations

Include only evidence that materially affects implementation.

```text
<logs, measurements, error excerpts, environment observations>
```

For large evidence, reference files under `analysis-output/` instead of embedding everything here.

## Acceptance criteria

- [ ] <objective criterion>
- [ ] <objective criterion>
- [ ] <objective criterion>

Acceptance criteria should be testable. Avoid vague phrases such as “works well” or “make it fast”.

## Suggested verification plan

Describe how Codex expects to verify the implementation later in the real target environment.

## Out of scope

- <explicit non-goal>

## Expected GPT Web deliverables

- source changes;
- relevant tests/checks;
- `handoffs/web-gpt/<new-handoff>.md` based on `templates/web-gpt-handoff.md`;
- exact implementation commit SHA;
- explicit list of anything not verified.

## Next actor

`web-gpt`

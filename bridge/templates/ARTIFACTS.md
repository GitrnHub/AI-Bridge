# Artifact Manifest — <handoff-id>

Use this file for artifacts not suitable for ordinary Git tracking.

## Artifact: <name>

```yaml
name: <name>
type: <model|binary|archive|dataset|log-bundle|benchmark|other>
location_type: <release|lfs|actions|external|git>
location: <tag/url/id/path>
size_bytes: <integer>
sha256: <hex>
produced_from_commit: <full-sha-or-null>
producer: <codex|web-gpt|workflow|external>
created_at: <ISO-8601-UTC>
retention: <permanent|temporary|expiry-date|unknown>
compressed: <true|false>
compression: <zip|tar.gz|7z|null>
purpose: <why this exists>
```

### Reproduction / build command

```bash
...
```

### Compatibility / notes

- ...

### Why it is not ordinary Git content

- ...

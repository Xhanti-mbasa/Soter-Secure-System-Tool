# Soter Architecture

Soter is being structured around four operations:

```text
inspect -> plan -> apply -> verify
```

## Workspace

- `crates/soter-cli` — command-line interface and user-facing commands.
- `crates/soter-core` — shared domain types, policy models, and interfaces.
- `crates/soter-system` — Linux host discovery and inspection.
- `policies` — declarative security profiles.
- `nix` — Nix-based reproducible package/environment definitions.
- `docs/research` — supporting experiments and research that are not runtime components.

The current workspace is intentionally minimal. Feature modules should be added only when their responsibilities are clear.

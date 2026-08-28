---
name: legend
description: Use Legend's MCP tools to reason about a codebase's structure deterministically — reachability, callers/callees, change impact, structural diffs between git refs, routes/models touched by a change, import cycles, the architecture map, and the public surface. Prefer these over grepping whenever the question is "who calls this", "what breaks if I change this", or "what changed between two refs".
---

# Legend — code-graph tools

Legend serves a **resolved** code graph over MCP. Each answer is deterministic and costs **one tool call** instead of a dozen speculative greps — grep finds text occurrences (including comments, strings, and unrelated same-named symbols); Legend returns real edges. Reach for these tools whenever a question is about structure or reachability rather than raw text.

## When to call which tool

- **Before editing any function** → `blast_radius(symbol)`. Returns every symbol that transitively calls it plus every file importing its home file. Read it before you change behavior.
- **Before changing a signature** → `callers_of(symbol)` (add `transitive=true` for the full chain). Update every caller it lists.
- **Before deleting or renaming a symbol** → `callers_of(symbol)` + `blast_radius(symbol)`. If callers exist, it is not dead.
- **Before editing a whole file** → `impact_of_change(file)`.
- **To see what a function depends on** → `callees_of(symbol)`.
- **Onboarding to an unfamiliar repo** → `overview()` first, then `architecture_map()` and `public_surface()`.
- **Reviewing a change / preparing a PR** → `structural_diff(base, head)` for a symbol-level changelog; `routes_touched(base=...)` and `models_touched(base=...)` for the API/schema surface that moved.
- **Before merging** → `cycles(base=<target branch>)` to catch import cycles you would introduce.
- **Locating a symbol** → `find_symbol(name)` accepts a bare name, `Class.method`, or a full id.
- **After you have edited files** → `reindex()` so later calls reflect your changes.

## Rules of thumb

- Prefer `blast_radius` / `callers_of` over grepping for a name — resolved edges, no false positives.
- If a tool returns `ambiguous`, pass the qualified name or full id it lists.
- Paths are repo-relative, exactly as Legend reports them.
- All tools are read-only; they never modify code.

## Setup

Point your MCP client at Legend's stdio server (needs the `mcp` extra):

```json
{
  "mcpServers": {
    "legend": { "command": "uvx", "args": ["--from", "legend-lens[mcp]", "legend", "mcp", "--repo", "."] }
  }
}
```

Or, if installed: `"command": "legend", "args": ["mcp", "--repo", "."]`.

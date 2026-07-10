export type GlossaryTerm = { term: string; def: string };

export const GLOSSARY: GlossaryTerm[] = [
  { term: "Symbol", def: "A function, method, or class KnowIT extracted from your code. Each carries its name, kind, docstring, complexity, and the other symbols it calls. The diagrams are built from symbols (nodes) and their calls (edges)." },
  { term: "Complexity", def: "Cyclomatic complexity — the number of independent paths through a function. Every if / for / while / and / or / except adds one. 1 = a straight line; 11-20 is worth tests or refactoring; 20+ is high-risk. A file or class total is the sum of its functions." },
  { term: "Avg complexity / fn", def: "Mean cyclomatic complexity across all functions. Higher means the codebase is, on average, harder to test and reason about." },
  { term: "Endpoints / Routes", def: "HTTP routes KnowIT detected (method + path) — the API surface of a web codebase. Shown in the API & DB tab." },
  { term: "Graph edges", def: "Connections in the code graph — one symbol calling another, or one file importing another. The diagrams visualise these." },
  { term: "Chunks", def: "Your code split into retrievable pieces and embedded as vectors, so the Ask tab can fetch the most relevant ones to ground an answer." },
  { term: "LOC", def: "Lines of code — total non-trivial source lines across the codebase; a rough size measure." },
  { term: "Entry points", def: "Files that look like starting points (mains, app/CLI entry, servers). Good places to begin reading a new codebase." },
  { term: "Hub files", def: "Files imported by many others (high in-degree). They are central, so changes here ripple widely — worth understanding early." },
  { term: "Dead code", def: "Symbols that nothing else appears to call. Often safe to remove, or a sign of an unfinished refactor — verify first, since reflection or dynamic calls can hide real usage." },
  { term: "Coverage", def: "In Learn, the share of symbols/files you have already explored — used to suggest what to study next." },
];

export function gdef(term: string): string {
  const t = GLOSSARY.find(g => g.term.toLowerCase() === term.toLowerCase());
  return t ? t.def : "";
}

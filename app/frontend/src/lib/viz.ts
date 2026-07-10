// This file used to lazy-load @viz-js/viz (Graphviz DOT renderer),
// mermaid, and svg-pan-zoom for the old Diagrams page. None of those are
// needed now that the only architecture view is codemap (which ships its
// own self-contained interactive HTML).
//
// The file is kept empty rather than deleted so any stale import statement
// elsewhere fails fast at build time with a clear "nothing exported" error
// instead of a confusing runtime crash. If you confirm nothing imports from
// it, you can delete this file entirely.
export {};

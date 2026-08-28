import React, { useState, useEffect } from 'react';
import Logo from './Logo';
import { GITHUB_URL, PYPI_URL } from './links';
import './Docs.css';

const NAV: { id: string; label: string }[] = [
  { id: 'introduction', label: 'Introduction' },
  { id: 'quickstart', label: 'Quick start' },
  { id: 'installation', label: 'Installation' },
  { id: 'cli', label: 'CLI reference' },
  { id: 'mcp', label: 'MCP integration' },
  { id: 'configuration', label: 'Configuration' },
  { id: 'architecture', label: 'How it works' },
  { id: 'how-built', label: 'How Legend was built' },
  { id: 'faq', label: 'FAQ' },
];

const Code: React.FC<{ children: string }> = ({ children }) => {
  const [ok, setOk] = useState(false);
  const copy = () => {
    try {
      navigator.clipboard.writeText(children);
      setOk(true);
      window.setTimeout(() => setOk(false), 1400);
    } catch { /* clipboard unavailable */ }
  };
  return (
    <div className="doc-code">
      <button className={'doc-code__copy' + (ok ? ' is-ok' : '')} onClick={copy} aria-label="Copy code">
        {ok ? 'Copied' : 'Copy'}
      </button>
      <pre><code>{children}</code></pre>
    </div>
  );
};

const MCP_JSON = `{
  "mcpServers": {
    "legend": {
      "command": "uvx",
      "args": ["--from", "legend-lens[mcp]", "legend", "mcp", "--repo", "."]
    }
  }
}`;

const ZED_JSON = `{
  "context_servers": {
    "legend": {
      "command": {
        "path": "uvx",
        "args": ["--from", "legend-lens[mcp]", "legend", "mcp", "--repo", "."]
      }
    }
  }
}`;

const Docs: React.FC = () => {
  const [active, setActive] = useState('introduction');

  useEffect(() => {
    const obs = new IntersectionObserver(
      (entries) => entries.forEach((e) => { if (e.isIntersecting) setActive(e.target.id); }),
      { rootMargin: '-45% 0px -50% 0px' },
    );
    NAV.forEach((n) => { const el = document.getElementById(n.id); if (el) obs.observe(el); });
    return () => obs.disconnect();
  }, []);

  return (
    <div className="doc">
      <header className="doc-top">
        <a className="doc-top__brand" href="./">
          <Logo size={22} />
          <span className="doc-top__name">Legend</span>
          <span className="doc-top__tag">docs</span>
        </a>
        <nav className="doc-top__links">
          <a href="./">Home</a>
          <a href="./#mcp">MCP</a>
          <a href={PYPI_URL} target="_blank" rel="noopener noreferrer">PyPI</a>
          <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer">GitHub</a>
        </nav>
      </header>

      <div className="doc-body">
        <aside className="doc-side">
          <div className="doc-side__inner">
            <span className="doc-side__title">Documentation</span>
            <nav>
              {NAV.map((n) => (
                <a key={n.id} href={'#' + n.id} className={'doc-side__link' + (active === n.id ? ' is-active' : '')}>
                  {n.label}
                </a>
              ))}
            </nav>
          </div>
        </aside>

        <main className="doc-main">
          <p className="doc-kicker">Legend — local-first codebase intelligence</p>
          <h1 className="doc-h1">Documentation</h1>
          <p className="doc-lead">
            Everything to install Legend, drive it from the command line, wire it into your coding agent
            over MCP, configure a model, and understand how it works — plus the story of how it was built.
          </p>

          {/* Introduction */}
          <section id="introduction">
            <h2>Introduction</h2>
            <p>
              Legend turns an unfamiliar codebase into something you can navigate. Point it at a repository
              or folder and it indexes the code <strong>once</strong> — symbols, a call/import graph, and
              searchable embeddings — then every view reads from that single in-memory index. It runs
              entirely on your machine: the only things that ever leave are the initial <code>git clone</code>{' '}
              and, if you enable AI answers, calls to a model you configure. No account, no telemetry, no cloud.
            </p>
            <p>Legend has three ways in:</p>
            <ul>
              <li><strong>The app</strong> — a local web UI that maps architecture, explains files, answers questions, and tracks change over time.</li>
              <li><strong>The MCP server</strong> — deterministic graph tools for coding agents (Claude Code, Cursor, Zed, …).</li>
              <li><strong>The CLI</strong> — <code>legend context</code> to emit a derived <code>AGENTS.md</code>, and <code>legend check</code> as a CI structural-regression gate.</li>
            </ul>
            <p className="doc-note">
              The PyPI package is <code>legend-lens</code> (PyPI reserves the bare name <code>legend</code>);
              the command it installs is <code>legend</code>.
            </p>
          </section>

          {/* Quick start */}
          <section id="quickstart">
            <h2>Quick start</h2>
            <p>With <a href="https://docs.astral.sh/uv/" target="_blank" rel="noopener noreferrer">uv</a> installed, you don't have to install Legend at all:</p>
            <Code>{`uvx legend-lens .                                   # index the current folder
uvx legend-lens https://github.com/pallets/click    # or clone + index any repo`}</Code>
            <p>
              It indexes the code and opens <code>http://127.0.0.1:8100</code>. Structure, files, search, the
              graph, and metrics all work immediately — no API key or configuration required. No uv? Install it
              once with <code>pip install uv</code>, or use pip/pipx below.
            </p>
          </section>

          {/* Installation */}
          <section id="installation">
            <h2>Installation</h2>
            <p>You need <strong>Python 3.10+</strong> and <strong>git</strong>. Pick a method:</p>
            <Code>{`uvx legend-lens .              # zero-install; always the latest
pipx install legend-lens       # isolated, permanent \`legend\` command
pip install legend-lens        # into the current virtual environment`}</Code>
            <p>After a pip/pipx install you have two equivalent commands: <code>legend</code> and <code>legend-lens</code>.</p>
            <h3>Optional features (extras)</h3>
            <p>The base install is lean and fully offline. Heavier features are opt-in:</p>
            <table className="doc-table">
              <thead><tr><th>Extra</th><th>Adds</th><th>Install</th></tr></thead>
              <tbody>
                <tr><td><code>semantic</code></td><td>On-device semantic search (ChromaDB)</td><td><code>pip install "legend-lens[semantic]"</code></td></tr>
                <tr><td><code>llm</code></td><td>AI answers &amp; explanations (LiteLLM)</td><td><code>pip install "legend-lens[llm]"</code></td></tr>
                <tr><td><code>treesitter</code></td><td>10+ languages (Go, Java, Rust, C#, …)</td><td><code>pip install "legend-lens[treesitter]"</code></td></tr>
                <tr><td><code>export</code></td><td>Word / PDF report export</td><td><code>pip install "legend-lens[export]"</code></td></tr>
                <tr><td><code>mcp</code></td><td>The <code>legend mcp</code> server for agents</td><td><code>pip install "legend-lens[mcp]"</code></td></tr>
                <tr><td><code>all</code></td><td>Everything above</td><td><code>pip install "legend-lens[all]"</code></td></tr>
              </tbody>
            </table>
          </section>

          {/* CLI reference */}
          <section id="cli">
            <h2>CLI reference</h2>
            <p>One binary, four modes.</p>

            <h3><code>legend</code> — the app</h3>
            <Code>{`legend .                              # index this folder + open the browser
legend C:\\path\\to\\project            # a specific local folder
legend https://github.com/user/repo   # clone + index a remote repo
legend                                # start empty; paste a repo in the UI`}</Code>
            <table className="doc-table">
              <thead><tr><th>Option</th><th>Default</th><th>Description</th></tr></thead>
              <tbody>
                <tr><td><code>source</code></td><td>—</td><td>Git URL, local folder, or <code>.</code></td></tr>
                <tr><td><code>--port</code></td><td><code>8100</code></td><td>Port to serve on</td></tr>
                <tr><td><code>--host</code></td><td><code>127.0.0.1</code></td><td>Bind address (keep on loopback)</td></tr>
                <tr><td><code>--data-dir</code></td><td><code>~/.legend/cache</code></td><td>Where indexes are cached</td></tr>
                <tr><td><code>--no-open</code></td><td>off</td><td>Don't auto-open the browser</td></tr>
              </tbody>
            </table>

            <h3><code>legend mcp</code> — the MCP server</h3>
            <p>Serves the graph tools over stdio for coding agents. See <a href="#mcp">MCP integration</a>.</p>
            <Code>{`legend mcp --repo .`}</Code>

            <h3><code>legend context</code> — derived AGENTS.md</h3>
            <p>Emits an always-fresh context file (route table, module boundaries, entry points, constraints) straight from the code graph.</p>
            <Code>{`legend context --write AGENTS.md      # or: legend context  (prints to stdout)`}</Code>

            <h3><code>legend check</code> — CI regression gate</h3>
            <p>Exits non-zero when a change introduces a structural regression — a new import cycle, a removed public symbol, or a complexity spike. Run at your repo's git root.</p>
            <Code>{`legend check --base main               # exit 0 = clean, 1 = regression, 2 = error
legend check --base origin/main --strict`}</Code>
          </section>

          {/* MCP integration */}
          <section id="mcp">
            <h2>MCP integration</h2>
            <p>
              Legend runs as an <a href="https://modelcontextprotocol.io" target="_blank" rel="noopener noreferrer">MCP</a>{' '}
              server, giving any MCP client deterministic answers about your code's structure — the questions
              that otherwise cost an agent a dozen greps and tens of thousands of tokens. The pitch is
              <strong> cost and determinism</strong>, not smarter answers: one call, one verifiable result.
            </p>
            <p>Launch it (the <code>[mcp]</code> extra pulls the small MCP SDK):</p>
            <Code>{`uvx --from "legend-lens[mcp]" legend mcp --repo .
# or, once installed:  pip install "legend-lens[mcp]"   then   legend mcp --repo .`}</Code>

            <h3>Universal config</h3>
            <p>Most clients accept this standard <code>mcpServers</code> block — add it to the client's MCP config:</p>
            <Code>{MCP_JSON}</Code>
            <p className="doc-note">
              For desktop apps that don't launch in your project directory, replace <code>--repo .</code> with an
              absolute path (e.g. <code>--repo /Users/you/project</code>). Each server instance indexes one repo.
            </p>

            <h3>Per-platform setup</h3>

            <h4>Claude Code</h4>
            <Code>{`claude mcp add legend -- uvx --from "legend-lens[mcp]" legend mcp --repo .`}</Code>
            <p>Then run <code>/mcp</code> in Claude Code to confirm the <code>legend</code> tools are connected.</p>

            <h4>Claude Desktop</h4>
            <p>Edit the config file, add the universal block, and restart:</p>
            <ul>
              <li>macOS: <code>~/Library/Application Support/Claude/claude_desktop_config.json</code></li>
              <li>Windows: <code>%APPDATA%\\Claude\\claude_desktop_config.json</code></li>
            </ul>

            <h4>Cursor</h4>
            <p>Create <code>.cursor/mcp.json</code> in your project (or <code>~/.cursor/mcp.json</code> globally) with the universal block. Cursor lists it under Settings → MCP.</p>

            <h4>Windsurf</h4>
            <p>Open Settings → Cascade → MCP (or edit <code>~/.codeium/windsurf/mcp_config.json</code>) and add the universal block.</p>

            <h4>Zed</h4>
            <p>Zed uses <code>context_servers</code> in <code>settings.json</code>:</p>
            <Code>{ZED_JSON}</Code>

            <h4>Cline / Continue (VS Code)</h4>
            <p>Both read the same <code>mcpServers</code> shape — add the universal block to Cline's <code>cline_mcp_settings.json</code> (Cline → MCP Servers → Configure) or Continue's assistant/<code>config</code> file.</p>

            <p className="doc-note">
              MCP client config formats evolve. If a path here differs from your version, search for “MCP” in the
              client's settings and paste the universal server block — the command and args are the same everywhere.
            </p>

            <h3>Tools</h3>
            <p>All read-only. The differentiated ones are the graph operations grep can't cheaply derive:</p>
            <table className="doc-table">
              <thead><tr><th>Tool</th><th>Answers</th></tr></thead>
              <tbody>
                <tr><td><code>blast_radius(symbol)</code></td><td>Everything transitively affected if this symbol changes (callers + importers).</td></tr>
                <tr><td><code>callers_of</code> / <code>callees_of</code></td><td>Resolved call edges, optionally transitive — not text matches.</td></tr>
                <tr><td><code>impact_of_change(file)</code></td><td>Blast radius of editing a whole file.</td></tr>
                <tr><td><code>structural_diff(base, head)</code></td><td>Symbol / import / complexity changes between two git refs.</td></tr>
                <tr><td><code>routes_touched</code> / <code>models_touched</code></td><td>HTTP routes / data models whose file is in a change set.</td></tr>
                <tr><td><code>cycles(base?)</code></td><td>Import cycles — or only those introduced since a ref.</td></tr>
                <tr><td><code>architecture_map</code> / <code>public_surface</code></td><td>Area dependencies; entry points, exports, cross-file API.</td></tr>
                <tr><td><code>find_symbol</code> / <code>overview</code> / <code>reindex</code></td><td>Resolve a name; orient; refresh after edits.</td></tr>
              </tbody>
            </table>
            <p>
              Ship <a href={GITHUB_URL + '/blob/main/skills/legend/SKILL.md'} target="_blank" rel="noopener noreferrer"><code>skills/legend/SKILL.md</code></a>{' '}
              alongside so the agent knows <em>when</em> to call them: <code>blast_radius</code> before editing a
              function, <code>callers_of</code> before changing a signature, <code>cycles</code> before merging.
            </p>

            <h3>Troubleshooting</h3>
            <ul>
              <li><strong>“command not found: uvx”</strong> — install uv: <code>pip install uv</code>. First launch downloads the package (a few seconds), then it's cached.</li>
              <li><strong>Server fails / no tools</strong> — a stale global <code>legend</code> can shadow a newer one. Use the module form: <code>python -m legend.mcp_server --repo .</code> from an environment that has <code>legend-lens[mcp]</code>.</li>
              <li><strong>First call is slow</strong> — it indexes the repo once, then caches. The connection and tool list are instant; only the first tool <em>call</em> builds the index.</li>
            </ul>
          </section>

          {/* Configuration */}
          <section id="configuration">
            <h2>Configuration</h2>
            <p>
              Everything is optional. Indexing, structure, files, search, the graph, metrics, and tracking all work
              offline with no model. Only the <strong>Ask</strong> tab and per-function explanations call an LLM —
              and you bring your own (install the <code>llm</code> extra, then set a provider in the app's Settings
              tab or via environment variables).
            </p>
            <table className="doc-table">
              <thead><tr><th>Variable</th><th>Purpose</th></tr></thead>
              <tbody>
                <tr><td><code>LEGEND_LLM_PROVIDER</code></td><td><code>openai | anthropic | gemini | groq | ollama | openrouter | custom</code></td></tr>
                <tr><td><code>LEGEND_LLM_MODEL</code></td><td>Model name for the chosen provider</td></tr>
                <tr><td><code>LEGEND_LLM_BASE_URL</code></td><td>Endpoint for Ollama (<code>http://localhost:11434</code>) or a custom provider</td></tr>
                <tr><td><code>OPENAI_API_KEY</code>, <code>ANTHROPIC_API_KEY</code>, …</td><td>Set only the one you use</td></tr>
                <tr><td><code>LEGEND_EMBED_BACKEND</code></td><td><code>auto | hybrid | bm25 | chroma</code> (retrieval mode)</td></tr>
                <tr><td><code>LEGEND_DATA_DIR</code></td><td>Where indexes and clones are cached</td></tr>
              </tbody>
            </table>
            <Code>{`# PowerShell example
$env:LEGEND_LLM_PROVIDER = "openai"
$env:LEGEND_LLM_MODEL    = "gpt-4o-mini"
$env:OPENAI_API_KEY      = "sk-..."
legend .`}</Code>
            <p>Your key stays on your machine and is used only to call the provider you chose.</p>
          </section>

          {/* How it works */}
          <section id="architecture">
            <h2>How it works</h2>
            <p>Three components live side by side and wire together by relative path:</p>
            <table className="doc-table">
              <thead><tr><th>Component</th><th>What it is</th></tr></thead>
              <tbody>
                <tr><td><code>app/</code></td><td>A React + Vite frontend over a thin FastAPI backend. When installed, the backend serves the pre-built UI on one port.</td></tr>
                <tr><td><code>engine/</code></td><td>The <code>legend</code> Python package: indexing, retrieval, graph, tracking, analysis.</td></tr>
                <tr><td><code>diagrams/</code></td><td><code>codemap</code> — a standalone, stdlib-only architecture-map generator.</td></tr>
              </tbody>
            </table>
            <p>Indexing runs in six stages, and every feature after that is a pure read over the resulting in-memory index:</p>
            <ol>
              <li><strong>Ingest / clone</strong> — resolve a local folder or clone a Git URL; work out what is actually source.</li>
              <li><strong>Parse</strong> — AST for Python, a brace-matched hand-written parser for JS/TS, optional tree-sitter for 10+ more languages.</li>
              <li><strong>Build the code graph</strong> — files and symbols become nodes; <code>contains</code>, <code>calls</code>, <code>imports</code>, <code>inherits</code>, and <code>method_of</code> become edges.</li>
              <li><strong>Chunk</strong> — symbols and module-level code become retrievable chunks.</li>
              <li><strong>Build retrievers</strong> — a stdlib BM25 index plus optional on-device Chroma embeddings.</li>
              <li><strong>Cache</strong> — the parsed tree, graph, and chunks are persisted, keyed by commit + file fingerprints.</li>
            </ol>
          </section>

          {/* How Legend was built */}
          <section id="how-built">
            <h2>How Legend was built</h2>
            <p>
              A short engineering tour — the decisions behind the code, in the spirit of the “how it works” docs
              that companies like Google and Meta publish for their own tools.
            </p>

            <h3>Design principles</h3>
            <p>Three ideas shaped every part of it:</p>
            <ul>
              <li><strong>Local-first.</strong> Your source is indexed, embedded, searched, graphed, and tracked entirely on your machine. The only outbound traffic is a clone you asked for and, optionally, a model you configured.</li>
              <li><strong>Stdlib-first engine.</strong> The core has no heavy dependencies — Python's <code>ast</code>, a hand-rolled code graph, and a from-scratch BM25 implementation. Heavy features (embeddings, LLMs, tree-sitter, report export) are optional extras, so the base install stays small and starts instantly.</li>
              <li><strong>Determinism over cleverness.</strong> Where the graph can't be sure, it prefers a missing edge to a wrong one. That single rule is what makes the agent tools trustworthy.</li>
            </ul>

            <h3>The code graph &amp; call resolution</h3>
            <p>
              Naive “who calls this” answers come from grepping a name — and they're wrong: comments, strings, and
              unrelated same-named symbols all match. Legend resolves calls by <em>receiver kind</em> recorded at
              parse time. A <code>self.method()</code> call resolves within the class and its bases; a typed{' '}
              <code>obj.method()</code> resolves the class cross-file then its method; an untyped attribute call is
              trusted only when a same-file definition exists; a bare call climbs a scoped ladder
              (unambiguous repo-wide → same-file → exactly-one imported match) and, if still ambiguous, is left
              unresolved. The result: real edges, not textual coincidences — which is exactly what makes{' '}
              <code>blast_radius</code> and <code>callers_of</code> worth a tool call.
            </p>

            <h3>Retrieval</h3>
            <p>
              Search fuses a stdlib BM25 keyword index with optional on-device semantic embeddings using Reciprocal
              Rank Fusion, then expands the top results through the call graph so answers pull in related code you
              didn't name. Without the semantic extra it gracefully falls back to BM25 alone — still useful, still local.
            </p>

            <h3>Caching &amp; security</h3>
            <p>
              The parsed tree, graph, and chunks are cached in a pickle keyed by the commit plus each file's
              modification time and size, and signed with a per-install HMAC key — a tampered or unsigned cache is
              treated as a miss and never unpickled blindly. Cloning is transport-allowlisted and argument-injection
              guarded; the server binds to loopback; all repository, LLM, and README content renders as text so an
              untrusted README can't run script; and on-device embedding telemetry is explicitly disabled.
            </p>

            <h3>Packaging &amp; distribution</h3>
            <p>
              The engine, the FastAPI app, and the codemap tool live in three separate source trees but ship as one
              wheel — mapped together with setuptools <code>package-dir</code> without moving a single file — with the
              built frontend bundled in so <code>uvx legend-lens</code> serves the whole UI from one command. On top
              of pip/uvx, Legend speaks MCP for agents, emits derived context with <code>legend context</code>, and
              gates CI with <code>legend check</code>; standalone binary and Docker distribution are on the roadmap.
            </p>

            <h3>Testing</h3>
            <p>
              A fixed sample repository pins exact invariants (symbol, call, import, edge, and chunk counts), so a
              regression in parsing or graph construction fails a test immediately. The engine suite covers parsing,
              the graph, retrieval, and the analyzers; a backend suite exercises the FastAPI routes end to end.
            </p>
          </section>

          {/* FAQ */}
          <section id="faq">
            <h2>FAQ</h2>
            <h4>Is any of my code sent anywhere?</h4>
            <p>No — indexing, search, the graph, and metrics are fully local. The only outbound traffic is the initial <code>git clone</code> for a URL you give, and, if you enable AI answers, calls to the provider you configured.</p>
            <h4>Why is the package called <code>legend-lens</code>?</h4>
            <p>PyPI reserves the bare name <code>legend</code>. The distribution is <code>legend-lens</code>; the command it installs is still <code>legend</code>.</p>
            <h4>Which languages are supported?</h4>
            <p>Python has the deepest analysis (full AST). JavaScript/TypeScript is best-effort built in. Install the <code>treesitter</code> extra for structural parsing of Go, Java, Rust, C#, Ruby, PHP, C, C++, and more.</p>
            <h4>Do I need a GPU or an API key?</h4>
            <p>No. Embeddings run on-device; the app is fully usable with no key. Only synthesized AI answers need a model you choose.</p>
          </section>

          <footer className="doc-foot">
            <span>© {new Date().getFullYear()} Legend — open source, local-first · MIT</span>
            <span className="doc-foot__links">
              <a href="./">Home</a>
              <a href={PYPI_URL} target="_blank" rel="noopener noreferrer">PyPI</a>
              <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer">GitHub</a>
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
};

export default Docs;

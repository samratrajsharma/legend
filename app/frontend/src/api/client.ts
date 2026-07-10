import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 600_000,
});

export default api;

// ── Types ───────────────────────────────────────────────────────
// ── codemap data shape (same as the embedded JSON in the standalone HTML) ──
export type CodemapArea = {
  id: string; name: string; band: number;
  files: number; lines: number;
  // computed positions added by the HTML's JS — we recompute these in React
  w?: number; h?: number; cx?: number; cy?: number;
};
export type CodemapFile = {
  n: string;        // basename
  area: string;
  l: number;        // lines
  c: { n: string; doc?: string; m?: string[] }[];     // classes
  f: { n: string; sig?: string; doc?: string }[];     // functions
  deps: string[];   // file paths it depends on (in-repo)
  used: string[];   // file paths that depend on it
  doc: string;
  ok: boolean;
};
export type CodemapData = {
  areas: CodemapArea[];
  E: [string, string][];
  AREAFILES: Record<string, string[]>;
  FILEINDEX: Record<string, CodemapFile>;
  SRC: Record<string, string>;
  AREADESC: Record<string, string>;
  BANDNAME: string[];
  COLORS: string[];
  EMBED: boolean;
  stats: { files: number; loc: number; areas: number; edges: number; depth: number };
};

export type RepoListItem = {
  repo_id: string; name: string; commit: string; source: string; status: string;
};
export type ConnectRepoResponse = {
  repo_id: string; name: string; commit: string; status: string;
};
export type OverviewResponse = {
  stats: Record<string, any>;
  insights: {
    entry_files: string[];
    hub_files: { file: string; imported_by: number; imports: number; degree: number }[];
    complex_symbols: { symbol: string; file: string; complexity: number }[];
    likely_unused: { symbol: string; file: string }[];
    loc_total: number; avg_complexity: number; n_python: number; n_symbols: number;
  };
  languages: { language: string; files: number; loc: number; symbols: number }[];
  config_surface: { source: string; kind: string; items: string[] }[];
};
export type AskSource = {
  file: string; start_line: number; end_line: number; name: string;
  via: string; score: number; text: string;
};
export type AskResponse = {
  question: string; answer: string | null; used_llm: boolean;
  needs_llm?: boolean; reason?: string | null; sources: AskSource[];
};
export type ApiRoute = { method: string; path: string; file: string };
export type DbModel  = { model: string; file: string; table: string };

export type TimelineMetrics = { files: number; symbols: number; loc: number; avg_complexity: number; dead_code: number };
export type TimelineEvent = {
  ts: string; kind: string; summary: string; sha?: string; author?: string; metrics?: TimelineMetrics;
  files_added?: string[]; files_removed?: string[];
  files_modified?: { file: string; loc: number; loc_was: number; cx_total: number; cx_was: number }[];
  symbols_added?: { file: string; symbol: string; kind?: string; cx?: number }[];
  symbols_removed?: { file: string; symbol: string }[];
  symbols_changed?: { file: string; symbol: string; cx?: number; cx_was?: number }[];
};

export type WorkspaceFolder = {
  rid: string; name: string; source: string; captures: number;
  last_ts: string | null; last_summary: string | null;
  metrics: TimelineMetrics | null; connected: boolean;
};

export type LlmProvider = {
  id: string; label: string; models: string[];
  needs_base_url: boolean; default_base: string; key_env: string; key_present: boolean;
};
export type LlmConfigBody = { provider: string; model: string; base_url?: string; api_key?: string };

export type FnCall = { id: string; file: string; name: string };
export type FunctionExplainResponse = {
  file: string; symbol: string; name: string; kind: string; language: string;
  line_start: number; line_end: number; complexity: number | null;
  docstring: string; code: string;
  callers: FnCall[]; callees: FnCall[];
  explanation: string | null; used_llm: boolean; reason?: string | null;
};

export const kycApi = {
  // Repos
  listRepos: () => api.get<RepoListItem[]>('/repos'),
  connectRepo: (source: string) => api.post<ConnectRepoResponse>('/repos', { source }),
  repoStatus: (rid: string) => api.get<{ repo_id: string; status: string; pct: number; message: string; error: string | null; name: string; commit: string }>(`/repos/${rid}/status`),
  deleteRepo: (rid: string) => api.delete(`/repos/${rid}`),
  llmStatus: () => api.get<{ configured: boolean; model: string | null; provider: string | null }>('/llm-status'),
  llmProviders: () => api.get<{ providers: LlmProvider[]; current: { provider: string | null; model: string | null; base_url: string | null } }>('/llm/providers'),
  llmOllamaModels: (base_url?: string) => api.get<{ ok: boolean; base_url: string; models: string[]; error?: string }>('/llm/ollama-models', { params: { base_url } }),
  setLlmConfig: (body: LlmConfigBody) => api.post<{ configured: boolean; model: string | null; provider: string | null; test_ok: boolean; test_message: string }>('/llm/config', body),
  testLlm: (body: LlmConfigBody) => api.post<{ ok: boolean; message: string; model: string | null }>('/llm/test', body),

  // Overview / Files
  overview: (rid: string) => api.get<OverviewResponse>(`/repos/${rid}/overview`),
  files: (rid: string) => api.get<{ files: string[]; by_language: Record<string, string[]> }>(`/repos/${rid}/files`),
  fileSummary: (rid: string, file: string) => api.get(`/repos/${rid}/files/summary`, { params: { file } }),
  fileContent: (rid: string, file: string) =>
    api.get<{ file: string; language: string; loc: number; text: string }>(`/repos/${rid}/files/content`, { params: { file } }),

  // codemap — the ONLY architecture / diagrams visualization.
  // Three-layer interactive HTML (areas → files → source) is served via iframe.
  codemapStats:  (rid: string, refresh = 0) =>
    api.get<{ stats: { files: number; loc: number; areas: number; edges: number; depth: number }; available: boolean }>(
      `/repos/${rid}/codemap/stats`, { params: { refresh } }
    ),
  codemapStatus: () => api.get<{ available: boolean; load_error: string | null; expected_path: string; expected_path_exists: boolean; codemap_module_file: string | null }>('/codemap/status'),
  codemapUrl: (rid: string, refresh = 0, embed = 1) =>
    `/api/v1/repos/${rid}/codemap?refresh=${refresh}&embed=${embed}`,
  codemapData: (rid: string, refresh = 0) =>
    api.get<CodemapData>(`/repos/${rid}/codemap/data`, { params: { refresh } }),

  // LLM-powered file explanation (for the deep-dive's "LLM" tab)
  explainFile: (rid: string, file: string) =>
    api.get<{ explanation: string | null; used_llm: boolean; reason: string | null }>(`/repos/${rid}/files/explain`, { params: { file } }),
  explainFunction: (rid: string, file: string, symbol: string, override?: { provider?: string; model?: string; base_url?: string }) =>
    api.get<FunctionExplainResponse>(`/repos/${rid}/functions/explain`, { params: { file, symbol, ...(override || {}) } }),

  // Graph nodes — still needed by Intel/Impact symbol picker.
  graphNodes:    (rid: string) => api.get<{ nodes: string[] }>(`/repos/${rid}/graph/nodes`),

  // API & DB
  apiDb: (rid: string) => api.get<{ routes: ApiRoute[]; models: DbModel[] }>(`/repos/${rid}/api-db`),

  // Ask
  ask: (rid: string, question: string) => api.post<AskResponse>(`/repos/${rid}/ask`, { question }),

  // Track
  trackCommits: (rid: string, n = 30) => api.get<{ is_git: boolean; commits: { sha: string; short: string; author: string; date: string; subject: string }[] }>(`/repos/${rid}/track/commits`, { params: { n } }),
  trackDiff:    (rid: string, base_commit: string, head_commit: string) =>
    api.post<{ diff: any; changelog: string; arch_delta_dot: string }>(`/repos/${rid}/track/diff`, { base_commit, head_commit }),

  // Timeline (over-time change tracking)
  trackCapture:  (rid: string) => api.post<{ changed: boolean; baseline?: boolean; event: TimelineEvent | null; metrics?: TimelineMetrics }>(`/repos/${rid}/track/capture`),
  trackTimeline: (rid: string) => api.get<{ events: TimelineEvent[]; count: number }>(`/repos/${rid}/track/timeline`),
  trackTrends:   (rid: string) => api.get<{ series: (TimelineMetrics & { ts: string })[] }>(`/repos/${rid}/track/trends`),
  trackNarrate:  (rid: string, ts: string, override?: { provider?: string; model?: string; base_url?: string }) =>
    api.post<{ narration: string | null; cached?: boolean; needs_llm?: boolean; reason?: string }>(`/repos/${rid}/track/narrate`, { ts, ...(override || {}) }),
  workspace:     () => api.get<{ folders: WorkspaceFolder[] }>(`/workspace`),
  trackDirty:     (rid: string) => api.get<{ trackable: boolean; dirty: boolean; has_baseline: boolean }>(`/repos/${rid}/track/dirty`),
  trackImportGit: (rid: string) => api.post<{ is_git: boolean; imported: number }>(`/repos/${rid}/track/import-git`),

  // Intel
  intelTechdebt: (rid: string) => api.get<any>(`/repos/${rid}/intel/techdebt`),
  intelMemory:   (rid: string) => api.get<{ decisions: any[]; errors: any[]; memory: any[] }>(`/repos/${rid}/intel/memory`),
  intelMemoryAdd:(rid: string, kind: string, title: string, body: string) =>
    api.post(`/repos/${rid}/intel/memory/add`, { kind, title, body }),
  intelMemoryDel:(rid: string, kind: string, eid: string) =>
    api.delete(`/repos/${rid}/intel/memory/${kind}/${eid}`),
  intelImpact:   (rid: string, symbol: string) => api.get<any>(`/repos/${rid}/intel/impact`, { params: { symbol } }),
  intelCoverage: (rid: string) => api.get<any>(`/repos/${rid}/intel/coverage`),
};

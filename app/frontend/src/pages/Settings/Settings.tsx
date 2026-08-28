import { useEffect, useState } from 'react';
import { kycApi, LlmProvider } from '../../api/client';
import './Settings.css';

export default function Settings() {
  const [providers, setProviders] = useState<LlmProvider[]>([]);
  const [provider, setProvider] = useState('');
  const [model, setModel] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [current, setCurrent] = useState<{ provider: string | null; model: string | null }>({ provider: null, model: null });
  const [ollama, setOllama] = useState<{ loading: boolean; models: string[]; error?: string }>({ loading: false, models: [] });
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState('');

  const load = () => {
    kycApi.llmProviders().then(r => {
      setProviders(r.data.providers);
      setCurrent({ provider: r.data.current.provider, model: r.data.current.model });
      if (r.data.current.provider) setProvider(r.data.current.provider);
      if (r.data.current.model) setModel(r.data.current.model);
      if (r.data.current.base_url) setBaseUrl(r.data.current.base_url);
    }).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  const sel = providers.find(p => p.id === provider);
  const isOllama = provider === 'ollama';
  const canSubmit = !!provider && !!model.trim();

  const onProvider = (id: string) => {
    setProvider(id); setModel(''); setTestResult(null); setSaved('');
    const p = providers.find(x => x.id === id);
    setBaseUrl(p?.needs_base_url ? (p.default_base || '') : '');
    setOllama({ loading: false, models: [] });
  };

  const detectOllama = () => {
    setOllama({ loading: true, models: [] });
    kycApi.llmOllamaModels(baseUrl || sel?.default_base).then(r => {
      setOllama({ loading: false, models: r.data.models || [], error: r.data.ok ? undefined : r.data.error });
    }).catch(e => setOllama({ loading: false, models: [], error: String(e) }));
  };

  const doTest = () => {
    setTesting(true); setTestResult(null);
    kycApi.testLlm({ provider, model, base_url: baseUrl, api_key: apiKey }).then(r => {
      setTestResult({ ok: r.data.ok, message: r.data.message });
    }).catch(e => setTestResult({ ok: false, message: String(e) })).finally(() => setTesting(false));
  };

  const doSave = () => {
    setSaving(true); setSaved('');
    kycApi.setLlmConfig({ provider, model, base_url: baseUrl, api_key: apiKey }).then(r => {
      setSaved(r.data.test_ok ? 'Saved and verified — AI features are live.' : `Saved. Connection test: ${r.data.test_message}`);
      setApiKey(''); load();
    }).catch(e => setSaved('Save failed: ' + String(e))).finally(() => setSaving(false));
  };

  return (
    <div className="settings">
      <div className="page-header">
        <h1>AI / LLM settings</h1>
        <p>Connect a language model so Ask and the LLM explanations can generate answers. It stays local unless you pick a cloud provider.</p>
      </div>

      <div className="set-card">
        <div className="set-status">
          <span className={`set-dot${current.model ? ' set-dot--on' : ''}`} />
          {current.model
            ? <span>Currently using <strong>{current.model}</strong></span>
            : <span>No model configured — the app runs in context-only mode (structure, files, graphs and metrics still work).</span>}
        </div>
      </div>

      <div className="set-card">
        <label className="set-label">Provider</label>
        <select className="set-input" value={provider} onChange={e => onProvider(e.target.value)}>
          <option value="">Select a provider…</option>
          {providers.map(p => (
            <option key={p.id} value={p.id}>{p.label}{p.key_env && !p.key_present ? ' (no key set)' : ''}</option>
          ))}
        </select>

        {isOllama && (
          <>
            <label className="set-label">Ollama URL</label>
            <div className="set-row">
              <input className="set-input" value={baseUrl} onChange={e => setBaseUrl(e.target.value)} placeholder="http://localhost:11434" />
              <button type="button" className="set-btn set-btn--ghost" onClick={detectOllama} disabled={ollama.loading}>
                {ollama.loading ? 'Detecting…' : 'Detect installed models'}
              </button>
            </div>
            {ollama.error && <p className="set-hint set-hint--err">Couldn’t reach Ollama: {ollama.error}. Is it running? (run “ollama serve”)</p>}
            {ollama.models.length > 0 && (
              <div className="set-chips">
                {ollama.models.map(m => (
                  <button key={m} type="button" className={`set-chip${model === m ? ' set-chip--on' : ''}`} onClick={() => setModel(m)}>{m}</button>
                ))}
              </div>
            )}
            {!ollama.loading && ollama.models.length === 0 && !ollama.error && (
              <p className="set-hint">Click “Detect installed models” to list what you’ve pulled, or type a model below.</p>
            )}
          </>
        )}

        <label className="set-label">Model</label>
        {sel && sel.models.length > 0 && !isOllama && (
          <div className="set-chips">
            {sel.models.map(m => (
              <button key={m} type="button" className={`set-chip${model === m ? ' set-chip--on' : ''}`} onClick={() => setModel(m)}>{m}</button>
            ))}
          </div>
        )}
        <input className="set-input" value={model} onChange={e => setModel(e.target.value)}
               placeholder={isOllama ? 'e.g. qwen2.5-coder:7b' : 'model name'} />

        {sel && sel.key_env && (
          <>
            <label className="set-label">
              API key {sel.key_present && <span className="set-hint">(a key is already saved — leave blank to keep it)</span>}
            </label>
            <input className="set-input" type="password" value={apiKey} onChange={e => setApiKey(e.target.value)}
                   placeholder={sel.key_present ? '•••••••• (saved)' : sel.key_env} />
            <p className="set-hint">Stored in know-your-code/app/backend/.env on this machine only.</p>
          </>
        )}

        <div className="set-actions">
          <button type="button" className="set-btn set-btn--ghost" onClick={doTest} disabled={!canSubmit || testing}>
            {testing ? 'Testing…' : 'Test connection'}
          </button>
          <button type="button" className="set-btn set-btn--primary" onClick={doSave} disabled={!canSubmit || saving}>
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
        {testResult && <p className={`set-result${testResult.ok ? ' set-result--ok' : ' set-result--err'}`}>{testResult.ok ? '✓ ' : '✗ '}{testResult.message}</p>}
        {saved && <p className="set-result set-result--ok">{saved}</p>}
      </div>

      <div className="set-card set-help">
        <h3>Which should I pick?</h3>
        <ul>
          <li><strong>Ollama (local)</strong> — free, private, offline. Install Ollama, run <code>ollama pull qwen2.5-coder:7b</code> (great for code), then “Detect installed models”.</li>
          <li><strong>OpenAI / Anthropic / Groq / OpenRouter</strong> — paste an API key; faster and higher quality, but requests leave your machine.</li>
          <li>No model is fine for browsing structure, files, graphs and metrics — only the generated answers (Ask and per-file/function explanations) need an LLM.</li>
        </ul>
      </div>
    </div>
  );
}

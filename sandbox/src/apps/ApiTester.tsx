// ============================================================
// API Tester — HTTP request builder similar to Postman
// ============================================================

import { useState, useCallback } from 'react';
import {
  Send, Plus, Trash2, Save, Star, Clock,
  Copy, Globe,
} from 'lucide-react';

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH' | 'HEAD' | 'OPTIONS';

const METHOD_COLORS: Record<HttpMethod, string> = {
  GET: '#4CAF50',
  POST: '#7C4DFF',
  PUT: '#FF9800',
  PATCH: '#FF9800',
  DELETE: '#F44336',
  HEAD: '#2196F3',
  OPTIONS: '#9E9E9E',
};

interface Header {
  id: string;
  key: string;
  value: string;
  enabled: boolean;
}

interface Param {
  id: string;
  key: string;
  value: string;
  enabled: boolean;
}

interface SavedRequest {
  id: string;
  name: string;
  method: HttpMethod;
  url: string;
  headers: Header[];
  body: string;
}

interface RequestHistory {
  id: string;
  method: HttpMethod;
  url: string;
  status: number;
  time: number;
  timestamp: number;
}

const DEFAULT_ENDPOINTS = [
  { method: 'GET' as HttpMethod, url: 'https://jsonplaceholder.typicode.com/posts', desc: 'List posts' },
  { method: 'GET' as HttpMethod, url: 'https://jsonplaceholder.typicode.com/posts/1', desc: 'Single post' },
  { method: 'POST' as HttpMethod, url: 'https://jsonplaceholder.typicode.com/posts', desc: 'Create post' },
  { method: 'GET' as HttpMethod, url: 'https://jsonplaceholder.typicode.com/users', desc: 'List users' },
];

export default function ApiTester() {
  const [method, setMethod] = useState<HttpMethod>('GET');
  const [url, setUrl] = useState('');
  const [activeTab, setActiveTab] = useState<'params' | 'headers' | 'body'>('params');
  const [params, setParams] = useState<Param[]>([{ id: '1', key: '', value: '', enabled: true }]);
  const [headers, setHeaders] = useState<Header[]>([
    { id: '1', key: 'Content-Type', value: 'application/json', enabled: true },
    { id: '2', key: 'Accept', value: 'application/json', enabled: true },
  ]);
  const [body, setBody] = useState('');
  const [response, setResponse] = useState<{
    status: number;
    statusText: string;
    headers: Record<string, string>;
    body: string;
    time: number;
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [history, setHistory] = useState<RequestHistory[]>([]);
  const [savedRequests, setSavedRequests] = useState<SavedRequest[]>([]);
  const [showSaved, setShowSaved] = useState(false);
  const [responseTab, setResponseTab] = useState<'body' | 'headers'>('body');
  const [copied, setCopied] = useState(false);

  const addParam = useCallback(() => {
    setParams((prev) => [...prev, { id: Date.now().toString(), key: '', value: '', enabled: true }]);
  }, []);

  const updateParam = useCallback((id: string, field: 'key' | 'value', value: string) => {
    setParams((prev) => prev.map((p) => p.id === id ? { ...p, [field]: value } : p));
  }, []);

  const removeParam = useCallback((id: string) => {
    setParams((prev) => prev.filter((p) => p.id !== id));
  }, []);

  const addHeader = useCallback(() => {
    setHeaders((prev) => [...prev, { id: Date.now().toString(), key: '', value: '', enabled: true }]);
  }, []);

  const updateHeader = useCallback((id: string, field: 'key' | 'value', value: string) => {
    setHeaders((prev) => prev.map((h) => h.id === id ? { ...h, [field]: value } : h));
  }, []);

  const removeHeader = useCallback((id: string) => {
    setHeaders((prev) => prev.filter((h) => h.id !== id));
  }, []);

  const buildUrl = useCallback(() => {
    if (!url) return '';
    const enabledParams = params.filter((p) => p.enabled && p.key);
    if (enabledParams.length === 0) return url;
    const qs = enabledParams.map((p) => `${encodeURIComponent(p.key)}=${encodeURIComponent(p.value)}`).join('&');
    return url.includes('?') ? `${url}&${qs}` : `${url}?${qs}`;
  }, [url, params]);

  const sendRequest = useCallback(async () => {
    const finalUrl = buildUrl();
    if (!finalUrl) return;
    setLoading(true);
    setError('');
    setResponse(null);
    const startTime = performance.now();

    try {
      const enabledHeaders = headers.filter((h) => h.enabled && h.key);
      const headerObj: Record<string, string> = {};
      enabledHeaders.forEach((h) => { headerObj[h.key] = h.value; });

      const opts: RequestInit = {
        method,
        headers: headerObj,
      };

      if (['POST', 'PUT', 'PATCH'].includes(method) && body) {
        opts.body = body;
      }

      const res = await fetch(finalUrl, opts);
      const resBody = await res.text();
      const time = Math.round(performance.now() - startTime);

      const responseHeaders: Record<string, string> = {};
      res.headers.forEach((v, k) => { responseHeaders[k] = v; });

      setResponse({
        status: res.status,
        statusText: res.statusText,
        headers: responseHeaders,
        body: resBody,
        time,
      });

      setHistory((prev) => [{
        id: Date.now().toString(),
        method,
        url: finalUrl,
        status: res.status,
        time,
        timestamp: Date.now(),
      }, ...prev].slice(0, 20));
    } catch (e) {
      setError((e as Error).message || 'Network error (CORS may be blocking this request)');
    } finally {
      setLoading(false);
    }
  }, [buildUrl, method, headers, body]);

  const saveRequest = useCallback(() => {
    if (!url) return;
    const newReq: SavedRequest = {
      id: Date.now().toString(),
      name: `${method} ${url.slice(0, 40)}`,
      method,
      url,
      headers: [...headers],
      body,
    };
    setSavedRequests((prev) => [...prev, newReq]);
  }, [method, url, headers, body]);

  const loadSaved = useCallback((req: SavedRequest) => {
    setMethod(req.method);
    setUrl(req.url);
    setHeaders(req.headers.length > 0 ? [...req.headers] : [{ id: '1', key: '', value: '', enabled: true }]);
    setBody(req.body);
  }, []);

  const loadEndpoint = useCallback((ep: { method: HttpMethod; url: string }) => {
    setMethod(ep.method);
    setUrl(ep.url);
    if (ep.method === 'POST') {
      setBody(JSON.stringify({ title: 'foo', body: 'bar', userId: 1 }, null, 2));
    } else {
      setBody('');
    }
  }, []);

  const copyResponse = useCallback(async () => {
    if (!response) return;
    await navigator.clipboard.writeText(response.body);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }, [response]);

  const formattedBody = response?.body || '';
  let prettyBody = formattedBody;
  try {
    prettyBody = JSON.stringify(JSON.parse(formattedBody), null, 2);
  } catch { /* not JSON */ }

  const getStatusColor = (s: number) => {
    if (s >= 200 && s < 300) return '#4CAF50';
    if (s >= 300 && s < 400) return '#2196F3';
    if (s >= 400 && s < 500) return '#FF9800';
    return '#F44336';
  };

  return (
    <div className="h-full flex flex-col" style={{ background: 'var(--bg-window)' }}>
      {/* URL Bar */}
      <div className="flex items-center gap-2 px-3 py-2 shrink-0" style={{ background: 'var(--bg-titlebar)', borderBottom: '1px solid var(--border-subtle)' }}>
        <select
          value={method}
          onChange={(e) => setMethod(e.target.value as HttpMethod)}
          className="text-xs font-semibold px-2 py-1.5 rounded outline-none"
          style={{ background: 'var(--bg-input)', color: METHOD_COLORS[method], border: '1px solid var(--border-default)', width: 90 }}
        >
          {Object.keys(METHOD_COLORS).map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://api.example.com/users"
          className="flex-1 px-3 py-1.5 rounded text-xs outline-none"
          style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)', fontFamily: "'JetBrains Mono', monospace" }}
        />
        <button
          onClick={sendRequest}
          disabled={loading || !url}
          className="flex items-center gap-1 px-4 py-1.5 rounded text-xs font-medium disabled:opacity-50 transition-all"
          style={{ background: 'var(--accent-primary)', color: 'white' }}
        >
          <Send size={13} /> {loading ? 'Sending...' : 'Send'}
        </button>
        <button onClick={saveRequest} className="p-1.5 rounded hover:bg-[var(--bg-hover)]" title="Save request">
          <Star size={14} style={{ color: 'var(--text-secondary)' }} />
        </button>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Left: Request panel */}
        <div className="flex-1 flex flex-col overflow-hidden" style={{ borderRight: '1px solid var(--border-subtle)' }}>
          {/* Tabs */}
          <div className="flex items-center px-3 shrink-0" style={{ height: 32, background: 'var(--bg-titlebar)', borderBottom: '1px solid var(--border-subtle)' }}>
            {(['params', 'headers', 'body'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className="px-3 py-1 text-xs font-medium capitalize transition-colors"
                style={{
                  color: activeTab === tab ? 'var(--accent-primary)' : 'var(--text-secondary)',
                  borderBottom: activeTab === tab ? '2px solid var(--accent-primary)' : '2px solid transparent',
                }}
              >
                {tab}
              </button>
            ))}
            <div className="ml-auto flex items-center gap-1">
              <button onClick={() => setShowSaved((v) => !v)} className="flex items-center gap-1 text-xs px-2 py-0.5 rounded hover:bg-[var(--bg-hover)]">
                <Save size={10} /> Saved
              </button>
            </div>
          </div>

          {/* Tab content */}
          <div className="flex-1 overflow-auto p-3 custom-scrollbar">
            {activeTab === 'params' && (
              <div className="flex flex-col gap-1">
                {params.map((p) => (
                  <div key={p.id} className="flex items-center gap-2">
                    <input type="checkbox" checked={p.enabled} onChange={() => {}} className="accent-purple-500" />
                    <input
                      value={p.key}
                      onChange={(e) => updateParam(p.id, 'key', e.target.value)}
                      placeholder="Key"
                      className="flex-1 px-2 py-1 rounded text-xs outline-none"
                      style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }}
                    />
                    <input
                      value={p.value}
                      onChange={(e) => updateParam(p.id, 'value', e.target.value)}
                      placeholder="Value"
                      className="flex-1 px-2 py-1 rounded text-xs outline-none"
                      style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }}
                    />
                    <button onClick={() => removeParam(p.id)} className="p-1 rounded hover:bg-[var(--bg-hover)]"><Trash2 size={12} /></button>
                  </div>
                ))}
                <button onClick={addParam} className="flex items-center gap-1 text-xs px-2 py-1 rounded hover:bg-[var(--bg-hover)] mt-1">
                  <Plus size={12} /> Add Parameter
                </button>
              </div>
            )}

            {activeTab === 'headers' && (
              <div className="flex flex-col gap-1">
                {headers.map((h) => (
                  <div key={h.id} className="flex items-center gap-2">
                    <input type="checkbox" checked={h.enabled} onChange={() => {}} className="accent-purple-500" />
                    <input
                      value={h.key}
                      onChange={(e) => updateHeader(h.id, 'key', e.target.value)}
                      placeholder="Header"
                      className="flex-1 px-2 py-1 rounded text-xs outline-none"
                      style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }}
                    />
                    <input
                      value={h.value}
                      onChange={(e) => updateHeader(h.id, 'value', e.target.value)}
                      placeholder="Value"
                      className="flex-1 px-2 py-1 rounded text-xs outline-none"
                      style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }}
                    />
                    <button onClick={() => removeHeader(h.id)} className="p-1 rounded hover:bg-[var(--bg-hover)]"><Trash2 size={12} /></button>
                  </div>
                ))}
                <button onClick={addHeader} className="flex items-center gap-1 text-xs px-2 py-1 rounded hover:bg-[var(--bg-hover)] mt-1">
                  <Plus size={12} /> Add Header
                </button>
              </div>
            )}

            {activeTab === 'body' && (
              <textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder="Request body (JSON, text, etc.)"
                spellCheck={false}
                className="w-full h-full min-h-[200px] resize-none outline-none p-3 rounded text-xs custom-scrollbar"
                style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)', fontFamily: "'JetBrains Mono', monospace" }}
              />
            )}
          </div>

          {/* Demo endpoints */}
          <div className="shrink-0 px-3 py-2" style={{ background: 'var(--bg-titlebar)', borderTop: '1px solid var(--border-subtle)' }}>
            <span className="text-xs font-semibold block mb-1" style={{ color: 'var(--text-secondary)' }}>Demo Endpoints</span>
            <div className="flex flex-col gap-0.5">
              {DEFAULT_ENDPOINTS.map((ep, i) => (
                <button
                  key={i}
                  onClick={() => loadEndpoint(ep)}
                  className="flex items-center gap-2 text-xs px-2 py-1 rounded hover:bg-[var(--bg-hover)] text-left"
                >
                  <span className="font-semibold" style={{ color: METHOD_COLORS[ep.method] }}>{ep.method}</span>
                  <span className="truncate" style={{ color: 'var(--text-secondary)' }}>{ep.url}</span>
                  <span className="ml-auto text-[10px]" style={{ color: 'var(--text-disabled)' }}>{ep.desc}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Right: Response + Saved */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {showSaved ? (
            <div className="flex-1 overflow-auto p-3 custom-scrollbar">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>SAVED REQUESTS</span>
                <button onClick={() => setShowSaved(false)} className="text-xs px-2 py-0.5 rounded hover:bg-[var(--bg-hover)]">Close</button>
              </div>
              {savedRequests.map((req) => (
                <div
                  key={req.id}
                  className="flex items-center gap-2 p-2 rounded mb-1 cursor-pointer hover:bg-[var(--bg-hover)]"
                  onClick={() => { loadSaved(req); setShowSaved(false); }}
                >
                  <span className="text-xs font-semibold" style={{ color: METHOD_COLORS[req.method] }}>{req.method}</span>
                  <span className="text-xs truncate" style={{ color: 'var(--text-primary)' }}>{req.name}</span>
                </div>
              ))}
              {savedRequests.length === 0 && (
                <p className="text-xs" style={{ color: 'var(--text-disabled)' }}>No saved requests yet</p>
              )}
            </div>
          ) : (
            <>
              {/* Response status bar */}
              {response && (
                <div className="flex items-center gap-3 px-3 py-1.5 shrink-0" style={{ background: 'var(--bg-titlebar)', borderBottom: '1px solid var(--border-subtle)' }}>
                  <span className="text-xs font-semibold" style={{ color: getStatusColor(response.status) }}>
                    {response.status} {response.statusText}
                  </span>
                  <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{response.time}ms</span>
                  <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{prettyBody.length} chars</span>
                  <button onClick={copyResponse} className="ml-auto flex items-center gap-1 text-xs px-2 py-0.5 rounded hover:bg-[var(--bg-hover)]">
                    <Copy size={10} /> {copied ? 'Copied!' : 'Copy'}
                  </button>
                </div>
              )}

              {/* Error */}
              {error && (
                <div className="flex items-center gap-2 px-3 py-2 shrink-0" style={{ background: 'rgba(244,67,54,0.1)', borderBottom: '1px solid var(--border-subtle)' }}>
                  <span className="text-xs text-red-400">{error}</span>
                </div>
              )}

              {/* Response tabs */}
              {response && (
                <div className="flex items-center px-3 shrink-0" style={{ height: 28, background: 'var(--bg-titlebar)', borderBottom: '1px solid var(--border-subtle)' }}>
                  {(['body', 'headers'] as const).map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setResponseTab(tab)}
                      className="px-3 py-0.5 text-xs capitalize transition-colors"
                      style={{
                        color: responseTab === tab ? 'var(--accent-primary)' : 'var(--text-secondary)',
                        borderBottom: responseTab === tab ? '2px solid var(--accent-primary)' : '2px solid transparent',
                      }}
                    >
                      {tab}
                    </button>
                  ))}
                </div>
              )}

              {/* Response content */}
              <div className="flex-1 overflow-auto p-3 custom-scrollbar">
                {response ? (
                  responseTab === 'body' ? (
                    <pre className="text-xs whitespace-pre-wrap break-all" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-primary)' }}>{prettyBody}</pre>
                  ) : (
                    <div className="flex flex-col gap-1">
                      {Object.entries(response.headers).map(([k, v]) => (
                        <div key={k} className="flex gap-2 text-xs">
                          <span className="font-medium shrink-0" style={{ color: 'var(--accent-primary)' }}>{k}:</span>
                          <span style={{ color: 'var(--text-primary)' }}>{v}</span>
                        </div>
                      ))}
                    </div>
                  )
                ) : (
                  <div className="flex flex-col items-center justify-center h-full gap-3">
                    <Globe size={36} className="text-[var(--text-disabled)]" />
                    <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Send a request to see the response</p>
                  </div>
                )}
              </div>

              {/* History */}
              <div className="shrink-0 overflow-y-auto custom-scrollbar" style={{ maxHeight: 120, borderTop: '1px solid var(--border-subtle)', background: 'var(--bg-titlebar)' }}>
                <div className="flex items-center gap-1 px-2 py-0.5">
                  <Clock size={10} style={{ color: 'var(--text-secondary)' }} />
                  <span className="text-[10px] font-semibold" style={{ color: 'var(--text-secondary)' }}>HISTORY</span>
                </div>
                {history.map((h) => (
                  <div
                    key={h.id}
                    className="flex items-center gap-2 px-2 py-0.5 cursor-pointer hover:bg-[var(--bg-hover)]"
                    onClick={() => { setMethod(h.method); setUrl(h.url); }}
                  >
                    <span className="text-[10px] font-semibold" style={{ color: METHOD_COLORS[h.method] }}>{h.method}</span>
                    <span className="text-[10px] truncate flex-1" style={{ color: 'var(--text-secondary)' }}>{h.url}</span>
                    <span className="text-[10px]" style={{ color: getStatusColor(h.status) }}>{h.status}</span>
                    <span className="text-[10px]" style={{ color: 'var(--text-disabled)' }}>{h.time}ms</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

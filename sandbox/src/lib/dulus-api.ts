// ============================================================
// Dulus API Bridge — Centralized backend communication
// Extracted from Terminal.tsx + extended for Memory/Tasks/Skills/Agents
// ============================================================

const API_BASE = '';

const ENDPOINTS = {
  health: `${API_BASE}/api/health`,
  chat: `${API_BASE}/chat`,
  exec: `${API_BASE}/api/sandbox/exec`,
  fsList: `${API_BASE}/api/sandbox/fs/list`,
  fsRead: `${API_BASE}/api/sandbox/fs/read`,
  fsWrite: `${API_BASE}/api/sandbox/fs/write`,
  toolInvoke: `${API_BASE}/api/tools/invoke`,
  tasks: `${API_BASE}/api/tasks`,
  agents: `${API_BASE}/api/agents`,
  mempalace: `${API_BASE}/api/mempalace`,
  events: `${API_BASE}/api/events`,
} as const;

// ---- Helpers -----------------------------------------------
export async function fetchWithTimeout(url: string, init?: RequestInit, timeoutMs = 5000): Promise<Response> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(url, { ...init, signal: ctrl.signal });
    clearTimeout(timer);
    return r;
  } catch (err) {
    clearTimeout(timer);
    throw err;
  }
}

// ---- Errors ------------------------------------------------
export class DulusAPIError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = 'DulusAPIError';
  }
}

// ---- Health ------------------------------------------------
export interface HealthStatus {
  ok: boolean;
  latency: number;
  timestamp: number;
}

export async function checkHealth(timeoutMs = 2000): Promise<HealthStatus> {
  const start = performance.now();
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    const r = await fetch(ENDPOINTS.health, { signal: ctrl.signal });
    clearTimeout(timer);
    return { ok: r.ok, latency: Math.round(performance.now() - start), timestamp: Date.now() };
  } catch {
    return { ok: false, latency: Math.round(performance.now() - start), timestamp: Date.now() };
  }
}

// ---- Chat Streaming ----------------------------------------
export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export async function* streamChat(messages: ChatMessage[]): AsyncGenerator<string> {
  const resp = await fetch(ENDPOINTS.chat, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages }),
  });
  if (!resp.ok || !resp.body) {
    yield `[error] HTTP ${resp.status}`;
    return;
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split('\n');
    buf = lines.pop()!;
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      try {
        const obj = JSON.parse(line.slice(6));
        if (obj.type === 'text' && obj.text) yield obj.text;
        if (obj.type === 'error' && obj.message) yield `[error] ${obj.message}`;
      } catch { /* skip malformed */ }
    }
  }
}

// ---- Exec --------------------------------------------------
export interface ExecResult {
  stdout: string;
  stderr: string;
  exitCode: number;
}

export async function execCommand(command: string, cwd?: string, timeoutMs = 30000): Promise<ExecResult> {
  const r = await fetchWithTimeout(ENDPOINTS.exec, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ command, cwd }),
  }, timeoutMs);
  if (!r.ok) throw new DulusAPIError(r.status, `Exec failed: ${r.statusText}`);
  return r.json();
}

// ---- File System -------------------------------------------
export interface FSListResult {
  path: string;
  entries: { name: string; type: 'file' | 'dir'; size?: number; modified?: string }[];
}

export async function fsList(path: string): Promise<FSListResult> {
  const r = await fetch(`${ENDPOINTS.fsList}?path=${encodeURIComponent(path)}`);
  if (!r.ok) throw new DulusAPIError(r.status, `FS list failed: ${r.statusText}`);
  return r.json();
}

export async function fsRead(path: string): Promise<{ content: string }> {
  const r = await fetch(`${ENDPOINTS.fsRead}?path=${encodeURIComponent(path)}`);
  if (!r.ok) throw new DulusAPIError(r.status, `FS read failed: ${r.statusText}`);
  return r.json();
}

export async function fsWrite(path: string, content: string): Promise<void> {
  const r = await fetch(ENDPOINTS.fsWrite, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, content }),
  });
  if (!r.ok) throw new DulusAPIError(r.status, `FS write failed: ${r.statusText}`);
}

// ---- Generic Tool Invocation -------------------------------
export interface ToolResult<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
}

export async function invokeTool<T = unknown>(toolName: string, args: Record<string, unknown>): Promise<ToolResult<T>> {
  try {
    const r = await fetchWithTimeout(ENDPOINTS.toolInvoke, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tool: toolName, arguments: args }),
    }, 8000);
    if (!r.ok) throw new DulusAPIError(r.status, `Tool invoke failed: ${r.statusText}`);
    const data = await r.json();
    return { success: true, data: data as T };
  } catch (err) {
    return { success: false, error: err instanceof Error ? err.message : String(err) };
  }
}

// ---- Memory System (REST) ----------------------------------
export interface MemoryEntry {
  id?: string;
  name: string;
  description: string;
  content: string;
  type: string;
  scope?: string;
  hall?: string;
  wing?: string;
  created_at?: string;
  confidence?: number;
  source?: string;
  metadata?: Record<string, unknown>;
}

export interface WingInfo {
  name: string;
  count: number;
  last_updated?: string;
}

export interface MemPalaceData {
  entries: MemoryEntry[];
  wings: WingInfo[];
  compact_text?: string;
  stats?: { total: number; wings: number; last_consolidated?: string };
}

export async function fetchMemPalace(): Promise<ToolResult<MemPalaceData>> {
  try {
    const r = await fetchWithTimeout(ENDPOINTS.mempalace, {}, 4000);
    if (!r.ok) throw new DulusAPIError(r.status, `MemPalace fetch failed: ${r.statusText}`);
    const data = await r.json();
    return { success: true, data };
  } catch (err) {
    return { success: false, error: err instanceof Error ? err.message : String(err) };
  }
}

export async function searchMemory(query: string, limit = 10, wing?: string): Promise<ToolResult<MemoryEntry[]>> {
  // Prefer REST if available, fallback to tool invoke
  try {
    const url = new URL(`${API_BASE}/api/memory/search`, window.location.origin);
    url.searchParams.set('query', query);
    url.searchParams.set('limit', String(limit));
    if (wing) url.searchParams.set('wing', wing);
    const r = await fetch(url.pathname + url.search);
    if (r.ok) return { success: true, data: await r.json() };
  } catch { /* fallback */ }
  return invokeTool<MemoryEntry[]>('search_memory', { query, limit, wing });
}

export async function listWings(): Promise<ToolResult<WingInfo[]>> {
  try {
    const r = await fetch(`${API_BASE}/api/memory/wings`);
    if (r.ok) return { success: true, data: await r.json() };
  } catch { /* fallback */ }
  return invokeTool<WingInfo[]>('list_wings', {});
}

// ---- Tasks System (REST + SSE) -----------------------------
export interface DulusTask {
  id: string;
  subject: string;
  description: string;
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled' | 'deleted';
  owner?: string;
  active_form?: string;
  createdAt?: string;
  created_at?: string;
  updated_at?: string;
  metadata?: Record<string, unknown>;
}

export async function listTasks(): Promise<ToolResult<DulusTask[]>> {
  try {
    const r = await fetchWithTimeout(ENDPOINTS.tasks, {}, 4000);
    if (!r.ok) throw new DulusAPIError(r.status, `Tasks list failed: ${r.statusText}`);
    const data = await r.json();
    const list = Array.isArray(data) ? data : data.tasks || [];
    return { success: true, data: list };
  } catch (err) {
    return { success: false, error: err instanceof Error ? err.message : String(err) };
  }
}

export async function getTask(taskId: string): Promise<ToolResult<DulusTask>> {
  try {
    const r = await fetch(`${ENDPOINTS.tasks}/${encodeURIComponent(taskId)}`);
    if (!r.ok) throw new DulusAPIError(r.status, `Task get failed: ${r.statusText}`);
    return { success: true, data: await r.json() };
  } catch (err) {
    return { success: false, error: err instanceof Error ? err.message : String(err) };
  }
}

export async function createTask(task: Omit<DulusTask, 'id'>): Promise<ToolResult<DulusTask>> {
  try {
    const r = await fetch(ENDPOINTS.tasks, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(task),
    });
    if (!r.ok) throw new DulusAPIError(r.status, `Task create failed: ${r.statusText}`);
    return { success: true, data: await r.json() };
  } catch (err) {
    return { success: false, error: err instanceof Error ? err.message : String(err) };
  }
}

export async function updateTask(taskId: string, updates: Partial<DulusTask>): Promise<ToolResult<DulusTask>> {
  try {
    const r = await fetch(`${ENDPOINTS.tasks}/${encodeURIComponent(taskId)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    });
    if (!r.ok) throw new DulusAPIError(r.status, `Task update failed: ${r.statusText}`);
    return { success: true, data: await r.json() };
  } catch (err) {
    return { success: false, error: err instanceof Error ? err.message : String(err) };
  }
}

export function createTasksEventSource(): EventSource {
  return new EventSource(ENDPOINTS.events);
}

// ---- Skills System (REST + Fallback) -----------------------
export interface SkillInfo {
  id?: string;
  name: string;
  description: string;
  category?: string;
  favorite?: boolean;
  lastUsed?: string;
  hotkey?: string;
}

export async function listSkills(): Promise<ToolResult<SkillInfo[]>> {
  try {
    const r = await fetchWithTimeout(`${API_BASE}/api/skills`, {}, 4000);
    if (r.ok) return { success: true, data: await r.json() };
  } catch { /* fallback to tool invoke */ }
  return invokeTool<SkillInfo[]>('SkillList', {});
}

export async function invokeSkill(skillName: string, args?: Record<string, unknown>): Promise<ToolResult<unknown>> {
  try {
    const r = await fetchWithTimeout(`${API_BASE}/api/skills/invoke`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: skillName, arguments: args || {} }),
    }, 15000);
    if (!r.ok) throw new DulusAPIError(r.status, `Skill invoke failed: ${r.statusText}`);
    return { success: true, data: await r.json() };
  } catch (err) {
    return { success: false, error: err instanceof Error ? err.message : String(err) };
  }
}

// ---- Agents System (REST + Fallback) -----------------------
export interface AgentInfo {
  id: string;
  name: string;
  status: 'idle' | 'running' | 'paused' | 'completed' | 'error';
  type?: string;
  model?: string;
  start_time?: string;
  last_activity?: string;
  progress?: number;
  task_count?: number;
  logs?: string[];
  metadata?: Record<string, unknown>;
}

export interface AgentTaskInfo {
  task_id: string;
  name: string;
  subagent_type?: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
}

export async function listAgents(): Promise<ToolResult<AgentInfo[]>> {
  try {
    const r = await fetchWithTimeout(ENDPOINTS.agents, {}, 3000);
    if (!r.ok) throw new DulusAPIError(r.status, `Agents list failed: ${r.statusText}`);
    const data = await r.json();
    const list = Array.isArray(data) ? data : data.agents || [];
    return { success: true, data: list };
  } catch (err) {
    return { success: false, error: err instanceof Error ? err.message : String(err) };
  }
}

export async function listAgentTasks(): Promise<ToolResult<AgentTaskInfo[]>> {
  // Fallback to tool invoke; REST endpoint may not expose raw agent tasks
  return invokeTool<AgentTaskInfo[]>('ListAgentTasks', {});
}

export async function checkAgentResult(taskId: string): Promise<ToolResult<unknown>> {
  return invokeTool<unknown>('CheckAgentResult', { task_id: taskId });
}

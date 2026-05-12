// ============================================================
// Terminal — Dulus Agent + Virtual FS Integration
// ============================================================

import { useState, useRef, useEffect, useCallback } from 'react';
import { useFileSystem } from '@/hooks/useFileSystem';

interface TerminalLine {
  type: 'input' | 'output' | 'error' | 'system' | 'dulus';
  text: string;
}

// Dulus agent API endpoint (same origin)
const DULUS_CHAT_URL = '/chat';
const DULUS_EXEC_URL = '/api/sandbox/exec';
const DULUS_FS_LIST_URL = '/api/sandbox/fs/list';
const DULUS_FS_READ_URL = '/api/sandbox/fs/read';
const DULUS_FS_WRITE_URL = '/api/sandbox/fs/write';

// Check if we can reach the backend
async function isDulusAvailable(): Promise<boolean> {
  try {
    const r = await fetch('/api/health', { method: 'GET', signal: AbortSignal.timeout(1500) });
    return r.ok;
  } catch {
    return false;
  }
}

// Stream the Dulus agent response
async function* streamDulus(url: string, body: object): AsyncGenerator<string> {
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
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
      } catch { /* skip */ }
    }
  }
}

// ---- Built-in commands (offline virtual FS) ----
const COMMANDS: Record<string, (args: string[], ctx: TerminalContext) => string | string[]> = {
  help: () => [
    'Available commands:',
    '  ls [path]         - List directory contents (real or virtual)',
    '  cd [path]         - Change directory',
    '  pwd               - Print working directory',
    '  mkdir <name>      - Create directory',
    '  rm <name>         - Remove file or directory',
    '  cat <file>        - Display file contents',
    '  echo <text>       - Print text',
    '  clear             - Clear terminal',
    '  whoami            - Print current user',
    '  date              - Print current date and time',
    '  uname             - Print system info',
    '  neofetch          - Display system information',
    '  calc <expr>       - Calculate expression',
    '  touch <file>      - Create empty file',
    '  history           - Show command history',
    '  dulus <msg>       - Send a message to the Dulus AI agent',
    '  exec <cmd>        - Run a command through Dulus agent',
    '  help              - Show this help message',
  ],

  ls: (args, ctx) => {
    const targetPath = args[0] || ctx.currentPath;
    const node = ctx.findNodeByPath(targetPath);
    if (!node) return `ls: cannot access '${targetPath}': No such file or directory`;
    if (node.type === 'file') return node.name;
    const children = ctx.getChildren(node.id);
    if (children.length === 0) return '';
    return children.map((c) => {
      const prefix = c.type === 'folder' ? '\x1b[34m' : '\x1b[0m';
      const suffix = '\x1b[0m';
      return `${prefix}${c.name}${suffix}`;
    });
  },

  cd: (args, ctx) => {
    if (!args[0] || args[0] === '~') {
      ctx.setCurrentPath('/home/user');
      return '';
    }
    let target = args[0];
    if (target.startsWith('/')) {
      const node = ctx.findNodeByPath(target);
      if (!node) return `cd: no such file or directory: ${target}`;
      if (node.type !== 'folder') return `cd: not a directory: ${target}`;
      ctx.setCurrentPath(target);
      return '';
    }
    const currentParts = ctx.currentPath.split('/').filter(Boolean);
    const parts = target.split('/').filter(Boolean);
    for (const part of parts) {
      if (part === '..') {
        currentParts.pop();
      } else if (part !== '.') {
        currentParts.push(part);
      }
    }
    const newPath = '/' + currentParts.join('/');
    const node = ctx.findNodeByPath(newPath);
    if (!node) return `cd: no such file or directory: ${target}`;
    if (node.type !== 'folder') return `cd: not a directory: ${target}`;
    ctx.setCurrentPath(newPath);
    return '';
  },

  pwd: (_args, ctx) => ctx.currentPath,

  mkdir: (args, ctx) => {
    if (!args[0]) return 'mkdir: missing operand';
    const currentNode = ctx.findNodeByPath(ctx.currentPath);
    if (!currentNode) return 'mkdir: cannot create directory';
    ctx.createFolder(currentNode.id, args[0]);
    return '';
  },

  touch: (args, ctx) => {
    if (!args[0]) return 'touch: missing file operand';
    const currentNode = ctx.findNodeByPath(ctx.currentPath);
    if (!currentNode) return 'touch: cannot create file';
    ctx.createFile(currentNode.id, args[0]);
    return '';
  },

  rm: (args, ctx) => {
    if (!args[0]) return 'rm: missing operand';
    const currentNode = ctx.findNodeByPath(ctx.currentPath);
    if (!currentNode) return 'rm: cannot remove';
    const children = ctx.getChildren(currentNode.id);
    const target = children.find((c) => c.name === args[0]);
    if (!target) return `rm: cannot remove '${args[0]}': No such file or directory`;
    ctx.deleteNode(target.id);
    return '';
  },

  cat: (args, ctx) => {
    if (!args[0]) return 'cat: missing file operand';
    const currentNode = ctx.findNodeByPath(ctx.currentPath);
    if (!currentNode) return 'cat: cannot read file';
    const children = ctx.getChildren(currentNode.id);
    const target = children.find((c) => c.name === args[0]);
    if (!target) return `cat: '${args[0]}': No such file or directory`;
    if (target.type === 'folder') return `cat: '${args[0]}': Is a directory`;
    const content = ctx.readFile(target.id);
    return content || '';
  },

  echo: (args) => args.join(' '),

  clear: (_args, ctx) => {
    ctx.clear();
    return '';
  },

  whoami: () => 'user',

  date: () => new Date().toString(),

  uname: () => 'Dulus OS Web 1.0.0-generic x86_64',

  neofetch: () => [
    '\x1b[35m     ____  _   _ _    _   _ ____  \\x1b[0m',
    '\x1b[35m    |  _ \\| | | | |  | | | / ___| \\x1b[0m',
    '\x1b[35m    | | | | | | | |  | | | \\___ \\ \\x1b[0m',
    '\x1b[35m    | |_| | |_| | |__| |_| |___) |\\x1b[0m',
    '\x1b[35m    |____/ \\___/|_____\\___/|____/ \\x1b[0m',
    '',
    '\x1b[36mOS:\x1b[0m Dulus OS Web 1.0.0',
    '\x1b[36mKernel:\x1b[0m browser-engine-20.0 + Dulus Agent',
    '\x1b[36mShell:\x1b[0m dulus-shell 2.0',
    '\x1b[36mDE:\x1b[0m Dulus Desktop Environment',
    '\x1b[36mTheme:\x1b[0m Adwaita-dark + Dulus Accent',
    '\x1b[36mIcons:\x1b[0m Dulus-mono-dark',
    '\x1b[36mTerminal:\x1b[0m dulus-terminal 2.0',
    '\x1b[36mCPU:\x1b[0m Virtual Web Core',
    '\x1b[36mMemory:\x1b[0m Browser Allocated',
    '\x1b[32mDulus Agent:\x1b[0m Connected ✓',
  ],

  calc: (args) => {
    if (!args.length) return 'calc: missing expression';
    const expr = args.join('');
    try {
      const sanitized = expr.replace(/[^0-9+\-*/().\\s]/g, '');
      if (sanitized !== expr) return 'calc: invalid characters in expression';
      // eslint-disable-next-line no-new-func
      const result = new Function('return ' + sanitized)();
      return String(result);
    } catch {
      return 'calc: invalid expression';
    }
  },

  history: (_args, ctx) => {
    return ctx.history.map((cmd, i) => `${i + 1}  ${cmd}`);
  },
};

interface TerminalContext {
  currentPath: string;
  setCurrentPath: (path: string) => void;
  findNodeByPath: ReturnType<typeof useFileSystem>['findNodeByPath'];
  getChildren: ReturnType<typeof useFileSystem>['getChildren'];
  createFolder: ReturnType<typeof useFileSystem>['createFolder'];
  createFile: ReturnType<typeof useFileSystem>['createFile'];
  deleteNode: ReturnType<typeof useFileSystem>['deleteNode'];
  readFile: ReturnType<typeof useFileSystem>['readFile'];
  clear: () => void;
  history: string[];
}

export default function Terminal() {
  const fsHook = useFileSystem();
  const [lines, setLines] = useState<TerminalLine[]>([
    { type: 'system', text: 'Dulus OS Terminal v2.0' },
    { type: 'system', text: 'Type "help" for available commands, "dulus <msg>" to talk to your AI agent.' },
    { type: 'output', text: '' },
  ]);
  const [input, setInput] = useState('');
  const [currentPath, setCurrentPath] = useState('/home/user');
  const [history, setHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [savedInput, setSavedInput] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [dulusAvailable, setDulusAvailable] = useState<boolean | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Check if Dulus backend is reachable on mount
  useEffect(() => {
    isDulusAvailable().then((ok) => {
      setDulusAvailable(ok);
      if (ok) {
        setLines((prev) => [
          ...prev,
          { type: 'system', text: '\x1b[32m✓ Dulus Agent connected — full system access enabled.\x1b[0m' },
          { type: 'output', text: '' },
        ]);
      } else {
        setLines((prev) => [
          ...prev,
          { type: 'system', text: '\x1b[33m⚠ Dulus Agent offline — running in virtual FS mode.\x1b[0m' },
          { type: 'output', text: '' },
        ]);
      }
    });
  }, []);

  // Check for context-menu "Open in Terminal" cwd
  useEffect(() => {
    const savedCwd = sessionStorage.getItem('dulus_terminal_cwd');
    if (savedCwd) {
      setCurrentPath(savedCwd);
      sessionStorage.removeItem('dulus_terminal_cwd');
    }
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [lines]);

  const addLine = useCallback((line: TerminalLine) => {
    setLines((prev) => [...prev, line]);
  }, []);

  const appendToLast = useCallback((text: string, type: TerminalLine['type']) => {
    setLines((prev) => {
      const last = prev[prev.length - 1];
      if (last && last.type === type) {
        return [...prev.slice(0, -1), { ...last, text: last.text + text }];
      }
      return [...prev, { type, text }];
    });
  }, []);

  const clear = useCallback(() => {
    setLines([]);
  }, []);

  // Handle "dulus <message>" command — talk to the agent
  const runDulusChat = useCallback(async (message: string) => {
    setIsThinking(true);
    addLine({ type: 'system', text: '◆ Dulus is thinking...' });
    try {
      let hasOutput = false;
      for await (const chunk of streamDulus(DULUS_CHAT_URL, { message })) {
        if (!hasOutput) {
          // Replace "thinking" line with first real output
          setLines((prev) => {
            const idx = [...prev].reverse().findIndex((l) => l.text === '◆ Dulus is thinking...');
            if (idx >= 0) {
              const real = prev.length - 1 - idx;
              const next = [...prev];
              next[real] = { type: 'dulus', text: chunk };
              return next;
            }
            return [...prev, { type: 'dulus', text: chunk }];
          });
          hasOutput = true;
        } else {
          appendToLast(chunk, 'dulus');
        }
      }
      if (!hasOutput) {
        setLines((prev) => prev.filter((l) => l.text !== '◆ Dulus is thinking...'));
      }
    } catch (e) {
      addLine({ type: 'error', text: `[dulus] ${e}` });
    } finally {
      setIsThinking(false);
    }
  }, [addLine, appendToLast]);

  // Handle "exec <cmd>" command — run via Dulus agent
  const runExecCommand = useCallback(async (cmd: string) => {
    setIsThinking(true);
    addLine({ type: 'system', text: `$ ${cmd}` });
    try {
      let hasOutput = false;
      for await (const chunk of streamDulus(DULUS_EXEC_URL, { command: cmd })) {
        if (!hasOutput) {
          addLine({ type: 'output', text: chunk });
          hasOutput = true;
        } else {
          appendToLast(chunk, 'output');
        }
      }
    } catch (e) {
      addLine({ type: 'error', text: `[exec] ${e}` });
    } finally {
      setIsThinking(false);
    }
  }, [addLine, appendToLast]);

  // List real files via backend API
  const runRealLs = useCallback(async (path: string) => {
    try {
      const r = await fetch(`${DULUS_FS_LIST_URL}?path=${encodeURIComponent(path)}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const entries: Array<{ name: string; type: string }> = await r.json();
      const output = entries.map((e) =>
        e.type === 'folder' ? `\x1b[34m${e.name}/\x1b[0m` : e.name
      );
      output.forEach((line) => addLine({ type: 'output', text: line }));
    } catch (e) {
      addLine({ type: 'error', text: `ls: ${e}` });
    }
  }, [addLine]);

  // Read real file via backend API
  const runRealCat = useCallback(async (path: string) => {
    try {
      const r = await fetch(`${DULUS_FS_READ_URL}?path=${encodeURIComponent(path)}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      addLine({ type: 'output', text: data.content });
    } catch (e) {
      addLine({ type: 'error', text: `cat: ${e}` });
    }
  }, [addLine]);

  const executeCommand = useCallback(
    async (cmdLine: string) => {
      const trimmed = cmdLine.trim();
      if (!trimmed) {
        setLines((prev) => [...prev, { type: 'input', text: '' }, { type: 'output', text: '' }]);
        return;
      }

      const parts = trimmed.split(/\s+/);
      const cmd = parts[0].toLowerCase();
      const args = parts.slice(1);

      setLines((prev) => [...prev, { type: 'input', text: `${currentPath}$ ${trimmed}` }]);
      setHistory((prev) => [...prev, trimmed]);
      setHistoryIndex(-1);

      // ── Special commands: dulus and exec need async handling ──
      if (cmd === 'dulus' || cmd === 'ai') {
        const msg = args.join(' ');
        if (!msg) {
          addLine({ type: 'error', text: 'dulus: message required. Usage: dulus <your message>' });
          return;
        }
        if (!dulusAvailable) {
          addLine({ type: 'error', text: 'dulus: Dulus agent not reachable. Make sure the server is running.' });
          return;
        }
        await runDulusChat(msg);
        return;
      }

      if (cmd === 'exec') {
        const execCmd = args.join(' ');
        if (!execCmd) {
          addLine({ type: 'error', text: 'exec: command required. Usage: exec <shell command>' });
          return;
        }
        if (!dulusAvailable) {
          addLine({ type: 'error', text: 'exec: Dulus agent not reachable. Make sure the server is running.' });
          return;
        }
        await runExecCommand(execCmd);
        return;
      }

      // ── Real filesystem commands when Dulus is available ──
      if (dulusAvailable && (cmd === 'ls' || cmd === 'dir')) {
        const targetArg = args[0] || '';
        // Translate virtual path to real relative path
        // Map /home/user -> '' (project root equivalent)
        const realPath = targetArg || '.';
        await runRealLs(realPath);
        return;
      }

      // ── Built-in virtual FS commands ──
      const ctx: TerminalContext = {
        currentPath,
        setCurrentPath,
        findNodeByPath: fsHook.findNodeByPath,
        getChildren: fsHook.getChildren,
        createFolder: fsHook.createFolder,
        createFile: fsHook.createFile,
        deleteNode: fsHook.deleteNode,
        readFile: fsHook.readFile,
        clear,
        history,
      };

      const handler = COMMANDS[cmd];
      if (handler) {
        try {
          const result = handler(args, ctx);
          if (result !== '') {
            if (Array.isArray(result)) {
              result.forEach((line) => {
                setLines((prev) => [...prev, { type: 'output', text: line }]);
              });
            } else {
              setLines((prev) => [...prev, { type: 'output', text: result }]);
            }
          }
        } catch (err) {
          setLines((prev) => [...prev, { type: 'error', text: `Error: ${err}` }]);
        }
      } else {
        setLines((prev) => [
          ...prev,
          { type: 'error', text: `${cmd}: command not found. Try "exec ${trimmed}" to run via Dulus agent.` },
        ]);
      }
    },
    [currentPath, fsHook, clear, history, dulusAvailable, runDulusChat, runExecCommand, runRealLs, addLine]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') {
        if (isThinking) return; // block input while agent is working
        executeCommand(input);
        setInput('');
        setHistoryIndex(-1);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (historyIndex === -1) {
          setSavedInput(input);
        }
        const newIndex = historyIndex + 1;
        if (newIndex < history.length) {
          setHistoryIndex(newIndex);
          setInput(history[history.length - 1 - newIndex]);
        }
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (historyIndex <= 0) {
          setHistoryIndex(-1);
          setInput(savedInput);
        } else {
          const newIndex = historyIndex - 1;
          setHistoryIndex(newIndex);
          setInput(history[history.length - 1 - newIndex]);
        }
      }
    },
    [input, executeCommand, history, historyIndex, savedInput, isThinking]
  );

  const handleTerminalClick = useCallback(() => {
    inputRef.current?.focus();
  }, []);

  // Parse ANSI color codes for display
  const parseAnsi = (text: string): React.ReactNode[] => {
    if (!text.includes('\x1b[')) return [text];
    const parts: React.ReactNode[] = [];
    const regex = /\x1b\[(\d+)m/g;
    let lastIndex = 0;
    let currentColor = '';
    let match;
    let key = 0;

    while ((match = regex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        parts.push(
          <span key={key++} style={{ color: currentColor }}>
            {text.slice(lastIndex, match.index)}
          </span>
        );
      }
      const code = parseInt(match[1], 10);
      switch (code) {
        case 30: currentColor = '#000'; break;
        case 31: currentColor = '#F44336'; break;
        case 32: currentColor = '#4CAF50'; break;
        case 33: currentColor = '#FF9800'; break;
        case 34: currentColor = '#2196F3'; break;
        case 35: currentColor = '#7C4DFF'; break;
        case 36: currentColor = '#00BCD4'; break;
        case 37: currentColor = '#E0E0E0'; break;
        case 0: currentColor = ''; break;
        default: currentColor = '';
      }
      lastIndex = regex.lastIndex;
    }
    if (lastIndex < text.length) {
      parts.push(
        <span key={key++} style={{ color: currentColor }}>
          {text.slice(lastIndex)}
        </span>
      );
    }
    return parts;
  };

  return (
    <div
      className="flex flex-col h-full font-mono text-xs select-text cursor-text"
      style={{
        background: '#0C0C0C',
        color: '#E0E0E0',
        fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace",
      }}
      onClick={handleTerminalClick}
    >
      {/* Terminal output */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 custom-scrollbar">
        {lines.map((line, i) => (
          <div key={i} className="whitespace-pre-wrap break-all leading-5">
            {line.type === 'input' && (
              <span>
                <span className="text-[#4CAF50]">{currentPath}</span>
                <span className="text-[#E0E0E0]">$ </span>
                <span className="text-[#E0E0E0]">{line.text.slice(line.text.indexOf('$') + 2)}</span>
              </span>
            )}
            {line.type === 'output' && <span className="text-[#E0E0E0]">{parseAnsi(line.text)}</span>}
            {line.type === 'error' && <span className="text-[#F44336]">{line.text}</span>}
            {line.type === 'system' && <span className="text-[#9E9E9E]">{parseAnsi(line.text)}</span>}
            {line.type === 'dulus' && (
              <span className="text-[#BB86FC]">
                <span className="text-[#7C4DFF] font-bold">◆ Dulus: </span>
                {line.text}
              </span>
            )}
          </div>
        ))}

        {/* Input line */}
        <div className="flex items-center gap-1 mt-1">
          {isThinking ? (
            <span className="text-[#7C4DFF] animate-pulse shrink-0">◆ thinking...</span>
          ) : (
            <>
              <span className="text-[#4CAF50] shrink-0">{currentPath}$</span>
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                className="flex-1 bg-transparent outline-none text-[#E0E0E0] min-w-0"
                autoFocus
                spellCheck={false}
                autoComplete="off"
                autoCapitalize="off"
                disabled={isThinking}
              />
            </>
          )}
        </div>
      </div>
    </div>
  );
}

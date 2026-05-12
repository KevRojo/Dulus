// ============================================================
// Git Client — Simulated git repository visualization
// ============================================================

import { useState, useCallback, useMemo } from 'react';
import {
  GitBranch, GitCommit, GitMerge, Plus,
  ChevronRight, ChevronDown, Circle, Clock, User,
  Minus, ArrowUp, ArrowDown,
} from 'lucide-react';

interface GitCommit {
  hash: string;
  shortHash: string;
  message: string;
  author: string;
  date: string;
  branch: string;
  parents: string[];
}

interface GitBranch {
  name: string;
  commits: string[];
  isRemote: boolean;
  upstream?: string;
  ahead: number;
  behind: number;
}

interface GitFile {
  name: string;
  status: 'modified' | 'added' | 'deleted' | 'renamed';
  additions: number;
  deletions: number;
  diff: string;
}

const COLORS = ['#7C4DFF', '#FF9800', '#4CAF50', '#2196F3', '#E91E63', '#00BCD4', '#FF5722'];

function generateMockHistory(): { commits: GitCommit[]; branches: GitBranch[]; staged: GitFile[]; unstaged: GitFile[] } {
  const commits: GitCommit[] = [
    { hash: 'a1b2c3d4e5f6', shortHash: 'a1b2c3d', message: 'Initial commit: project setup', author: 'Alice', date: '2025-01-15 09:00', branch: 'main', parents: [] },
    { hash: 'b2c3d4e5f6a7', shortHash: 'b2c3d4e', message: 'Add README and license', author: 'Bob', date: '2025-01-15 10:30', branch: 'main', parents: ['a1b2c3d4e5f6'] },
    { hash: 'c3d4e5f6a7b8', shortHash: 'c3d4e5f', message: 'Setup build configuration', author: 'Alice', date: '2025-01-16 11:00', branch: 'main', parents: ['b2c3d4e5f6a7'] },
    { hash: 'd4e5f6a7b8c9', shortHash: 'd4e5f6a', message: 'Implement core module', author: 'Charlie', date: '2025-01-17 14:20', branch: 'main', parents: ['c3d4e5f6a7b8'] },
    { hash: 'e5f6a7b8c9d0', shortHash: 'e5f6a7b', message: 'Add feature: user authentication', author: 'Alice', date: '2025-01-18 09:45', branch: 'feature/auth', parents: ['c3d4e5f6a7b8'] },
    { hash: 'f6a7b8c9d0e1', shortHash: 'f6a7b8c', message: 'Add login form component', author: 'Alice', date: '2025-01-18 11:30', branch: 'feature/auth', parents: ['e5f6a7b8c9d0'] },
    { hash: 'a7b8c9d0e1f2', shortHash: 'a7b8c9d', message: 'Fix: validation bug in auth', author: 'Bob', date: '2025-01-19 08:15', branch: 'feature/auth', parents: ['f6a7b8c9d0e1'] },
    { hash: 'b8c9d0e1f2a3', shortHash: 'b8c9d0e', message: 'Merge feature/auth into main', author: 'Alice', date: '2025-01-19 16:00', branch: 'main', parents: ['d4e5f6a7b8c9', 'a7b8c9d0e1f2'] },
    { hash: 'c9d0e1f2a3b4', shortHash: 'c9d0e1f', message: 'Add unit tests for auth', author: 'Charlie', date: '2025-01-20 10:00', branch: 'main', parents: ['b8c9d0e1f2a3'] },
    { hash: 'd0e1f2a3b4c5', shortHash: 'd0e1f2a', message: 'Refactor: optimize rendering', author: 'Alice', date: '2025-01-21 14:30', branch: 'main', parents: ['c9d0e1f2a3b4'] },
  ];

  const branches: GitBranch[] = [
    { name: 'main', commits: ['d0e1f2a3b4c5', 'c9d0e1f2a3b4', 'b8c9d0e1f2a3', 'd4e5f6a7b8c9', 'c3d4e5f6a7b8', 'b2c3d4e5f6a7', 'a1b2c3d4e5f6'], isRemote: false, ahead: 0, behind: 0 },
    { name: 'feature/auth', commits: ['a7b8c9d0e1f2', 'f6a7b8c9d0e1', 'e5f6a7b8c9d0'], isRemote: true, upstream: 'origin/feature/auth', ahead: 0, behind: 0 },
    { name: 'feature/ui', commits: ['c3d4e5f6a7b8', 'b2c3d4e5f6a7', 'a1b2c3d4e5f6'], isRemote: false, ahead: 2, behind: 3 },
    { name: 'hotfix/login', commits: ['d0e1f2a3b4c5', 'c9d0e1f2a3b4'], isRemote: true, upstream: 'origin/hotfix/login', ahead: 1, behind: 0 },
  ];

  const staged: GitFile[] = [
    { name: 'src/components/Button.tsx', status: 'modified', additions: 12, deletions: 3, diff: '+ import React from "react"\n+ export const Button = () => {\n+   return <button>Click</button>\n+ }\n- const Button = () => {}' },
    { name: 'src/styles/theme.css', status: 'added', additions: 45, deletions: 0, diff: '+ :root {\n+   --primary: #7C4DFF;\n+   --bg: #1E1E1E;\n+ }' },
  ];

  const unstaged: GitFile[] = [
    { name: 'src/App.tsx', status: 'modified', additions: 8, deletions: 2, diff: '+ import { BrowserRouter } from "react-router-dom"\n+ <BrowserRouter>\n- <Router>' },
    { name: 'package.json', status: 'modified', additions: 1, deletions: 1, diff: '- "version": "1.0.0"\n+ "version": "1.1.0"' },
    { name: 'README.md', status: 'deleted', additions: 0, deletions: 20, diff: '- # Project Name\n- Getting started...' },
  ];

  return { commits, branches, staged, unstaged };
}

const getStatusIcon = (status: GitFile['status']) => {
  switch (status) {
    case 'added': return <Plus size={14} className="text-green-500" />;
    case 'deleted': return <Minus size={14} className="text-red-500" />;
    case 'modified': return <Circle size={14} className="text-yellow-500" />;
    case 'renamed': return <GitMerge size={14} className="text-blue-500" />;
  }
};

export default function GitClient() {
  const [activeTab, setActiveTab] = useState<'history' | 'changes' | 'branches'>('history');
  const [repo] = useState(() => generateMockHistory());
  const [currentBranch, setCurrentBranch] = useState('main');
  const [selectedCommit, setSelectedCommit] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<GitFile | null>(null);
  const [commitMessage, setCommitMessage] = useState('');
  const [expandedBranches, setExpandedBranches] = useState(true);

  const toggleBranchExpand = useCallback(() => setExpandedBranches((v) => !v), []);

  const branchCommits = useMemo(() => {
    const branch = repo.branches.find((b) => b.name === currentBranch);
    if (!branch) return [];
    return branch.commits.map((h) => repo.commits.find((c) => c.hash === h)).filter(Boolean) as GitCommit[];
  }, [repo, currentBranch]);

  const handleCommit = useCallback(() => {
    if (!commitMessage.trim()) return;
    setCommitMessage('');
  }, [commitMessage]);

  const handleStageAll = useCallback(() => { }, []);
  const handleUnstageAll = useCallback(() => { }, []);

  return (
    <div className="h-full flex flex-col" style={{ background: 'var(--bg-window)' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-1.5 shrink-0" style={{ background: 'var(--bg-titlebar)', borderBottom: '1px solid var(--border-subtle)' }}>
        <div className="flex items-center gap-2">
          <GitBranch size={16} style={{ color: 'var(--accent-primary)' }} />
          <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>my-project</span>
          <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: 'var(--bg-active)', color: 'var(--accent-primary)' }}>
            {currentBranch}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <span className="flex items-center gap-1 text-xs" style={{ color: 'var(--accent-success)' }}><ArrowUp size={12} />0</span>
          <span className="flex items-center gap-1 text-xs" style={{ color: 'var(--accent-info)' }}><ArrowDown size={12} />0</span>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex items-center px-3 shrink-0" style={{ height: 36, background: 'var(--bg-titlebar)', borderBottom: '1px solid var(--border-subtle)' }}>
        {(['history', 'changes', 'branches'] as const).map((tab) => (
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
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar */}
        <div className="shrink-0 overflow-y-auto custom-scrollbar" style={{ width: 180, background: 'var(--bg-window)', borderRight: '1px solid var(--border-subtle)' }}>
          {/* Branches */}
          <div className="py-1">
            <button onClick={toggleBranchExpand} className="flex items-center gap-1 px-2 py-1 text-xs w-full hover:bg-[var(--bg-hover)]">
              {expandedBranches ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
              <span style={{ color: 'var(--text-secondary)' }}>BRANCHES</span>
            </button>
            {expandedBranches && repo.branches.map((b) => (
              <div
                key={b.name}
                className="flex items-center gap-1.5 px-2 py-1 cursor-pointer text-xs hover:bg-[var(--bg-hover)]"
                style={{
                  background: b.name === currentBranch ? 'var(--bg-selected)' : 'transparent',
                  color: 'var(--text-primary)',
                }}
                onClick={() => setCurrentBranch(b.name)}
              >
                {b.name === currentBranch ? <GitBranch size={12} style={{ color: 'var(--accent-primary)' }} /> : <GitBranch size={12} style={{ color: 'var(--text-disabled)' }} />}
                <span>{b.name}</span>
                {b.isRemote && <span className="text-[10px]" style={{ color: 'var(--text-disabled)' }}>origin</span>}
              </div>
            ))}
          </div>
        </div>

        {/* Main content */}
        <div className="flex-1 overflow-auto custom-scrollbar">
          {activeTab === 'history' && (
            <div className="p-3">
              {/* Commit graph */}
              <div className="flex flex-col gap-1">
                {branchCommits.map((commit, idx) => {
                  const isMerge = commit.parents.length > 1;
                  const isSelected = selectedCommit === commit.hash;
                  return (
                    <div
                      key={commit.hash}
                      className="flex items-start gap-3 p-2 rounded cursor-pointer transition-colors"
                      style={{ background: isSelected ? 'var(--bg-selected)' : 'transparent' }}
                      onClick={() => setSelectedCommit(isSelected ? null : commit.hash)}
                    >
                      {/* Graph line */}
                      <div className="flex flex-col items-center shrink-0" style={{ width: 32 }}>
                        <div
                          className="w-4 h-4 rounded-full border-2 shrink-0"
                          style={{
                            borderColor: COLORS[idx % COLORS.length],
                            background: isSelected ? COLORS[idx % COLORS.length] : 'transparent',
                          }}
                        />
                        {idx < branchCommits.length - 1 && (
                          <div className="w-0.5 flex-1" style={{ background: 'var(--border-default)', minHeight: 20 }} />
                        )}
                      </div>

                      {/* Commit info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium truncate" style={{ color: 'var(--text-primary)' }}>
                            {commit.message}
                          </span>
                          {isMerge && (
                            <span className="text-[10px] px-1 py-0.5 rounded" style={{ background: 'var(--bg-active)', color: 'var(--accent-primary)' }}>
                              merge
                            </span>
                          )}
                          {idx === 0 && (
                            <span className="text-[10px] px-1 py-0.5 rounded" style={{ background: 'var(--accent-primary)', color: 'white' }}>
                              HEAD
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-3 mt-0.5">
                          <span className="text-xs font-mono" style={{ color: 'var(--accent-primary)' }}>{commit.shortHash}</span>
                          <span className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-secondary)' }}>
                            <User size={10} /> {commit.author}
                          </span>
                          <span className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-disabled)' }}>
                            <Clock size={10} /> {commit.date}
                          </span>
                        </div>

                        {/* Expanded diff */}
                        {isSelected && (
                          <div className="mt-2 p-2 rounded text-xs" style={{ background: 'var(--bg-input)', fontFamily: "'JetBrains Mono', monospace" }}>
                            <div className="mb-1" style={{ color: 'var(--text-secondary)' }}>Commit {commit.shortHash}</div>
                            <div style={{ color: 'var(--text-primary)' }}>
                              {commit.parents.length > 1 ? 'Merged branches' : `Parent: ${commit.parents[0]?.slice(0, 7) || 'none'}`}
                            </div>
                            <div className="mt-1" style={{ color: 'var(--text-secondary)' }}>Branch: {commit.branch}</div>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {activeTab === 'changes' && (
            <div className="flex h-full">
              {/* File lists */}
              <div className="flex-1 overflow-y-auto p-3 custom-scrollbar">
                {/* Staged */}
                <div className="mb-4">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>STAGED ({repo.staged.length})</span>
                    <button onClick={handleUnstageAll} className="text-xs px-2 py-0.5 rounded hover:bg-[var(--bg-hover)]">Unstage All</button>
                  </div>
                  {repo.staged.map((file) => (
                    <div
                      key={file.name}
                      className="flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer hover:bg-[var(--bg-hover)]"
                      style={{ background: selectedFile?.name === file.name ? 'var(--bg-selected)' : 'transparent' }}
                      onClick={() => setSelectedFile(file)}
                    >
                      {getStatusIcon(file.status)}
                      <span className="text-xs flex-1 truncate" style={{ color: 'var(--text-primary)' }}>{file.name}</span>
                      <span className="text-xs text-green-500">+{file.additions}</span>
                      <span className="text-xs text-red-500">-{file.deletions}</span>
                    </div>
                  ))}
                </div>

                {/* Unstaged */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>CHANGES ({repo.unstaged.length})</span>
                    <button onClick={handleStageAll} className="text-xs px-2 py-0.5 rounded hover:bg-[var(--bg-hover)]">Stage All</button>
                  </div>
                  {repo.unstaged.map((file) => (
                    <div
                      key={file.name}
                      className="flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer hover:bg-[var(--bg-hover)]"
                      style={{ background: selectedFile?.name === file.name ? 'var(--bg-selected)' : 'transparent' }}
                      onClick={() => setSelectedFile(file)}
                    >
                      {getStatusIcon(file.status)}
                      <span className="text-xs flex-1 truncate" style={{ color: 'var(--text-primary)' }}>{file.name}</span>
                      <span className="text-xs text-green-500">+{file.additions}</span>
                      <span className="text-xs text-red-500">-{file.deletions}</span>
                    </div>
                  ))}
                </div>

                {/* Commit message */}
                <div className="mt-4 p-2 rounded" style={{ background: 'var(--bg-titlebar)' }}>
                  <textarea
                    value={commitMessage}
                    onChange={(e) => setCommitMessage(e.target.value)}
                    placeholder="Commit message..."
                    className="w-full text-xs p-2 rounded outline-none resize-none"
                    style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)', height: 60 }}
                  />
                  <button
                    onClick={handleCommit}
                    className="mt-1 px-3 py-1 rounded text-xs font-medium transition-colors disabled:opacity-50"
                    style={{ background: 'var(--accent-primary)', color: 'white' }}
                    disabled={!commitMessage.trim()}
                  >
                    Commit
                  </button>
                </div>
              </div>

              {/* Diff panel */}
              {selectedFile && (
                <div className="shrink-0 overflow-y-auto custom-scrollbar p-3" style={{ width: 360, borderLeft: '1px solid var(--border-subtle)', background: 'var(--bg-window)' }}>
                  <div className="text-xs font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>{selectedFile.name}</div>
                  <pre className="text-xs whitespace-pre-wrap break-all" style={{ fontFamily: "'JetBrains Mono', monospace", lineHeight: '18px' }}>
                    {selectedFile.diff.split('\n').map((line, i) => (
                      <div key={i} style={{
                        background: line.startsWith('+') ? 'rgba(76,175,80,0.1)' : line.startsWith('-') ? 'rgba(244,67,54,0.1)' : 'transparent',
                        color: line.startsWith('+') ? '#4CAF50' : line.startsWith('-') ? '#F44336' : 'var(--text-primary)',
                      }}>
                        {line}
                      </div>
                    ))}
                  </pre>
                </div>
              )}
            </div>
          )}

          {activeTab === 'branches' && (
            <div className="p-3">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>LOCAL BRANCHES</span>
              </div>
              {repo.branches.filter((b) => !b.isRemote).map((b) => (
                <div
                  key={b.name}
                  className="flex items-center justify-between p-2 rounded mb-1 cursor-pointer hover:bg-[var(--bg-hover)]"
                  style={{ background: b.name === currentBranch ? 'var(--bg-selected)' : 'transparent' }}
                  onClick={() => setCurrentBranch(b.name)}
                >
                  <div className="flex items-center gap-2">
                    <GitBranch size={14} style={{ color: b.name === currentBranch ? 'var(--accent-primary)' : 'var(--text-secondary)' }} />
                    <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>{b.name}</span>
                    {b.name === currentBranch && <span className="text-[10px] px-1 rounded" style={{ background: 'var(--accent-primary)', color: 'white' }}>current</span>}
                  </div>
                  <div className="flex items-center gap-2">
                    {b.ahead > 0 && <span className="flex items-center gap-0.5 text-xs text-green-500"><ArrowUp size={10} />{b.ahead}</span>}
                    {b.behind > 0 && <span className="flex items-center gap-0.5 text-xs text-blue-500"><ArrowDown size={10} />{b.behind}</span>}
                  </div>
                </div>
              ))}

              <div className="flex items-center justify-between mt-4 mb-3">
                <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>REMOTE BRANCHES</span>
              </div>
              {repo.branches.filter((b) => b.isRemote).map((b) => (
                <div
                  key={b.name}
                  className="flex items-center justify-between p-2 rounded mb-1 cursor-pointer hover:bg-[var(--bg-hover)]"
                  style={{ background: b.name === currentBranch ? 'var(--bg-selected)' : 'transparent' }}
                  onClick={() => setCurrentBranch(b.name)}
                >
                  <div className="flex items-center gap-2">
                    <GitBranch size={14} style={{ color: 'var(--text-disabled)' }} />
                    <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{b.name}</span>
                    {b.upstream && <span className="text-[10px]" style={{ color: 'var(--text-disabled)' }}>{b.upstream}</span>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

import { useState, useEffect, useCallback } from 'react';
import {
  Server, Upload, Download, FolderPlus, Trash2, RefreshCw, ChevronRight,
  File, Folder, HardDrive, Globe, Link, Unlink, X, Check
} from 'lucide-react';
import { useFileSystem } from '@/hooks/useFileSystem';

interface RemoteFile {
  id: string;
  name: string;
  type: 'file' | 'folder';
  size: number;
  date: string;
  parentId: string | null;
}

interface TransferItem {
  id: string;
  name: string;
  direction: 'upload' | 'download';
  progress: number;
  status: 'pending' | 'running' | 'completed' | 'error';
}

const generateMockRemoteFiles = (): RemoteFile[] => {
  const rootId = 'remote-root';
  const files: RemoteFile[] = [
    { id: rootId, name: '/', type: 'folder', size: 0, date: '', parentId: null },
    { id: 'r1', name: 'public_html', type: 'folder', size: 0, date: '2025-01-15', parentId: rootId },
    { id: 'r2', name: 'logs', type: 'folder', size: 0, date: '2025-01-20', parentId: rootId },
    { id: 'r3', name: 'backups', type: 'folder', size: 0, date: '2025-02-01', parentId: rootId },
    { id: 'r4', name: 'index.html', type: 'file', size: 4500, date: '2025-03-01', parentId: 'r1' },
    { id: 'r5', name: 'style.css', type: 'file', size: 3200, date: '2025-03-02', parentId: 'r1' },
    { id: 'r6', name: 'script.js', type: 'file', size: 8900, date: '2025-03-03', parentId: 'r1' },
    { id: 'r7', name: 'logo.png', type: 'file', size: 25600, date: '2025-02-15', parentId: 'r1' },
    { id: 'r8', name: 'README.md', type: 'file', size: 2100, date: '2025-01-10', parentId: rootId },
    { id: 'r9', name: 'server.log', type: 'file', size: 128000, date: '2025-03-10', parentId: 'r2' },
    { id: 'r10', name: 'error.log', type: 'file', size: 45000, date: '2025-03-10', parentId: 'r2' },
    { id: 'r11', name: 'backup-2025-03-01.tar.gz', type: 'file', size: 10485760, date: '2025-03-01', parentId: 'r3' },
    { id: 'r12', name: 'backup-2025-02-01.tar.gz', type: 'file', size: 9876543, date: '2025-02-01', parentId: 'r3' },
    { id: 'r13', name: '.htaccess', type: 'file', size: 450, date: '2025-01-05', parentId: rootId },
  ];
  return files;
};

const formatBytes = (bytes: number) => {
  if (bytes === 0) return '-';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

export default function FtpClient() {
  const { fs, getChildren, getNodeById } = useFileSystem();
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [host, setHost] = useState('ftp.example.com');
  const [port, setPort] = useState('21');
  const [username, setUsername] = useState('user');
  const [password, setPassword] = useState('password');
  const [remoteFiles] = useState<RemoteFile[]>(generateMockRemoteFiles);
  const [remotePath, setRemotePath] = useState<string>('remote-root');
  const [localPath, setLocalPath] = useState<string | null>(null);
  const [transfers, setTransfers] = useState<TransferItem[]>([]);
  const [selectedLocal, setSelectedLocal] = useState<string | null>(null);
  const [selectedRemote, setSelectedRemote] = useState<string | null>(null);
  const [showNewFolder, setShowNewFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');

  useEffect(() => {
    const rootNode = Object.values(fs.nodes).find(n => n.parentId === null);
    if (rootNode) {
      const userNode = getChildren(rootNode.id).find(n => n.name === 'home');
      if (userNode) {
        const homeChild = getChildren(userNode.id).find(n => n.name === 'user');
        if (homeChild) setLocalPath(homeChild.id);
      }
    }
  }, [fs, getChildren]);

  const localNodes = localPath ? getChildren(localPath) : [];
  const currentRemote = remoteFiles.filter(r => r.parentId === remotePath);

  const connect = () => {
    setConnecting(true);
    setTimeout(() => { setConnecting(false); setConnected(true); }, 1500);
  };

  const disconnect = () => { setConnected(false); };

  const addTransfer = (name: string, direction: 'upload' | 'download') => {
    const item: TransferItem = { id: Date.now().toString(), name, direction, progress: 0, status: 'pending' };
    setTransfers(prev => [...prev, item]);
    // Simulate progress
    let progress = 0;
    const interval = setInterval(() => {
      progress += Math.random() * 20 + 5;
      if (progress >= 100) {
        progress = 100;
        clearInterval(interval);
        setTransfers(prev => prev.map(t => t.id === item.id ? { ...t, progress: 100, status: 'completed' } : t));
      } else {
        setTransfers(prev => prev.map(t => t.id === item.id ? { ...t, progress, status: 'running' } : t));
      }
    }, 300);
  };

  const downloadFile = () => {
    if (!selectedRemote) return;
    const file = remoteFiles.find(f => f.id === selectedRemote);
    if (file && file.type === 'file') addTransfer(file.name, 'download');
  };

  const uploadFile = () => {
    if (!selectedLocal) return;
    const node = getNodeById(selectedLocal);
    if (node && node.type === 'file') addTransfer(node.name, 'upload');
  };

  const navigateRemote = (folderId: string) => setRemotePath(folderId);
  const navigateLocal = (folderId: string) => setLocalPath(folderId);

  const getRemoteBreadcrumb = () => {
    const parts: { name: string; id: string }[] = [];
    let current = remotePath;
    while (current) {
      const node = remoteFiles.find(f => f.id === current);
      if (!node) break;
      parts.unshift({ name: node.name, id: node.id });
      current = node.parentId || '';
    }
    return parts;
  };

  if (!connected) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4" style={{ background: 'var(--bg-window)' }}>
        <div className="w-16 h-16 rounded-full flex items-center justify-center" style={{ background: 'var(--accent-primary)' }}>
          <Server size={28} color="#fff" />
        </div>
        <div className="text-center">
          <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>FTP Client</h3>
          <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>Connect to a remote server</p>
        </div>
        <div className="w-72 space-y-2">
          <div className="flex gap-2">
            <input value={host} onChange={e => setHost(e.target.value)} placeholder="Host" className="flex-1 px-2.5 py-1.5 rounded-md text-xs outline-none" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }} />
            <input value={port} onChange={e => setPort(e.target.value)} placeholder="Port" className="w-16 px-2.5 py-1.5 rounded-md text-xs outline-none" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }} />
          </div>
          <input value={username} onChange={e => setUsername(e.target.value)} placeholder="Username" className="w-full px-2.5 py-1.5 rounded-md text-xs outline-none" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }} />
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Password" className="w-full px-2.5 py-1.5 rounded-md text-xs outline-none" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }} />
          <button onClick={connect} disabled={connecting} className="w-full py-2 rounded-md text-xs font-medium flex items-center justify-center gap-2" style={{ background: 'var(--accent-primary)', color: '#fff', opacity: connecting ? 0.7 : 1 }}>
            {connecting ? <RefreshCw size={12} className="animate-spin" /> : <Link size={12} />}{connecting ? 'Connecting...' : 'Connect'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-window)' }}>
      {/* Toolbar */}
      <div className="flex items-center gap-1 px-3 py-1.5 border-b" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-panel)' }}>
        <div className="flex items-center gap-1.5 px-2 py-1 rounded-md text-xs" style={{ background: 'rgba(76,175,80,0.15)', color: '#4CAF50' }}>
          <Globe size={10} /> {host}:{port}
        </div>
        <button onClick={disconnect} className="flex items-center gap-1 px-2 py-1 rounded-md text-xs" style={{ color: 'var(--accent-error)' }}><Unlink size={10} /> Disconnect</button>
        <div className="w-px h-4 mx-1" style={{ background: 'var(--border-subtle)' }} />
        <button onClick={downloadFile} disabled={!selectedRemote} className="flex items-center gap-1 px-2 py-1 rounded-md text-xs" style={{ color: selectedRemote ? 'var(--accent-primary)' : 'var(--text-disabled)' }}><Download size={10} /> Download</button>
        <button onClick={uploadFile} disabled={!selectedLocal} className="flex items-center gap-1 px-2 py-1 rounded-md text-xs" style={{ color: selectedLocal ? 'var(--accent-primary)' : 'var(--text-disabled)' }}><Upload size={10} /> Upload</button>
        <div className="flex-1" />
        <button onClick={() => { const f = remoteFiles.find(rf => rf.id === selectedRemote); if (f) { setTransfers(prev => prev.filter(t => t.name !== f.name)); } }} className="p-1 rounded" style={{ color: 'var(--text-secondary)' }}><RefreshCw size={12} /></button>
      </div>

      {/* Two Panes */}
      <div className="flex-1 flex overflow-hidden">
        {/* Local */}
        <div className="flex-1 border-r flex flex-col min-w-0" style={{ borderColor: 'var(--border-subtle)' }}>
          <div className="flex items-center gap-1 px-2 py-1 border-b text-xs" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-panel)' }}>
            <HardDrive size={10} style={{ color: 'var(--text-secondary)' }} />
            <span className="truncate" style={{ color: 'var(--text-secondary)' }}>Local</span>
          </div>
          <div className="flex-1 overflow-auto custom-scrollbar">
            {localNodes.map(node => (
              <button
                key={node.id}
                onClick={() => setSelectedLocal(node.id)}
                onDoubleClick={() => node.type === 'folder' ? navigateLocal(node.id) : undefined}
                className="flex items-center gap-2 w-full px-3 py-1.5 text-xs text-left transition-colors"
                style={{ background: selectedLocal === node.id ? 'var(--bg-selected)' : 'transparent', color: 'var(--text-primary)' }}
                onMouseEnter={e => (e.currentTarget.style.background = selectedLocal === node.id ? 'var(--bg-selected)' : 'var(--bg-hover)')}
                onMouseLeave={e => (e.currentTarget.style.background = selectedLocal === node.id ? 'var(--bg-selected)' : 'transparent')}
              >
                {node.type === 'folder' ? <Folder size={12} style={{ color: 'var(--accent-primary)' }} /> : <File size={12} style={{ color: 'var(--text-secondary)' }} />}
                <span className="flex-1 truncate">{node.name}</span>
                <span className="text-[10px]" style={{ color: 'var(--text-disabled)' }}>{node.type === 'file' ? formatBytes(node.size || 0) : ''}</span>
              </button>
            ))}
            {localNodes.length === 0 && <div className="text-center py-8 text-xs" style={{ color: 'var(--text-secondary)' }}>Empty folder</div>}
          </div>
        </div>

        {/* Remote */}
        <div className="flex-1 flex flex-col min-w-0">
          <div className="flex items-center gap-1 px-2 py-1 border-b text-xs" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-panel)' }}>
            <Server size={10} style={{ color: 'var(--accent-primary)' }} />
            {getRemoteBreadcrumb().map((crumb, i, arr) => (
              <span key={crumb.id} className="flex items-center">
                {i > 0 && <ChevronRight size={8} style={{ color: 'var(--text-disabled)' }} />}
                <button onClick={() => navigateRemote(crumb.id)} className="truncate hover:underline" style={{ color: i === arr.length - 1 ? 'var(--accent-primary)' : 'var(--text-secondary)' }}>{i === 0 ? 'Remote' : crumb.name}</button>
              </span>
            ))}
          </div>
          <div className="flex-1 overflow-auto custom-scrollbar">
            {currentRemote.map(file => (
              <button
                key={file.id}
                onClick={() => setSelectedRemote(file.id)}
                onDoubleClick={() => file.type === 'folder' ? navigateRemote(file.id) : undefined}
                className="flex items-center gap-2 w-full px-3 py-1.5 text-xs text-left transition-colors"
                style={{ background: selectedRemote === file.id ? 'var(--bg-selected)' : 'transparent', color: 'var(--text-primary)' }}
                onMouseEnter={e => (e.currentTarget.style.background = selectedRemote === file.id ? 'var(--bg-selected)' : 'var(--bg-hover)')}
                onMouseLeave={e => (e.currentTarget.style.background = selectedRemote === file.id ? 'var(--bg-selected)' : 'transparent')}
              >
                {file.type === 'folder' ? <Folder size={12} style={{ color: 'var(--accent-primary)' }} /> : <File size={12} style={{ color: 'var(--text-secondary)' }} />}
                <span className="flex-1 truncate">{file.name}</span>
                <span className="text-[10px]" style={{ color: 'var(--text-disabled)' }}>{file.type === 'file' ? formatBytes(file.size) : ''}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Transfer Queue */}
      {transfers.length > 0 && (
        <div className="border-t" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-panel)', maxHeight: '120px' }}>
          <div className="px-3 py-1 text-[10px] font-semibold uppercase" style={{ color: 'var(--text-secondary)' }}>Transfers</div>
          <div className="overflow-auto custom-scrollbar px-3 pb-2 space-y-1">
            {transfers.map(t => (
              <div key={t.id} className="flex items-center gap-2">
                {t.direction === 'download' ? <Download size={10} style={{ color: 'var(--accent-primary)' }} /> : <Upload size={10} style={{ color: 'var(--accent-secondary)' }} />}
                <span className="text-[10px] flex-1 truncate" style={{ color: 'var(--text-primary)' }}>{t.name}</span>
                <div className="w-24 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--bg-hover)' }}>
                  <div className="h-full rounded-full transition-all" style={{ width: `${t.progress}%`, background: t.status === 'completed' ? 'var(--accent-success)' : 'var(--accent-primary)' }} />
                </div>
                <span className="text-[9px] w-10 text-right" style={{ color: t.status === 'completed' ? 'var(--accent-success)' : 'var(--text-secondary)' }}>{Math.round(t.progress)}%</span>
                {t.status === 'completed' && <Check size={10} style={{ color: 'var(--accent-success)' }} />}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

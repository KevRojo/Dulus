// ============================================================
// FileManager — Three-pane file manager with breadcrumb nav
// ============================================================

import { useState, useMemo, useCallback, useRef } from 'react';
import { useFileSystem } from '@/hooks/useFileSystem';
import type { FileSystemNode } from '@/types';
import {
  Folder, FileText, ChevronRight, Home, ArrowUp,
  Grid3x3, List, Search, Trash2, FolderPlus, FilePlus,
} from 'lucide-react';

const SIDEBAR_ITEMS = [
  { id: 'home', name: 'Home', icon: 'Home', path: '/home/user' },
  { id: 'desktop', name: 'Desktop', icon: 'Monitor', path: '/home/user/Desktop' },
  { id: 'documents', name: 'Documents', icon: 'FileText', path: '/home/user/Documents' },
  { id: 'downloads', name: 'Downloads', icon: 'Download', path: '/home/user/Downloads' },
  { id: 'music', name: 'Music', icon: 'Music', path: '/home/user/Music' },
  { id: 'pictures', name: 'Pictures', icon: 'Image', path: '/home/user/Pictures' },
  { id: 'videos', name: 'Videos', icon: 'Video', path: '/home/user/Videos' },
  { id: 'trash', name: 'Trash', icon: 'Trash2', path: '/home/user/.trash' },
];

const getFileIcon = (name: string, type: FileSystemNode['type']) => {
  if (type === 'folder') return Folder;
  if (name.endsWith('.txt')) return FileText;
  if (name.endsWith('.json')) return FileText;
  if (name.endsWith('.js') || name.endsWith('.ts')) return FileText;
  if (name.endsWith('.md')) return FileText;
  return FileText;
};

export default function FileManager() {
  const fs = useFileSystem();
  const [currentFolderId, setCurrentFolderId] = useState<string>(() => {
    // Find home/user folder
    const rootChildren = Object.values(fs.fs.nodes).filter((n) => n.parentId === null);
    const homeNode = rootChildren.find((n) => n.name === 'home');
    const userNode = homeNode
      ? Object.values(fs.fs.nodes).find((n) => n.parentId === homeNode.id && n.name === 'user')
      : undefined;
    return userNode?.id || '';
  });
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('list');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isCreatingFolder, setIsCreatingFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [isCreatingFile, setIsCreatingFile] = useState(false);
  const [newFileName, setNewFileName] = useState('');
  const [renameId, setRenameId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const currentNode = fs.getNodeById(currentFolderId);
  const children = fs.getChildren(currentFolderId);

  const filteredChildren = useMemo(() => {
    if (!searchQuery) return children;
    return children.filter((c) =>
      c.name.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [children, searchQuery]);

  // Breadcrumb path
  const breadcrumb = useMemo(() => {
    const path: FileSystemNode[] = [];
    let node = currentNode;
    while (node) {
      path.unshift(node);
      node = node.parentId ? fs.getNodeById(node.parentId) : undefined;
    }
    return path;
  }, [currentNode, fs]);

  const navigateTo = useCallback((id: string) => {
    setCurrentFolderId(id);
    setSelectedId(null);
  }, []);

  const navigateUp = useCallback(() => {
    if (currentNode?.parentId) {
      navigateTo(currentNode.parentId);
    }
  }, [currentNode, navigateTo]);

  const handleDoubleClick = useCallback(
    (node: FileSystemNode) => {
      if (node.type === 'folder') {
        navigateTo(node.id);
      }
    },
    [navigateTo]
  );

  const handleCreateFolder = useCallback(() => {
    if (!newFolderName.trim()) return;
    fs.createFolder(currentFolderId, newFolderName.trim());
    setNewFolderName('');
    setIsCreatingFolder(false);
  }, [fs, currentFolderId, newFolderName]);

  const handleCreateFile = useCallback(() => {
    if (!newFileName.trim()) return;
    fs.createFile(currentFolderId, newFileName.trim());
    setNewFileName('');
    setIsCreatingFile(false);
  }, [fs, currentFolderId, newFileName]);

  const handleRename = useCallback(() => {
    if (!renameId || !renameValue.trim()) {
      setRenameId(null);
      return;
    }
    fs.renameNode(renameId, renameValue.trim());
    setRenameId(null);
    setRenameValue('');
  }, [fs, renameId, renameValue]);

  /* Delete handler - unused for now */
  // const handleDelete = useCallback(
  //   (id: string) => {
  //     fs.moveToTrash(id);
  //     setSelectedId(null);
  //   },
  //   [fs]
  // );

  const handleSidebarClick = useCallback(
    (path: string) => {
      const node = fs.findNodeByPath(path);
      if (node) navigateTo(node.id);
    },
    [fs, navigateTo]
  );

  // Sort folders first
  const sortedChildren = useMemo(() => {
    return [...filteredChildren].sort((a, b) => {
      if (a.type === b.type) return a.name.localeCompare(b.name);
      return a.type === 'folder' ? -1 : 1;
    });
  }, [filteredChildren]);

  return (
    <div className="flex h-full text-[var(--text-primary)]">
      {/* Sidebar */}
      <div className="w-48 shrink-0 border-r border-[var(--border-subtle)] overflow-y-auto py-2">
        {SIDEBAR_ITEMS.map((item) => (
          <button
            key={item.id}
            onClick={() => handleSidebarClick(item.path)}
            className="w-full flex items-center gap-2.5 px-3 py-1.5 text-xs text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition-colors text-left"
          >
            {item.id === 'home' && <Home size={14} />}
            {item.id === 'desktop' && <Folder size={14} />}
            {item.id === 'documents' && <FileText size={14} />}
            {item.id === 'downloads' && <Folder size={14} />}
            {item.id === 'music' && <span>🎵</span>}
            {item.id === 'pictures' && <span>🖼</span>}
            {item.id === 'videos' && <span>🎬</span>}
            {item.id === 'trash' && <Trash2 size={14} />}
            <span className="truncate">{item.name}</span>
          </button>
        ))}
      </div>

      {/* Main area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Toolbar */}
        <div className="flex items-center gap-2 px-3 py-2 border-b border-[var(--border-subtle)]">
          <button
            onClick={navigateUp}
            className="w-7 h-7 rounded flex items-center justify-center text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] disabled:opacity-30"
            disabled={!currentNode?.parentId}
          >
            <ArrowUp size={14} />
          </button>
          <div className="flex items-center gap-0.5 text-xs text-[var(--text-secondary)] overflow-hidden flex-1">
            {breadcrumb.map((node, i) => (
              <div key={node.id} className="flex items-center shrink-0">
                {i > 0 && <ChevronRight size={12} className="mx-0.5" />}
                <button
                  onClick={() => navigateTo(node.id)}
                  className="px-1.5 py-0.5 rounded hover:bg-[var(--bg-hover)] text-[var(--text-primary)] truncate max-w-[80px]"
                >
                  {node.name === '/' ? 'Computer' : node.name}
                </button>
              </div>
            ))}
          </div>

          {/* Search */}
          <div className="relative">
            <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search"
              className="h-7 w-36 rounded-md pl-7 pr-2 text-xs outline-none"
              style={{
                background: 'var(--bg-input)',
                border: '1px solid var(--border-default)',
                color: 'var(--text-primary)',
              }}
            />
          </div>

          {/* View toggle */}
          <div className="flex items-center">
            <button
              onClick={() => setViewMode('grid')}
              className="w-7 h-7 rounded flex items-center justify-center text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
              style={{ background: viewMode === 'grid' ? 'var(--bg-hover)' : 'transparent' }}
            >
              <Grid3x3 size={14} />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className="w-7 h-7 rounded flex items-center justify-center text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
              style={{ background: viewMode === 'list' ? 'var(--bg-hover)' : 'transparent' }}
            >
              <List size={14} />
            </button>
          </div>

          {/* Create buttons */}
          <button
            onClick={() => { setIsCreatingFolder(true); setTimeout(() => inputRef.current?.focus(), 50); }}
            className="w-7 h-7 rounded flex items-center justify-center text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
            title="New Folder"
          >
            <FolderPlus size={14} />
          </button>
          <button
            onClick={() => { setIsCreatingFile(true); setTimeout(() => inputRef.current?.focus(), 50); }}
            className="w-7 h-7 rounded flex items-center justify-center text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
            title="New File"
          >
            <FilePlus size={14} />
          </button>
        </div>

        {/* File list header (list view) */}
        {viewMode === 'list' && (
          <div
            className="flex items-center px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]"
            style={{ borderBottom: '1px solid var(--border-subtle)' }}
          >
            <span className="flex-1">Name</span>
            <span className="w-20 text-right">Size</span>
            <span className="w-28 text-right">Modified</span>
          </div>
        )}

        {/* File list */}
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          {/* New folder input */}
          {isCreatingFolder && (
            <div className="flex items-center gap-2 px-3 py-1.5 hover:bg-[var(--bg-hover)]">
              <Folder size={16} className="text-[var(--accent-primary)]" />
              <input
                ref={inputRef}
                type="text"
                value={newFolderName}
                onChange={(e) => setNewFolderName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleCreateFolder();
                  if (e.key === 'Escape') { setIsCreatingFolder(false); setNewFolderName(''); }
                }}
                onBlur={handleCreateFolder}
                className="flex-1 h-6 px-2 text-xs rounded outline-none"
                style={{
                  background: 'var(--bg-input)',
                  border: '1px solid var(--accent-primary)',
                  color: 'var(--text-primary)',
                }}
                placeholder="New Folder"
              />
            </div>
          )}

          {/* New file input */}
          {isCreatingFile && (
            <div className="flex items-center gap-2 px-3 py-1.5 hover:bg-[var(--bg-hover)]">
              <FileText size={16} className="text-[var(--text-secondary)]" />
              <input
                ref={inputRef}
                type="text"
                value={newFileName}
                onChange={(e) => setNewFileName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleCreateFile();
                  if (e.key === 'Escape') { setIsCreatingFile(false); setNewFileName(''); }
                }}
                onBlur={handleCreateFile}
                className="flex-1 h-6 px-2 text-xs rounded outline-none"
                style={{
                  background: 'var(--bg-input)',
                  border: '1px solid var(--accent-primary)',
                  color: 'var(--text-primary)',
                }}
                placeholder="New File"
              />
            </div>
          )}

          {sortedChildren.map((node) => {
            const IconComp = getFileIcon(node.name, node.type);
            const isSelected = selectedId === node.id;
            const isRenaming = renameId === node.id;

            if (viewMode === 'grid') {
              return (
                <button
                  key={node.id}
                  onClick={() => setSelectedId(node.id)}
                  onDoubleClick={() => handleDoubleClick(node)}
                  className="inline-flex flex-col items-center gap-1 p-2 m-1 rounded-lg transition-colors w-20"
                  style={{
                    background: isSelected ? 'var(--bg-selected)' : 'transparent',
                  }}
                  onContextMenu={(e) => {
                    e.preventDefault();
                    setSelectedId(node.id);
                  }}
                >
                  <IconComp
                    size={32}
                    className={node.type === 'folder' ? 'text-[var(--accent-primary)]' : 'text-[var(--text-secondary)]'}
                  />
                  {isRenaming ? (
                    <input
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter') handleRename(); if (e.key === 'Escape') setRenameId(null); }}
                      onBlur={handleRename}
                      autoFocus
                      className="w-full text-[10px] px-1 rounded outline-none"
                      style={{ background: 'var(--bg-input)', border: '1px solid var(--accent-primary)', color: 'var(--text-primary)' }}
                    />
                  ) : (
                    <span className="text-[10px] text-[var(--text-primary)] text-center truncate max-w-[72px]">{node.name}</span>
                  )}
                </button>
              );
            }

            // List view
            return (
              <div
                key={node.id}
                onClick={() => setSelectedId(node.id)}
                onDoubleClick={() => handleDoubleClick(node)}
                className="flex items-center px-3 py-1.5 text-xs cursor-pointer transition-colors"
                style={{
                  background: isSelected ? 'var(--bg-selected)' : 'transparent',
                  borderBottom: '1px solid var(--border-subtle)',
                }}
                onContextMenu={(e) => {
                  e.preventDefault();
                  setSelectedId(node.id);
                }}
              >
                <IconComp
                  size={16}
                  className={`shrink-0 mr-2 ${node.type === 'folder' ? 'text-[var(--accent-primary)]' : 'text-[var(--text-secondary)]'}`}
                />
                {isRenaming ? (
                  <input
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') handleRename(); if (e.key === 'Escape') setRenameId(null); }}
                    onBlur={handleRename}
                    autoFocus
                    className="flex-1 h-6 px-2 text-xs rounded outline-none"
                    style={{ background: 'var(--bg-input)', border: '1px solid var(--accent-primary)', color: 'var(--text-primary)' }}
                    onClick={(e) => e.stopPropagation()}
                  />
                ) : (
                  <span className="flex-1 truncate text-[var(--text-primary)]">{node.name}</span>
                )}
                <span className="w-20 text-right text-[var(--text-secondary)] text-[10px]">
                  {node.type === 'file' ? `${node.size || 0} B` : '--'}
                </span>
                <span className="w-28 text-right text-[var(--text-disabled)] text-[10px]">
                  {new Date(node.modifiedAt).toLocaleDateString()}
                </span>
              </div>
            );
          })}

          {sortedChildren.length === 0 && !isCreatingFolder && !isCreatingFile && (
            <div className="flex flex-col items-center justify-center py-16 text-[var(--text-secondary)]">
              <Folder size={48} className="mb-3 opacity-20" />
              <p className="text-xs">Folder is empty</p>
            </div>
          )}
        </div>

        {/* Status bar */}
        <div
          className="flex items-center justify-between px-3 py-1 text-[10px] text-[var(--text-secondary)]"
          style={{ borderTop: '1px solid var(--border-subtle)' }}
        >
          <span>{sortedChildren.length} items</span>
          <span>{currentNode ? fs.getNodePath(currentNode.id) : ''}</span>
        </div>
      </div>
    </div>
  );
}

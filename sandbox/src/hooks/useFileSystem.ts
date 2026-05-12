// ============================================================
// Virtual File System — In-Memory with localStorage Persistence
// ============================================================

import { useState, useCallback, useEffect } from 'react';
import type { FileSystemNode, FileSystemState, FileAssociation } from '@/types';

const generateId = () => Math.random().toString(36).slice(2) + Date.now().toString(36);

// ---- Default File System Structure ----
const createDefaultFS = (): FileSystemState => {
  const rootId = generateId();
  const homeId = generateId();
  const userId = generateId();
  const desktopId = generateId();
  const documentsId = generateId();
  const downloadsId = generateId();
  const musicId = generateId();
  const picturesId = generateId();
  const videosId = generateId();
  const configId = generateId();
  const trashId = generateId();
  const trashFilesId = generateId();
  const trashInfoId = generateId();

  const nodes: Record<string, FileSystemNode> = {
    [rootId]: { id: rootId, name: '/', type: 'folder', parentId: null, createdAt: 0, modifiedAt: 0 },
    [homeId]: { id: homeId, name: 'home', type: 'folder', parentId: rootId, createdAt: 0, modifiedAt: 0 },
    [userId]: { id: userId, name: 'user', type: 'folder', parentId: homeId, createdAt: 0, modifiedAt: 0 },
    [desktopId]: { id: desktopId, name: 'Desktop', type: 'folder', parentId: userId, createdAt: 0, modifiedAt: 0 },
    [documentsId]: { id: documentsId, name: 'Documents', type: 'folder', parentId: userId, createdAt: 0, modifiedAt: 0 },
    [downloadsId]: { id: downloadsId, name: 'Downloads', type: 'folder', parentId: userId, createdAt: 0, modifiedAt: 0 },
    [musicId]: { id: musicId, name: 'Music', type: 'folder', parentId: userId, createdAt: 0, modifiedAt: 0 },
    [picturesId]: { id: picturesId, name: 'Pictures', type: 'folder', parentId: userId, createdAt: 0, modifiedAt: 0 },
    [videosId]: { id: videosId, name: 'Videos', type: 'folder', parentId: userId, createdAt: 0, modifiedAt: 0 },
    [configId]: { id: configId, name: '.config', type: 'folder', parentId: userId, createdAt: 0, modifiedAt: 0, isHidden: true },
    [trashId]: { id: trashId, name: '.trash', type: 'folder', parentId: userId, createdAt: 0, modifiedAt: 0, isHidden: true },
    [trashFilesId]: { id: trashFilesId, name: 'files', type: 'folder', parentId: trashId, createdAt: 0, modifiedAt: 0 },
    [trashInfoId]: { id: trashInfoId, name: 'info', type: 'folder', parentId: trashId, createdAt: 0, modifiedAt: 0 },
  };

  // Sample files
  const readmeId = generateId();
  nodes[readmeId] = {
    id: readmeId, name: 'welcome.txt', type: 'file', parentId: documentsId,
    createdAt: Date.now(), modifiedAt: Date.now(),
    content: 'Welcome to Dulus OS!\n\nThis is a web-based Linux desktop environment.\nExplore the apps and enjoy the experience.',
    size: 96,
  };

  const todoFileId = generateId();
  nodes[todoFileId] = {
    id: todoFileId, name: 'todo.txt', type: 'file', parentId: documentsId,
    createdAt: Date.now(), modifiedAt: Date.now(),
    content: '- [ ] Explore the desktop\n- [ ] Open some apps\n- [ ] Try the terminal',
    size: 60,
  };

  return { nodes, trashMetadata: {} };
};

export const initialFileSystem = createDefaultFS();

// ---- File Associations ----
export const FILE_ASSOCIATIONS: FileAssociation[] = [
  { extension: '.txt', appId: 'texteditor', icon: 'FileText', mimeType: 'text/plain' },
  { extension: '.md', appId: 'markdownpreview', icon: 'FileCode', mimeType: 'text/markdown' },
  { extension: '.json', appId: 'jsonformatter', icon: 'Braces', mimeType: 'application/json' },
  { extension: '.js', appId: 'codeeditor', icon: 'Code2', mimeType: 'text/javascript' },
  { extension: '.ts', appId: 'codeeditor', icon: 'Code2', mimeType: 'text/typescript' },
  { extension: '.html', appId: 'codeeditor', icon: 'Code2', mimeType: 'text/html' },
  { extension: '.css', appId: 'codeeditor', icon: 'Code2', mimeType: 'text/css' },
  { extension: '.py', appId: 'codeeditor', icon: 'Code2', mimeType: 'text/x-python' },
  { extension: '.jpg', appId: 'imageviewer', icon: 'Image', mimeType: 'image/jpeg' },
  { extension: '.png', appId: 'imageviewer', icon: 'Image', mimeType: 'image/png' },
  { extension: '.gif', appId: 'imageviewer', icon: 'Image', mimeType: 'image/gif' },
  { extension: '.mp3', appId: 'musicplayer', icon: 'Music', mimeType: 'audio/mpeg' },
  { extension: '.mp4', appId: 'videoplayer', icon: 'PlayCircle', mimeType: 'video/mp4' },
  { extension: '.pdf', appId: 'documentviewer', icon: 'File', mimeType: 'application/pdf' },
  { extension: '.zip', appId: 'archivemanager', icon: 'Package', mimeType: 'application/zip' },
  { extension: '.csv', appId: 'spreadsheet', icon: 'Table2', mimeType: 'text/csv' },
];

export const getFileAssociation = (filename: string): FileAssociation | undefined => {
  const ext = filename.slice(filename.lastIndexOf('.')).toLowerCase();
  return FILE_ASSOCIATIONS.find((a) => a.extension === ext);
};

const FS_STORAGE_KEY = 'dulus_filesystem';

function loadFS(): FileSystemState {
  try {
    const saved = localStorage.getItem(FS_STORAGE_KEY);
    if (saved) return JSON.parse(saved) as FileSystemState;
  } catch { /* ignore */ }
  return createDefaultFS();
}

function saveFS(state: FileSystemState) {
  try {
    localStorage.setItem(FS_STORAGE_KEY, JSON.stringify(state));
  } catch { /* ignore */ }
}

// ---- Hook ----
export function useFileSystem() {
  const [fs, setFs] = useState<FileSystemState>(loadFS);

  useEffect(() => {
    saveFS(fs);
  }, [fs]);

  const getChildren = useCallback(
    (parentId: string): FileSystemNode[] =>
      Object.values(fs.nodes).filter((n) => n.parentId === parentId),
    [fs.nodes]
  );

  const getNodeById = useCallback(
    (id: string): FileSystemNode | undefined => fs.nodes[id],
    [fs.nodes]
  );

  const getNodePath = useCallback(
    (id: string): string => {
      const parts: string[] = [];
      let current: FileSystemNode | undefined = fs.nodes[id];
      while (current) {
        parts.unshift(current.name);
        current = current.parentId ? fs.nodes[current.parentId] : undefined;
      }
      return parts.join('/') || '/';
    },
    [fs.nodes]
  );

  const createFile = useCallback(
    (parentId: string, name: string, content = '') => {
      const id = generateId();
      const node: FileSystemNode = {
        id, name, type: 'file', parentId,
        createdAt: Date.now(), modifiedAt: Date.now(),
        content, size: new Blob([content]).size,
      };
      setFs((prev) => ({
        ...prev,
        nodes: { ...prev.nodes, [id]: node },
      }));
      return id;
    },
    []
  );

  const createFolder = useCallback(
    (parentId: string, name: string) => {
      const id = generateId();
      const node: FileSystemNode = {
        id, name, type: 'folder', parentId,
        createdAt: Date.now(), modifiedAt: Date.now(),
      };
      setFs((prev) => ({
        ...prev,
        nodes: { ...prev.nodes, [id]: node },
      }));
      return id;
    },
    []
  );

  const deleteNode = useCallback((id: string) => {
    setFs((prev) => {
      const nodes = { ...prev.nodes };
      const trashMeta = { ...prev.trashMetadata };

      const recurseDelete = (nodeId: string) => {
        const node = nodes[nodeId];
        if (!node) return;
        if (node.type === 'folder') {
          Object.values(nodes)
            .filter((n) => n.parentId === nodeId)
            .forEach((n) => recurseDelete(n.id));
        }
        delete nodes[nodeId];
        delete trashMeta[nodeId];
      };

      recurseDelete(id);
      return { nodes, trashMetadata: trashMeta };
    });
  }, []);

  const moveToTrash = useCallback((id: string) => {
    setFs((prev) => {
      const nodes = { ...prev.nodes };
      const trashMeta = { ...prev.trashMetadata };
      const originalPath = (() => {
        const parts: string[] = [];
        let current: FileSystemNode | undefined = nodes[id];
        while (current) {
          parts.unshift(current.name);
          current = current.parentId ? nodes[current.parentId] : undefined;
        }
        return parts.join('/');
      })();

      trashMeta[id] = { originalPath, deletedAt: Date.now() };

      const recurseMove = (nodeId: string, newParentId: string) => {
        const node = nodes[nodeId];
        if (!node) return;
        nodes[nodeId] = { ...node, parentId: newParentId, modifiedAt: Date.now() };
        if (node.type === 'folder') {
          Object.values(nodes)
            .filter((n) => n.parentId === nodeId)
            .forEach((n) => recurseMove(n.id, nodeId));
        }
      };

      const trashFilesId = Object.values(nodes).find((n) => n.name === 'files' && n.parentId && nodes[n.parentId]?.name === '.trash')?.id;
      if (trashFilesId) {
        recurseMove(id, trashFilesId);
      }

      return { nodes, trashMetadata: trashMeta };
    });
  }, []);

  const renameNode = useCallback((id: string, newName: string) => {
    setFs((prev) => ({
      ...prev,
      nodes: {
        ...prev.nodes,
        [id]: { ...prev.nodes[id], name: newName, modifiedAt: Date.now() },
      },
    }));
  }, []);

  const moveNode = useCallback((id: string, newParentId: string) => {
    setFs((prev) => ({
      ...prev,
      nodes: {
        ...prev.nodes,
        [id]: { ...prev.nodes[id], parentId: newParentId, modifiedAt: Date.now() },
      },
    }));
  }, []);

  const readFile = useCallback(
    (id: string): string | undefined => {
      const node = fs.nodes[id];
      return node?.type === 'file' ? node.content : undefined;
    },
    [fs.nodes]
  );

  const writeFile = useCallback((id: string, content: string) => {
    setFs((prev) => {
      const node = prev.nodes[id];
      if (!node || node.type !== 'file') return prev;
      return {
        ...prev,
        nodes: {
          ...prev.nodes,
          [id]: { ...node, content, size: new Blob([content]).size, modifiedAt: Date.now() },
        },
      };
    });
  }, []);

  const emptyTrash = useCallback(() => {
    setFs((prev) => {
      const nodes = { ...prev.nodes };
      const trashMeta = { ...prev.trashMetadata };
      Object.keys(trashMeta).forEach((id) => {
        const recurseDelete = (nodeId: string) => {
          const node = nodes[nodeId];
          if (!node) return;
          if (node.type === 'folder') {
            Object.values(nodes)
              .filter((n) => n.parentId === nodeId)
              .forEach((n) => recurseDelete(n.id));
          }
          delete nodes[nodeId];
        };
        recurseDelete(id);
        delete trashMeta[id];
      });
      return { nodes, trashMetadata: trashMeta };
    });
  }, []);

  const getTrashItems = useCallback((): FileSystemNode[] => {
    return Object.keys(fs.trashMetadata)
      .map((id) => fs.nodes[id])
      .filter(Boolean);
  }, [fs]);

  const findNodeByPath = useCallback(
    (path: string): FileSystemNode | undefined => {
      if (path === '/') return Object.values(fs.nodes).find((n) => n.parentId === null);
      const parts = path.split('/').filter(Boolean);
      let current = Object.values(fs.nodes).find((n) => n.parentId === null);
      for (const part of parts) {
        const found = Object.values(fs.nodes).find((n) => n.parentId === current?.id && n.name === part);
        if (!found) return undefined;
        current = found;
      }
      return current;
    },
    [fs.nodes]
  );

  return {
    fs,
    getChildren,
    getNodeById,
    getNodePath,
    createFile,
    createFolder,
    deleteNode,
    moveToTrash,
    renameNode,
    moveNode,
    readFile,
    writeFile,
    emptyTrash,
    getTrashItems,
    findNodeByPath,
  };
}

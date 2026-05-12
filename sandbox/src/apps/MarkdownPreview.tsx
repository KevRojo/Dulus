// ============================================================
// Markdown Preview — Split-pane editor + live preview
// ============================================================

import { useState, useCallback, useMemo, useRef } from 'react';
import { useFileSystem } from '@/hooks/useFileSystem';
import {
  Bold, Italic, Heading, Link, Image, Code, Quote, List,
  ListOrdered, CheckSquare, Minus, Eye, FileCode, Copy, Save, Download, FileUp,
} from 'lucide-react';

function markdownToHtml(md: string): string {
  let html = md;

  // Escape HTML
  html = html.replace(/</g, '&lt;').replace(/>/g, '&gt;');

  // Code blocks
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, _lang: string, code) => {
    return `<pre style="background:#1A1A1A;padding:16px;border-radius:8px;overflow:auto;margin:12px 0"><code style="font-family:'JetBrains Mono',monospace;font-size:13px;color:var(--text-primary)">${code.trim()}</code></pre>`;
  });

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code style="background:rgba(124,77,255,0.1);padding:2px 6px;border-radius:4px;font-family:\'JetBrains Mono\',monospace;font-size:12px">$1</code>');

  // Headings
  html = html.replace(/^###### (.*$)/gim, '<h6 style="font-size:13px;font-weight:600;margin:12px 0">$1</h6>');
  html = html.replace(/^##### (.*$)/gim, '<h5 style="font-size:14px;font-weight:600;margin:12px 0">$1</h5>');
  html = html.replace(/^#### (.*$)/gim, '<h4 style="font-size:16px;font-weight:600;margin:14px 0">$1</h4>');
  html = html.replace(/^### (.*$)/gim, '<h3 style="font-size:20px;font-weight:600;margin:16px 0">$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h2 style="font-size:24px;font-weight:600;margin:20px 0;padding-bottom:8px;border-bottom:1px solid var(--border-default)">$1</h2>');
  html = html.replace(/^# (.*$)/gim, '<h1 style="font-size:32px;font-weight:700;margin:24px 0;padding-bottom:8px;border-bottom:2px solid var(--border-default)">$1</h1>');

  // Bold & Italic
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
  html = html.replace(/___(.+?)___/g, '<strong><em>$1</em></strong>');
  html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');
  html = html.replace(/_(.+?)_/g, '<em>$1</em>');

  // Strikethrough
  html = html.replace(/~~(.+?)~~/g, '<del>$1</del>');

  // Links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" style="color:var(--accent-primary);text-decoration:none" target="_blank" rel="noopener">$1</a>');

  // Images
  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width:100%;border-radius:8px;margin:12px 0" />');

  // Blockquotes
  html = html.replace(/^&gt; (.*$)/gim, '<blockquote style="border-left:4px solid var(--accent-primary);padding-left:16px;margin:12px 0;color:var(--text-secondary)">$1</blockquote>');

  // Horizontal rules
  html = html.replace(/^---+$/gim, '<hr style="border:none;border-top:1px solid var(--border-default);margin:24px 0" />');
  html = html.replace(/^\*\*\*+$/gim, '<hr style="border:none;border-top:1px solid var(--border-default);margin:24px 0" />');

  // Task lists
  html = html.replace(/^- \[x\] (.*$)/gim, '<div style="display:flex;align-items:center;gap:8px;margin:4px 0"><span style="color:var(--accent-success)">&#9745;</span><span>$1</span></div>');
  html = html.replace(/^- \[ \] (.*$)/gim, '<div style="display:flex;align-items:center;gap:8px;margin:4px 0"><span>&#9744;</span><span>$1</span></div>');

  // Ordered lists
  html = html.replace(/^(\d+\.\s.*(?:\n\d+\.\s.*)*)/gm, (block) => {
    const items = block.split('\n').map((line: string) =>
      `<li style="margin:4px 0">${line.replace(/^\d+\.\s/, '')}</li>`
    ).join('');
    return `<ol style="padding-left:24px;margin:12px 0">${items}</ol>`;
  });

  // Unordered lists
  html = html.replace(/^([-*]\s.*(?:\n[-*]\s.*)*)/gm, (block) => {
    const items = block.split('\n').map((line: string) =>
      `<li style="margin:4px 0">${line.replace(/^[-*]\s/, '')}</li>`
    ).join('');
    return `<ul style="padding-left:24px;margin:12px 0">${items}</ul>`;
  });

  // Tables
  html = html.replace(/\|(.+)\|\n\|[-:\|\s]+\|\n((?:\|.+\|\n?)+)/g, (_, header, rows) => {
    const headers = header.split('|').filter(Boolean).map((h: string) => `<th style="padding:8px 12px;background:var(--bg-titlebar);font-weight:600;font-size:13px;border:1px solid var(--border-default)">${h.trim()}</th>`).join('');
    const bodyRows = rows.trim().split('\n').map((row: string) => {
      const cells = row.split('|').filter(Boolean).map((c: string, i: number) =>
        `<td style="padding:8px 12px;border:1px solid var(--border-default);font-size:13px;background:${i % 2 === 0 ? 'transparent' : 'var(--bg-hover)'};color:var(--text-primary)">${c.trim()}</td>`
      ).join('');
      return `<tr>${cells}</tr>`;
    }).join('');
    return `<table style="border-collapse:collapse;margin:16px 0;width:100%;border:1px solid var(--border-default)"><thead><tr>${headers}</tr></thead><tbody>${bodyRows}</tbody></table>`;
  });

  // Paragraphs (remaining lines)
  html = html.replace(/^(?!<[a-z])(.+)$/gim, '<p style="line-height:1.6;margin:12px 0;color:var(--text-primary)">$1</p>');

  // Fix multiple breaks
  html = html.replace(/\n+/g, '\n');

  return html;
}

const DEFAULT_MD = `# Welcome to Markdown Preview

This is a **live** markdown editor with *GitHub-flavored* rendering.

## Features

- **Bold** and *italic* text
- ~~Strikethrough~~ text
- Code blocks and inline \`code\`
- Links, images, tables
- Task lists
- Blockquotes

## Code Example

\`\`\`javascript
function greet(name) {
  return \`Hello, \${name}!\`;
}
\`\`\`

## Table

| Feature | Status |
|---------|--------|
| Editor  | Done   |
| Preview | Done   |
| Export  | Done   |

## Task List

- [x] Write markdown
- [x] See preview
- [ ] Share with team

> "Markdown is a lightweight markup language."

---

Enjoy writing!
`;

export default function MarkdownPreview() {
  const fs = useFileSystem();
  const [content, setContent] = useState(DEFAULT_MD);
  const [syncScroll, setSyncScroll] = useState(true);
  const [copied, setCopied] = useState(false);
  const editorRef = useRef<HTMLTextAreaElement>(null);
  const previewRef = useRef<HTMLDivElement>(null);
  const isScrolling = useRef(false);

  const html = useMemo(() => markdownToHtml(content), [content]);

  const handleScroll = useCallback((source: 'editor' | 'preview') => {
    if (!syncScroll || isScrolling.current) return;
    isScrolling.current = true;

    const editor = editorRef.current;
    const preview = previewRef.current;
    if (!editor || !preview) return;

    if (source === 'editor') {
      const ratio = editor.scrollTop / (editor.scrollHeight - editor.clientHeight);
      preview.scrollTop = ratio * (preview.scrollHeight - preview.clientHeight);
    } else {
      const ratio = preview.scrollTop / (preview.scrollHeight - preview.clientHeight);
      editor.scrollTop = ratio * (editor.scrollHeight - editor.clientHeight);
    }

    setTimeout(() => { isScrolling.current = false; }, 50);
  }, [syncScroll]);

  const insertMarkdown = useCallback((before: string, after: string = '') => {
    const ta = editorRef.current;
    if (!ta) return;
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const selected = ta.value.substring(start, end);
    const replacement = before + selected + after;
    ta.value = ta.value.substring(0, start) + replacement + ta.value.substring(end);
    ta.selectionStart = start + before.length;
    ta.selectionEnd = start + before.length + selected.length;
    setContent(ta.value);
    ta.focus();
  }, []);

  const exportHtml = useCallback(() => {
    const fullHtml = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>Export</title><style>body{font-family:sans-serif;max-width:800px;margin:40px auto;padding:20px;color:#333}</style></head><body>${html}</body></html>`;
    const blob = new Blob([fullHtml], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'export.html';
    a.click();
    URL.revokeObjectURL(url);
  }, [html]);

  const copyHtml = useCallback(async () => {
    await navigator.clipboard.writeText(html);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }, [html]);

  const saveToFS = useCallback(() => {
    const docs = Object.values(fs.fs.nodes).find(
      (n) => n.name === 'Documents' && n.parentId
    );
    if (docs) {
      fs.createFile(docs.id, 'document.md', content);
    }
  }, [fs, content]);

  const loadFromFS = useCallback(() => {
    const docs = Object.values(fs.fs.nodes).find(
      (n) => n.name === 'Documents' && n.parentId
    );
    if (!docs) return;
    const files = fs.getChildren(docs.id).filter((n) => n.type === 'file' && n.name.endsWith('.md'));
    if (files.length > 0) {
      const c = fs.readFile(files[0].id) || '';
      setContent(c);
    }
  }, [fs]);

  return (
    <div className="h-full flex flex-col" style={{ background: 'var(--bg-window)' }}>
      {/* Toolbar */}
      <div className="flex items-center gap-1 px-2 py-1.5 shrink-0" style={{ background: 'var(--bg-titlebar)', borderBottom: '1px solid var(--border-subtle)' }}>
        <button onClick={() => insertMarkdown('**', '**')} className="p-1.5 rounded hover:bg-[var(--bg-hover)]" title="Bold"><Bold size={14} /></button>
        <button onClick={() => insertMarkdown('*', '*')} className="p-1.5 rounded hover:bg-[var(--bg-hover)]" title="Italic"><Italic size={14} /></button>
        <button onClick={() => insertMarkdown('### ', '')} className="p-1.5 rounded hover:bg-[var(--bg-hover)]" title="Heading"><Heading size={14} /></button>
        <button onClick={() => insertMarkdown('[', '](url)')} className="p-1.5 rounded hover:bg-[var(--bg-hover)]" title="Link"><Link size={14} /></button>
        <button onClick={() => insertMarkdown('![alt](', ')')} className="p-1.5 rounded hover:bg-[var(--bg-hover)]" title="Image"><Image size={14} /></button>
        <button onClick={() => insertMarkdown('`', '`')} className="p-1.5 rounded hover:bg-[var(--bg-hover)]" title="Code"><Code size={14} /></button>
        <button onClick={() => insertMarkdown('> ', '')} className="p-1.5 rounded hover:bg-[var(--bg-hover)]" title="Quote"><Quote size={14} /></button>
        <button onClick={() => insertMarkdown('- ', '')} className="p-1.5 rounded hover:bg-[var(--bg-hover)]" title="List"><List size={14} /></button>
        <button onClick={() => insertMarkdown('1. ', '')} className="p-1.5 rounded hover:bg-[var(--bg-hover)]" title="Ordered List"><ListOrdered size={14} /></button>
        <button onClick={() => insertMarkdown('- [ ] ', '')} className="p-1.5 rounded hover:bg-[var(--bg-hover)]" title="Task List"><CheckSquare size={14} /></button>
        <button onClick={() => insertMarkdown('\n---\n', '')} className="p-1.5 rounded hover:bg-[var(--bg-hover)]" title="Horizontal Rule"><Minus size={14} /></button>
        <div className="w-px h-5 mx-1" style={{ background: 'var(--border-subtle)' }} />
        <button onClick={() => setSyncScroll((v) => !v)} className="flex items-center gap-1 px-2 py-1 rounded text-xs hover:bg-[var(--bg-hover)] transition-colors" style={{ color: syncScroll ? 'var(--accent-primary)' : 'var(--text-secondary)' }}>
          <Eye size={12} /> Sync
        </button>
        <button onClick={copyHtml} className="flex items-center gap-1 px-2 py-1 rounded text-xs hover:bg-[var(--bg-hover)]">
          <Copy size={12} /> {copied ? 'Copied!' : 'Copy HTML'}
        </button>
        <button onClick={exportHtml} className="flex items-center gap-1 px-2 py-1 rounded text-xs hover:bg-[var(--bg-hover)]">
          <Download size={12} /> Export HTML
        </button>
        <div className="ml-auto flex items-center gap-1">
          <button onClick={loadFromFS} className="flex items-center gap-1 px-2 py-1 rounded text-xs hover:bg-[var(--bg-hover)]">
            <FileUp size={12} /> Load
          </button>
          <button onClick={saveToFS} className="flex items-center gap-1 px-2 py-1 rounded text-xs hover:bg-[var(--bg-hover)]">
            <Save size={12} /> Save
          </button>
        </div>
      </div>

      {/* Split pane */}
      <div className="flex-1 flex overflow-hidden">
        {/* Editor */}
        <div className="flex-1 flex flex-col overflow-hidden" style={{ borderRight: '1px solid var(--border-subtle)' }}>
          <div className="px-2 py-0.5 text-xs font-medium shrink-0" style={{ background: 'var(--bg-titlebar)', color: 'var(--text-secondary)' }}>
            <FileCode size={12} className="inline mr-1" /> Editor
          </div>
          <textarea
            ref={editorRef}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onScroll={() => handleScroll('editor')}
            spellCheck={false}
            className="flex-1 w-full resize-none outline-none p-4 custom-scrollbar"
            style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', fontFamily: "'JetBrains Mono', monospace", fontSize: 13, lineHeight: '20px' }}
          />
        </div>

        {/* Preview */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="px-2 py-0.5 text-xs font-medium shrink-0" style={{ background: 'var(--bg-titlebar)', color: 'var(--text-secondary)' }}>
            <Eye size={12} className="inline mr-1" /> Preview
          </div>
          <div
            ref={previewRef}
            onScroll={() => handleScroll('preview')}
            className="flex-1 overflow-auto p-6 custom-scrollbar"
            style={{ background: 'var(--bg-window)' }}
          >
            <div dangerouslySetInnerHTML={{ __html: html }} />
          </div>
        </div>
      </div>
    </div>
  );
}

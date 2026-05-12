// ============================================================
// Web Browser — Tabbed browser with bookmarks and homepage
// ============================================================

import { useState, useRef, useEffect, useCallback, memo } from 'react';
import {
  ArrowLeft, ArrowRight, RefreshCw, Home, Star, Plus, X, Lock, Search,
  Globe, Youtube, Github, Twitter, Linkedin, ShoppingBag, Newspaper, Code
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

// ---- Types ----
interface Tab {
  id: string;
  url: string;
  title: string;
  history: string[];
  historyIndex: number;
  loading: boolean;
}

interface Bookmark {
  url: string;
  title: string;
}

// ---- Quick Links ----
const QUICK_LINKS: { icon: LucideIcon; name: string; url: string; color: string }[] = [
  { icon: Search, name: 'Google', url: 'https://google.com', color: '#4285F4' },
  { icon: Youtube, name: 'YouTube', url: 'https://youtube.com', color: '#FF0000' },
  { icon: Github, name: 'GitHub', url: 'https://github.com', color: '#333' },
  { icon: Twitter, name: 'Twitter', url: 'https://twitter.com', color: '#1DA1F2' },
  { icon: Linkedin, name: 'LinkedIn', url: 'https://linkedin.com', color: '#0A66C2' },
  { icon: ShoppingBag, name: 'Amazon', url: 'https://amazon.com', color: '#FF9900' },
  { icon: Code, name: 'Stack Overflow', url: 'https://stackoverflow.com', color: '#F48024' },
  { icon: Newspaper, name: 'Reddit', url: 'https://reddit.com', color: '#FF4500' },
];

// ---- News articles for homepage ----
const NEWS_ARTICLES = [
  { title: 'Ubuntu 24.04 LTS Released with New Features', source: 'ubuntu.com', time: '2h ago' },
  { title: 'React 19 Introduces New Compiler for Performance', source: 'react.dev', time: '4h ago' },
  { title: 'TypeScript 5.5 Brings Improved Type Inference', source: 'dev.to', time: '6h ago' },
  { title: 'WebAssembly Now Supported in All Major Browsers', source: 'webassembly.org', time: '8h ago' },
];

// ---- Simulated pages ----
const IFRAME_FRIENDLY_SITES = ['example.com', 'wikipedia.org', 'ubuntu.com'];

const generateSimulatedPage = (url: string): string => {
  const host = url.replace(/^https?:\/\//, '').split('/')[0];
  return `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          background: #f5f5f5;
          padding: 40px;
          color: #333;
        }
        .header {
          background: linear-gradient(135deg, #7C4DFF, #FF9800);
          color: white;
          padding: 40px;
          border-radius: 12px;
          margin-bottom: 30px;
        }
        .header h1 { font-size: 32px; margin-bottom: 8px; }
        .header p { font-size: 16px; opacity: 0.9; }
        .content {
          background: white;
          padding: 30px;
          border-radius: 12px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .content h2 { color: #7C4DFF; margin-bottom: 16px; }
        .content p { line-height: 1.7; margin-bottom: 12px; }
        .links { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; margin-top: 20px; }
        .link-item {
          background: #f8f8f8;
          padding: 16px;
          border-radius: 8px;
          text-decoration: none;
          color: #333;
          transition: transform 0.2s, box-shadow 0.2s;
        }
        .link-item:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
      </style>
    </head>
    <body>
      <div class="header">
        <h1>${host}</h1>
        <p>Simulated page for Dulus OS Browser</p>
      </div>
      <div class="content">
        <h2>Welcome to ${host}</h2>
        <p>This is a simulated version of the website running inside Dulus OS Browser. Many real websites block iframe embedding for security reasons.</p>
        <p>In a real environment, this page would load the actual website content. For this demo, you're seeing a placeholder with the structure of the requested site.</p>
        <div class="links">
          <a href="#" class="link-item">Home</a>
          <a href="#" class="link-item">About</a>
          <a href="#" class="link-item">Services</a>
          <a href="#" class="link-item">Contact</a>
        </div>
      </div>
    </body>
    </html>
  `;
};

// ---- Helpers ----
const generateId = () => Math.random().toString(36).slice(2);

const normalizeUrl = (input: string): string => {
  const trimmed = input.trim();
  if (trimmed === '') return '';
  if (trimmed === 'home') return 'home';
  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) return trimmed;
  if (trimmed.includes(' ') || (!trimmed.includes('.') && !trimmed.startsWith('localhost'))) {
    return `search://${trimmed}`;
  }
  return `https://${trimmed}`;
};

// ---- Homepage Component ----
const Homepage = memo(function Homepage({ onNavigate }: { onNavigate: (url: string) => void }) {
  const [searchQuery, setSearchQuery] = useState('');

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) onNavigate(`search://${searchQuery.trim()}`);
  };

  return (
    <div className="h-full flex flex-col items-center justify-start pt-12 custom-scrollbar overflow-auto" style={{ background: 'var(--bg-window)' }}>
      <div className="flex items-center gap-3 mb-8">
        <Globe size={36} style={{ color: 'var(--accent-primary)' }} />
        <h1 style={{ fontSize: '28px', fontWeight: 700, color: 'var(--text-primary)' }}>Dulus OS Browser</h1>
      </div>

      <form onSubmit={handleSearch} className="w-full flex justify-center px-4 mb-10">
        <div
          className="flex items-center gap-2 px-4"
          style={{
            width: '480px', height: '44px', borderRadius: '22px',
            background: 'var(--bg-input)', border: '1px solid var(--border-default)',
          }}
        >
          <Search size={18} style={{ color: 'var(--text-disabled)', flexShrink: 0 }} />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search or enter address"
            className="flex-1 bg-transparent outline-none"
            style={{ color: 'var(--text-primary)', fontSize: '14px' }}
          />
        </div>
      </form>

      <div className="grid grid-cols-4 gap-4 mb-10" style={{ maxWidth: '400px' }}>
        {QUICK_LINKS.map((link) => (
          <button
            key={link.name}
            onClick={() => onNavigate(link.url)}
            className="flex flex-col items-center gap-2 p-3 rounded-xl transition-all hover:scale-105"
            style={{ background: 'var(--bg-hover)' }}
          >
            <div
              className="flex items-center justify-center"
              style={{ width: 48, height: 48, borderRadius: 12, background: link.color + '20' }}
            >
              <link.icon size={24} style={{ color: link.color }} />
            </div>
            <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{link.name}</span>
          </button>
        ))}
      </div>

      <div style={{ width: '100%', maxWidth: '640px', padding: '0 24px' }}>
        <h2 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '12px' }}>Top Stories</h2>
        <div className="grid grid-cols-1 gap-3">
          {NEWS_ARTICLES.map((article, i) => (
            <div
              key={i}
              className="flex items-start gap-3 p-3 rounded-lg cursor-pointer transition-all"
              style={{ background: 'var(--bg-titlebar)', border: '1px solid var(--border-subtle)' }}
              onClick={() => onNavigate(`https://${article.source}`)}
            >
              <div className="flex-1">
                <h3 style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)' }}>{article.title}</h3>
                <div className="flex items-center gap-2 mt-1">
                  <span style={{ fontSize: '11px', color: 'var(--text-disabled)' }}>{article.source}</span>
                  <span style={{ fontSize: '11px', color: 'var(--text-disabled)' }}>{article.time}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
});

// ---- Search Results Page ----
const SearchResults = memo(function SearchResults({ query, onNavigate }: { query: string; onNavigate: (url: string) => void }) {
  const results = [
    { title: `${query} - Search Results`, url: `https://google.com/search?q=${encodeURIComponent(query)}`, desc: `Find information about ${query} on the web.` },
    { title: `${query} - Wikipedia`, url: `https://wikipedia.org/wiki/${encodeURIComponent(query)}`, desc: `Read about ${query} on Wikipedia, the free encyclopedia.` },
    { title: `${query} tutorials and guides`, url: 'https://stackoverflow.com', desc: `Learn about ${query} with tutorials, examples, and documentation.` },
    { title: `${query} news and updates`, url: 'https://news.ycombinator.com', desc: `Latest news and discussions about ${query}.` },
  ];

  return (
    <div className="h-full p-6 custom-scrollbar overflow-auto" style={{ background: '#f5f5f5' }}>
      <h1 style={{ fontSize: '20px', fontWeight: 600, color: '#333', marginBottom: '16px' }}>
        Search results for "{query}"
      </h1>
      <div className="flex flex-col gap-4" style={{ maxWidth: '680px' }}>
        {results.map((r, i) => (
          <div key={i} className="p-4 rounded-lg bg-white" style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
            <button
              onClick={() => onNavigate(r.url)}
              className="text-left block"
            >
              <h3 style={{ fontSize: '15px', fontWeight: 500, color: '#1a0dab', marginBottom: '4px' }}>{r.title}</h3>
              <p style={{ fontSize: '12px', color: '#006621', marginBottom: '4px' }}>{r.url}</p>
              <p style={{ fontSize: '13px', color: '#545454' }}>{r.desc}</p>
            </button>
          </div>
        ))}
      </div>
    </div>
  );
});

// ---- Error Page ----
// ---- Main Browser Component ----
export default function Browser() {
  const [tabs, setTabs] = useState<Tab[]>([
    { id: generateId(), url: 'home', title: 'New Tab', history: ['home'], historyIndex: 0, loading: false },
  ]);
  const [activeTabId, setActiveTabId] = useState(tabs[0].id);
  const [bookmarks, setBookmarks] = useState<Bookmark[]>(() => {
    try {
      const saved = localStorage.getItem('dulus_browser_bookmarks');
      return saved ? JSON.parse(saved) : [];
    } catch { return []; }
  });
  const [addressBarValue, setAddressBarValue] = useState('');
  const showBookmarks = true;
  const iframeRef = useRef<HTMLIFrameElement>(null);

  const activeTab = tabs.find((t) => t.id === activeTabId) || tabs[0];

  useEffect(() => {
    localStorage.setItem('dulus_browser_bookmarks', JSON.stringify(bookmarks));
  }, [bookmarks]);

  const updateActiveTab = useCallback((updates: Partial<Tab>) => {
    setTabs((prev) => prev.map((t) => (t.id === activeTabId ? { ...t, ...updates } : t)));
  }, [activeTabId]);

  const navigateTo = useCallback((url: string) => {
    const normalized = normalizeUrl(url);
    if (!normalized) return;

    updateActiveTab({ loading: true });

    setTimeout(() => {
      setTabs((prev) =>
        prev.map((t) => {
          if (t.id !== activeTabId) return t;
          const newHistory = t.history.slice(0, t.historyIndex + 1);
          if (newHistory[newHistory.length - 1] !== normalized) {
            newHistory.push(normalized);
          }
          const title = normalized === 'home' ? 'New Tab' : normalized.replace(/^https?:\/\//, '').split('/')[0];
          return { ...t, url: normalized, title, history: newHistory, historyIndex: newHistory.length - 1, loading: false };
        })
      );
      setAddressBarValue(normalized === 'home' ? '' : normalized);
    }, 300);
  }, [activeTabId, updateActiveTab]);

  const addTab = useCallback(() => {
    const newTab: Tab = { id: generateId(), url: 'home', title: 'New Tab', history: ['home'], historyIndex: 0, loading: false };
    setTabs((prev) => [...prev, newTab]);
    setActiveTabId(newTab.id);
    setAddressBarValue('');
  }, []);

  const closeTab = useCallback((tabId: string) => {
    setTabs((prev) => {
      if (prev.length === 1) {
        return [{ id: generateId(), url: 'home', title: 'New Tab', history: ['home'], historyIndex: 0, loading: false }];
      }
      const filtered = prev.filter((t) => t.id !== tabId);
      if (activeTabId === tabId) {
        const idx = prev.findIndex((t) => t.id === tabId);
        const newActive = prev[idx - 1] || prev[idx + 1];
        if (newActive) setActiveTabId(newActive.id);
      }
      return filtered;
    });
  }, [activeTabId]);

  const goBack = useCallback(() => {
    setTabs((prev) =>
      prev.map((t) => {
        if (t.id !== activeTabId || t.historyIndex <= 0) return t;
        const newIndex = t.historyIndex - 1;
        const url = t.history[newIndex];
        return { ...t, url, historyIndex: newIndex };
      })
    );
  }, [activeTabId]);

  const goForward = useCallback(() => {
    setTabs((prev) =>
      prev.map((t) => {
        if (t.id !== activeTabId || t.historyIndex >= t.history.length - 1) return t;
        const newIndex = t.historyIndex + 1;
        const url = t.history[newIndex];
        return { ...t, url, historyIndex: newIndex };
      })
    );
  }, [activeTabId]);

  const refresh = useCallback(() => {
    const tab = tabs.find((t) => t.id === activeTabId);
    if (tab) navigateTo(tab.url);
  }, [activeTabId, tabs, navigateTo]);

  const toggleBookmark = useCallback(() => {
    if (activeTab.url === 'home' || activeTab.url.startsWith('search://')) return;
    setBookmarks((prev) => {
      const exists = prev.find((b) => b.url === activeTab.url);
      if (exists) return prev.filter((b) => b.url !== activeTab.url);
      return [...prev, { url: activeTab.url, title: activeTab.title }];
    });
  }, [activeTab]);

  const isBookmarked = bookmarks.some((b) => b.url === activeTab.url);
  const canGoBack = activeTab.historyIndex > 0;
  const canGoForward = activeTab.historyIndex < activeTab.history.length - 1;

  const handleAddressSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    navigateTo(addressBarValue);
  };

  // Render content based on URL
  const renderContent = () => {
    if (activeTab.loading) {
      return (
        <div className="h-full flex items-center justify-center" style={{ background: 'var(--bg-window)' }}>
          <div className="flex flex-col items-center gap-3">
            <div
              className="w-8 h-1 rounded-full overflow-hidden"
              style={{ background: 'var(--border-subtle)', width: '200px' }}
            >
              <div
                className="h-full rounded-full"
                style={{
                  background: 'linear-gradient(90deg, var(--accent-primary), var(--accent-primary-hover))',
                  backgroundSize: '200% 100%',
                  animation: 'shimmer 1.5s infinite',
                  width: '100%',
                }}
              />
            </div>
            <span style={{ fontSize: '12px', color: 'var(--text-disabled)' }}>Loading...</span>
          </div>
        </div>
      );
    }

    if (activeTab.url === 'home') {
      return <Homepage onNavigate={navigateTo} />;
    }

    if (activeTab.url.startsWith('search://')) {
      return <SearchResults query={activeTab.url.replace('search://', '')} onNavigate={navigateTo} />;
    }

    // For real URLs, show iframe or error
    const host = activeTab.url.replace(/^https?:\/\//, '').split('/')[0];
    const isIframeFriendly = IFRAME_FRIENDLY_SITES.some((s) => host.includes(s));

    if (isIframeFriendly) {
      return (
        <iframe
          ref={iframeRef}
          src={activeTab.url}
          className="w-full h-full border-0"
          sandbox="allow-scripts allow-same-origin allow-forms"
          title={activeTab.title}
        />
      );
    }

    // Show simulated page
    return (
      <iframe
        ref={iframeRef}
        srcDoc={generateSimulatedPage(activeTab.url)}
        className="w-full h-full border-0"
        title={activeTab.title}
      />
    );
  };

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-window)' }}>
      {/* Address Bar */}
      <div
        className="flex items-center gap-2 px-3 shrink-0"
        style={{
          height: 44,
          background: 'var(--bg-titlebar)',
          borderBottom: '1px solid var(--border-subtle)',
        }}
      >
        <button
          onClick={goBack}
          disabled={!canGoBack}
          className="flex items-center justify-center rounded-lg transition-all"
          style={{ width: 32, height: 32, opacity: canGoBack ? 1 : 0.3 }}
        >
          <ArrowLeft size={16} style={{ color: 'var(--text-primary)' }} />
        </button>
        <button
          onClick={goForward}
          disabled={!canGoForward}
          className="flex items-center justify-center rounded-lg transition-all"
          style={{ width: 32, height: 32, opacity: canGoForward ? 1 : 0.3 }}
        >
          <ArrowRight size={16} style={{ color: 'var(--text-primary)' }} />
        </button>
        <button
          onClick={refresh}
          className="flex items-center justify-center rounded-lg transition-all"
          style={{ width: 32, height: 32 }}
        >
          <RefreshCw size={16} style={{ color: 'var(--text-primary)' }} />
        </button>
        <button
          onClick={() => navigateTo('home')}
          className="flex items-center justify-center rounded-lg transition-all"
          style={{ width: 32, height: 32 }}
        >
          <Home size={16} style={{ color: 'var(--text-primary)' }} />
        </button>

        <form onSubmit={handleAddressSubmit} className="flex-1 flex items-center">
          <div
            className="flex items-center gap-2 px-3 flex-1"
            style={{
              height: 32,
              borderRadius: 16,
              background: 'var(--bg-input)',
              border: '1px solid var(--border-default)',
            }}
          >
            <Lock size={14} style={{ color: 'var(--accent-success)', flexShrink: 0 }} />
            <input
              type="text"
              value={addressBarValue}
              onChange={(e) => setAddressBarValue(e.target.value)}
              onFocus={() => setAddressBarValue(activeTab.url === 'home' ? '' : activeTab.url)}
              className="flex-1 bg-transparent outline-none"
              style={{ color: 'var(--text-primary)', fontSize: '13px' }}
            />
          </div>
        </form>

        <button
          onClick={toggleBookmark}
          className="flex items-center justify-center rounded-lg transition-all"
          style={{ width: 32, height: 32 }}
        >
          <Star
            size={16}
            style={{ color: isBookmarked ? 'var(--accent-secondary)' : 'var(--text-secondary)' }}
            fill={isBookmarked ? 'var(--accent-secondary)' : 'none'}
          />
        </button>
      </div>

      {/* Bookmark bar */}
      {showBookmarks && bookmarks.length > 0 && (
        <div
          className="flex items-center gap-1 px-3 shrink-0 overflow-hidden"
          style={{
            height: 32,
            background: 'var(--bg-titlebar)',
            borderBottom: '1px solid var(--border-subtle)',
          }}
        >
          {bookmarks.map((bm) => (
            <button
              key={bm.url}
              onClick={() => navigateTo(bm.url)}
              className="flex items-center gap-1.5 px-2 py-1 rounded transition-all hover:bg-[var(--bg-hover)]"
              style={{ maxWidth: 140 }}
            >
              <Star size={12} style={{ color: 'var(--accent-secondary)', flexShrink: 0 }} fill="var(--accent-secondary)" />
              <span className="truncate" style={{ fontSize: '11px', color: 'var(--text-primary)' }}>{bm.title}</span>
            </button>
          ))}
        </div>
      )}

      {/* Tab Bar */}
      <div
        className="flex items-center gap-1 px-2 shrink-0 overflow-x-auto"
        style={{
          height: 36,
          background: 'var(--bg-titlebar)',
          borderBottom: '1px solid var(--border-subtle)',
        }}
      >
        {tabs.map((tab) => (
          <div
            key={tab.id}
            onClick={() => { setActiveTabId(tab.id); setAddressBarValue(tab.url === 'home' ? '' : tab.url); }}
            className="flex items-center gap-2 px-3 py-1.5 rounded-t-lg cursor-pointer transition-all shrink-0 relative"
            style={{
              maxWidth: 180,
              minWidth: 100,
              background: tab.id === activeTabId ? 'var(--bg-window)' : 'transparent',
              borderTop: tab.id === activeTabId ? '2px solid var(--accent-primary)' : '2px solid transparent',
            }}
          >
            <Globe size={14} style={{ color: 'var(--text-secondary)', flexShrink: 0 }} />
            <span className="truncate flex-1" style={{ fontSize: '11px', color: 'var(--text-primary)' }}>
              {tab.title}
            </span>
            <button
              onClick={(e) => { e.stopPropagation(); closeTab(tab.id); }}
              className="flex items-center justify-center rounded-full transition-all hover:bg-[var(--bg-hover)]"
              style={{ width: 16, height: 16, flexShrink: 0 }}
            >
              <X size={12} style={{ color: 'var(--text-secondary)' }} />
            </button>
          </div>
        ))}
        <button
          onClick={addTab}
          className="flex items-center justify-center rounded-lg transition-all hover:bg-[var(--bg-hover)] ml-1"
          style={{ width: 28, height: 28, flexShrink: 0 }}
        >
          <Plus size={16} style={{ color: 'var(--text-secondary)' }} />
        </button>
      </div>

      {/* Viewport */}
      <div className="flex-1 overflow-hidden">
        {renderContent()}
      </div>
    </div>
  );
}

import { useState, useEffect, useMemo } from 'react';
import {
  Rss, RefreshCw, Check, CheckCheck, Plus, X, ChevronLeft,
  ExternalLink, Clock, Globe
} from 'lucide-react';

interface Article {
  id: string;
  title: string;
  snippet: string;
  content: string;
  date: string;
  read: boolean;
  feedId: string;
}

interface Feed {
  id: string;
  name: string;
  url: string;
  icon: string;
  articles: Article[];
}

const STORAGE_KEY = 'dulus_rss_read';

const MOCK_FEEDS: Feed[] = [
  {
    id: 'tc', name: 'TechCrunch', url: 'https://techcrunch.com/feed/', icon: 'TC',
    articles: Array.from({ length: 10 }, (_, i) => ({
      id: `tc-${i}`, title: ['AI Startup Raises $500M for Foundation Models', 'New Smartphone Features Revolutionary Camera', 'Cloud Computing Market Grows 35%', 'Fintech Disruption in Emerging Markets', 'Cybersecurity Threats Rise in 2025', 'SpaceX Launches New Satellite Constellation', 'Electric Vehicle Sales Hit Record High', 'Meta Unveils New VR Headset', 'Quantum Computing Breakthrough Announced', 'Robotics Startup Acquired for $2B'][i],
      snippet: ['A leading AI startup has secured $500 million in Series C funding to develop next-generation foundation models.', 'The latest flagship smartphone features a 200MP sensor and AI-powered computational photography.', 'Enterprise cloud spending continues to accelerate as companies migrate legacy infrastructure.', 'Mobile payment adoption is transforming financial services across developing economies.', 'Ransomware attacks have increased 40% year-over-year, prompting new defensive measures.', 'The new constellation will provide global internet coverage to remote regions.', 'EVs now represent 25% of all new car sales globally, up from 15% last year.', 'The Quest Pro 2 features improved resolution, field of view, and mixed reality capabilities.', 'Researchers have achieved a new milestone in quantum error correction.', 'The acquisition signals strong investor confidence in the robotics sector.'][i],
      content: ['Full article about the AI funding round and what it means for the industry.', 'Detailed review of the new smartphone camera system and sample photos.', 'Analysis of cloud market trends and vendor market share.', 'Deep dive into fintech innovations and regulatory challenges.', 'Report on the latest cybersecurity threats and mitigation strategies.', 'Coverage of the launch and its implications for global connectivity.', 'Market analysis of the electric vehicle industry and future projections.', 'Hands-on review of the new VR headset and its features.', 'Explanation of the quantum computing breakthrough and its significance.', 'Details of the robotics acquisition and strategic rationale.'][i],
      date: new Date(Date.now() - i * 3600000 * 3).toISOString(), read: false, feedId: 'tc',
    })),
  },
  {
    id: 'bbc', name: 'BBC News', url: 'https://feeds.bbci.co.uk/news/rss.xml', icon: 'BBC',
    articles: Array.from({ length: 10 }, (_, i) => ({
      id: `bbc-${i}`, title: ['Global Climate Summit Reaches Historic Agreement', 'New COVID Variant Monitoring System Launched', 'Olympics 2028 Host City Preparations Begin', 'Archaeological Discovery Rewrites Ancient History', 'Space Mission Returns with Asteroid Samples', 'Economic Recovery Accelerates Across Europe', 'Breakthrough in Cancer Research Announced', 'Renewable Energy Surpasses Coal Output', 'International Trade Deal Signed', 'Cultural Festival Celebrates Diversity'][i],
      snippet: ['Nations agree on binding emissions targets at the summit in Geneva.', 'Health authorities deploy enhanced genomic sequencing to track variants.', 'Los Angeles begins infrastructure upgrades ahead of the summer games.', 'Excavations in Turkey reveal a lost civilization dating back 5,000 years.', 'The samples contain organic compounds that could reveal origins of life.', 'GDP growth exceeds expectations in the eurozone for the third quarter.', 'A new immunotherapy treatment shows promising results in clinical trials.', 'Wind and solar power now generate more electricity than coal globally.', 'The bilateral agreement eliminates tariffs on key agricultural products.', 'The festival features artists from over 50 countries.'][i],
      content: ['Full coverage of the climate agreement and reaction from world leaders.', 'Details on the new monitoring system and its capabilities.', 'Preview of the planned venues and new sports to be included.', 'Analysis of the archaeological findings and their implications.', 'Scientific analysis of the asteroid samples and what they reveal.', 'Economic data and expert commentary on the recovery.', 'Medical details of the cancer treatment breakthrough.', 'Energy statistics and future projections for renewables.', 'Terms of the trade deal and expected economic impact.', 'Highlights from the cultural festival celebrations.'][i],
      date: new Date(Date.now() - i * 3600000 * 5).toISOString(), read: false, feedId: 'bbc',
    })),
  },
  {
    id: 'hn', name: 'Hacker News', url: 'https://news.ycombinator.com/rss', icon: 'HN',
    articles: Array.from({ length: 10 }, (_, i) => ({
      id: `hn-${i}`, title: ['Show HN: I Built a Rust-Powered Database from Scratch', 'The Future of WebAssembly in Browser Applications', 'Understanding Linux Kernel Memory Management', 'Why I Switched from React to Svelte', 'Building a Distributed System with Go', 'Lessons from Running Postgres at Scale', 'The Art of Writing Clean Shell Scripts', 'Debugging Memory Leaks in Production', 'Implementing CRDTs for Real-Time Collaboration', 'Exploring eBPF for System Observability'][i],
      snippet: ['A detailed writeup of building an in-memory database in Rust with persistence.', 'WebAssembly is enabling near-native performance for complex web applications.', 'Deep dive into how the Linux kernel manages virtual memory and paging.', 'A developer shares their experience migrating a large codebase to Svelte.', 'Best practices for building fault-tolerant distributed systems with Go.', 'Operational lessons from managing multi-terabyte PostgreSQL deployments.', 'Patterns and conventions for maintainable Bash scripts in production.', 'Techniques for identifying and fixing memory leaks in live systems.', 'How conflict-free replicated data types enable offline-first apps.', 'Using eBPF to gain deep visibility into Linux system calls.'][i],
      content: ['Full technical writeup with code examples and benchmarks.', 'Technical analysis of WASM capabilities and limitations.', 'Detailed explanation with diagrams of the memory management subsystem.', 'Comparison of developer experience, performance, and ecosystem.', 'Architecture patterns with code examples and failure scenarios.', 'Configuration tuning, monitoring, and maintenance strategies.', 'Code examples and style guide for production shell scripts.', 'Tools and methodologies for production debugging.', 'Implementation details and performance characteristics.', 'Tutorial on writing eBPF programs for tracing.'][i],
      date: new Date(Date.now() - i * 3600000 * 2).toISOString(), read: false, feedId: 'hn',
    })),
  },
  {
    id: 'wd', name: 'Wired', url: 'https://www.wired.com/feed/', icon: 'WD',
    articles: Array.from({ length: 10 }, (_, i) => ({
      id: `wd-${i}`, title: ['Inside the Lab Growing Human Organs', 'The Ethics of AI-Generated Art', 'How Blockchain is Changing Supply Chains', 'The Rise of Brain-Computer Interfaces', 'Gene Editing: Promise and Peril', 'Autonomous Drones in Disaster Response', 'The Science of Sleep Optimization', 'Virtual Reality Therapy for PTSD', 'Smart Cities and Privacy Concerns', 'The New Space Race to Mars'][i],
      snippet: ['Scientists are bio-printing functional organ tissue for transplantation.', 'As AI art tools improve, questions about authorship and copyright arise.', 'Distributed ledger technology is bringing transparency to global trade.', 'Neural interfaces are restoring mobility to paralyzed patients.', 'CRISPR technology offers cures but raises ethical questions.', 'Drone swarms are being deployed to search earthquake rubble.', 'Researchers are decoding the mysteries of restorative sleep.', 'VR exposure therapy shows remarkable results for veterans.', 'Urban sensors collect data but at what cost to privacy?', 'Space agencies and private companies compete for the red planet.'][i],
      content: ['Exclusive access to the organ growth laboratory and interviews with researchers.', 'Exploration of copyright law and artistic creativity in the age of AI.', 'Case studies of blockchain implementation in shipping and logistics.', 'Firsthand accounts from patients using brain-computer interfaces.', 'Comprehensive overview of gene editing applications and regulations.', 'Footage and analysis of drone operations in emergency scenarios.', 'Latest research findings on sleep cycles and health implications.', 'Clinical trial results and patient testimonials for VR therapy.', 'Investigation into data collection practices in modern cities.', 'Timeline and technology comparison of Mars mission proposals.'][i],
      date: new Date(Date.now() - i * 3600000 * 7).toISOString(), read: false, feedId: 'wd',
    })),
  },
  {
    id: 'tv', name: 'The Verge', url: 'https://www.theverge.com/rss/index.xml', icon: 'TV',
    articles: Array.from({ length: 10 }, (_, i) => ({
      id: `tv-${i}`, title: ['Pixel 9 Pro Review: The AI Phone', 'Sony WH-1000XM6 First Look', 'Tesla Model 3 Refresh Test Drive', 'Apple Vision Pro Six Months Later', 'Samsung Galaxy S25 Ultra Hands-On', 'Netflix Password Sharing Crackdown', 'Steam Deck vs ROG Ally Comparison', 'Instagram Threads: One Year On', 'YouTube Music Redesign Impressions', 'Best Laptops for Students 2025'][i],
      snippet: ['Google latest flagship puts AI features front and center.', 'Sony newest noise-canceling headphones bring incremental improvements.', 'The refreshed Model 3 gets subtle but meaningful updates.', 'Has the Vision Pro found its place in Apple ecosystem?', 'Samsung new ultra phone pushes the boundaries of mobile photography.', 'Netflix enforcement of account sharing rules is expanding globally.', 'We compare the leading handheld gaming PCs head-to-head.', 'Threads has evolved significantly since its chaotic launch.', 'The redesigned app focuses on discovery and personalization.', 'Our top picks for students heading back to school.'][i],
      content: ['Comprehensive review with photo samples and performance benchmarks.', 'Audio quality analysis and comparison with previous generation.', 'Driving impressions of the updated Model 3 range and features.', 'Long-term evaluation of the Vision Pro software and comfort.', 'Camera test samples and feature breakdown.', 'How the password sharing rules work and user reactions.', 'Performance benchmarks and ergonomics comparison.', 'Feature updates and community growth analysis.', 'UI walkthrough and feature comparison with Spotify.', 'Laptop recommendations across different budgets and use cases.'][i],
      date: new Date(Date.now() - i * 3600000 * 4).toISOString(), read: false, feedId: 'tv',
    })),
  },
];

const loadReadState = (): Set<string> => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) return new Set(JSON.parse(saved));
  } catch { /* ignore */ }
  return new Set();
};

const saveReadState = (readIds: Set<string>) => {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify([...readIds])); } catch { /* ignore */ }
};

export default function RssReader() {
  const [feeds, setFeeds] = useState<Feed[]>(MOCK_FEEDS);
  const [selectedFeed, setSelectedFeed] = useState<string>('all');
  const [readIds, setReadIds] = useState<Set<string>>(loadReadState);
  const [viewArticle, setViewArticle] = useState<Article | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [showAddFeed, setShowAddFeed] = useState(false);
  const [newFeedUrl, setNewFeedUrl] = useState('');
  const [newFeedName, setNewFeedName] = useState('');

  useEffect(() => { saveReadState(readIds); }, [readIds]);

  const allArticles = useMemo(() => {
    const articles = feeds.flatMap(f => f.articles);
    articles.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
    return articles;
  }, [feeds]);

  const filteredArticles = useMemo(() => {
    if (selectedFeed === 'all') return allArticles;
    return allArticles.filter(a => a.feedId === selectedFeed);
  }, [allArticles, selectedFeed]);

  const feedUnreadCounts = useMemo(() => {
    const counts: Record<string, number> = { all: 0 };
    feeds.forEach(f => {
      const unread = f.articles.filter(a => !readIds.has(a.id)).length;
      counts[f.id] = unread;
      counts.all += unread;
    });
    return counts;
  }, [feeds, readIds]);

  const markRead = (id: string) => setReadIds(prev => new Set([...prev, id]));
  const markUnread = (id: string) => setReadIds(prev => { const next = new Set(prev); next.delete(id); return next; });

  const refreshFeeds = () => {
    setRefreshing(true);
    setTimeout(() => {
      setFeeds(prev => prev.map(f => ({
        ...f,
        articles: f.articles.map(a => ({ ...a, date: new Date(Date.now() - Math.random() * 86400000).toISOString() })),
      })));
      setRefreshing(false);
    }, 1500);
  };

  const addFeed = () => {
    if (!newFeedUrl.trim() || !newFeedName.trim()) return;
    const newFeed: Feed = {
      id: Date.now().toString(), name: newFeedName.trim(), url: newFeedUrl.trim(), icon: newFeedName.trim().slice(0, 2).toUpperCase(),
      articles: Array.from({ length: 5 }, (_, i) => ({
        id: `custom-${Date.now()}-${i}`, title: `Sample Article ${i + 1} from ${newFeedName.trim()}`,
        snippet: 'This is a sample article from your newly added RSS feed. Real articles would appear here.',
        content: 'Full content would be fetched from the RSS feed URL you provided.',
        date: new Date(Date.now() - i * 3600000).toISOString(), read: false, feedId: `custom-${Date.now()}`,
      })),
    };
    setFeeds(prev => [...prev, newFeed]);
    setShowAddFeed(false);
    setNewFeedUrl('');
    setNewFeedName('');
  };

  const formatDate = (d: string) => {
    const date = new Date(d);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  if (viewArticle) {
    return (
      <div className="flex flex-col h-full" style={{ background: 'var(--bg-window)' }}>
        <div className="flex items-center gap-2 px-3 py-2 border-b" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-panel)' }}>
          <button onClick={() => setViewArticle(null)} className="p-1 rounded" style={{ color: 'var(--text-secondary)' }}><ChevronLeft size={16} /></button>
          <span className="text-sm font-medium flex-1 truncate" style={{ color: 'var(--text-primary)' }}>{viewArticle.title}</span>
          {!readIds.has(viewArticle.id) ? (
            <button onClick={() => markRead(viewArticle.id)} className="flex items-center gap-1 px-2 py-1 rounded-md text-xs" style={{ color: 'var(--text-secondary)' }}><Check size={12} /> Mark Read</button>
          ) : (
            <button onClick={() => markUnread(viewArticle.id)} className="flex items-center gap-1 px-2 py-1 rounded-md text-xs" style={{ color: 'var(--text-secondary)' }}><CheckCheck size={12} /> Read</button>
          )}
        </div>
        <div className="flex-1 overflow-auto custom-scrollbar p-4">
          <h2 className="text-lg font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>{viewArticle.title}</h2>
          <div className="flex items-center gap-3 mb-4 text-xs" style={{ color: 'var(--text-secondary)' }}>
            <span className="flex items-center gap-1"><Globe size={10} /> {feeds.find(f => f.id === viewArticle.feedId)?.name}</span>
            <span className="flex items-center gap-1"><Clock size={10} /> {formatDate(viewArticle.date)}</span>
          </div>
          <p className="text-sm leading-relaxed" style={{ color: 'var(--text-primary)' }}>{viewArticle.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full" style={{ background: 'var(--bg-window)' }}>
      {/* Sidebar */}
      <div className="w-44 border-r flex-shrink-0 flex flex-col" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-panel)' }}>
        <div className="flex items-center gap-2 px-3 py-2 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
          <Rss size={14} style={{ color: 'var(--accent-primary)' }} />
          <span className="text-xs font-semibold flex-1" style={{ color: 'var(--text-primary)' }}>Feeds</span>
        </div>
        <button onClick={() => setSelectedFeed('all')} className="flex items-center justify-between px-3 py-2 text-xs transition-colors" style={{ background: selectedFeed === 'all' ? 'var(--bg-selected)' : 'transparent', color: selectedFeed === 'all' ? 'var(--accent-primary)' : 'var(--text-primary)' }}>
          <span>All Articles</span><span className="px-1.5 py-0.5 rounded-full text-[10px]" style={{ background: 'var(--bg-hover)', color: 'var(--text-secondary)' }}>{feedUnreadCounts.all}</span>
        </button>
        {feeds.map(f => (
          <button key={f.id} onClick={() => setSelectedFeed(f.id)} className="flex items-center justify-between px-3 py-2 text-xs transition-colors" style={{ background: selectedFeed === f.id ? 'var(--bg-selected)' : 'transparent', color: selectedFeed === f.id ? 'var(--accent-primary)' : 'var(--text-primary)' }}>
            <span className="flex items-center gap-1.5"><span className="w-5 h-5 rounded flex items-center justify-center text-[9px] font-bold flex-shrink-0" style={{ background: 'var(--accent-primary)', color: '#fff' }}>{f.icon}</span> {f.name}</span>
            <span className="px-1.5 py-0.5 rounded-full text-[10px]" style={{ background: 'var(--bg-hover)', color: 'var(--text-secondary)' }}>{feedUnreadCounts[f.id]}</span>
          </button>
        ))}
        <div className="mt-auto p-2 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
          <button onClick={() => setShowAddFeed(true)} className="flex items-center gap-1 w-full px-2 py-1.5 rounded-md text-xs" style={{ background: 'var(--bg-hover)', color: 'var(--text-secondary)' }}><Plus size={10} /> Add Feed</button>
        </div>
      </div>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex items-center gap-2 px-3 py-2 border-b" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-panel)' }}>
          <span className="text-sm font-medium flex-1" style={{ color: 'var(--text-primary)' }}>{selectedFeed === 'all' ? 'All Articles' : feeds.find(f => f.id === selectedFeed)?.name}</span>
          <button onClick={refreshFeeds} className={`p-1.5 rounded ${refreshing ? 'animate-spin' : ''}`} style={{ color: 'var(--text-secondary)' }}><RefreshCw size={14} /></button>
        </div>
        <div className="flex-1 overflow-auto custom-scrollbar">
          {filteredArticles.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full gap-2" style={{ color: 'var(--text-secondary)' }}><Rss size={32} strokeWidth={1} /><p className="text-xs">No articles</p></div>
          ) : (
            <div className="divide-y" style={{ borderColor: 'var(--border-subtle)' }}>
              {filteredArticles.map(a => (
                <button key={a.id} onClick={() => { markRead(a.id); setViewArticle(a); }} className="flex items-start gap-3 w-full px-4 py-3 text-left transition-colors" style={{ background: readIds.has(a.id) ? 'transparent' : 'rgba(124,77,255,0.03)' }} onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')} onMouseLeave={e => (e.currentTarget.style.background = readIds.has(a.id) ? 'transparent' : 'rgba(124,77,255,0.03)')}>
                  {!readIds.has(a.id) && <div className="w-2 h-2 rounded-full mt-1.5 flex-shrink-0" style={{ background: 'var(--accent-primary)' }} />}
                  {readIds.has(a.id) && <div className="w-2 h-2 rounded-full mt-1.5 flex-shrink-0" style={{ background: 'var(--border-subtle)' }} />}
                  <div className="flex-1 min-w-0">
                    <h4 className={`text-sm truncate ${readIds.has(a.id) ? 'font-normal' : 'font-medium'}`} style={{ color: readIds.has(a.id) ? 'var(--text-secondary)' : 'var(--text-primary)' }}>{a.title}</h4>
                    <p className="text-xs mt-0.5 line-clamp-2" style={{ color: 'var(--text-disabled)' }}>{a.snippet}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-hover)', color: 'var(--text-secondary)' }}>{feeds.find(f => f.id === a.feedId)?.name}</span>
                      <span className="text-[10px]" style={{ color: 'var(--text-disabled)' }}>{formatDate(a.date)}</span>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Add Feed Modal */}
      {showAddFeed && (
        <div className="absolute inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.5)' }}>
          <div className="rounded-lg shadow-xl p-4" style={{ width: '360px', background: 'var(--bg-window)' }}>
            <div className="flex items-center justify-between mb-3"><span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>Add RSS Feed</span><button onClick={() => setShowAddFeed(false)} className="p-1 rounded"><X size={14} /></button></div>
            <input value={newFeedName} onChange={e => setNewFeedName(e.target.value)} placeholder="Feed name" className="w-full px-2.5 py-1.5 rounded-md text-xs outline-none mb-2" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }} />
            <input value={newFeedUrl} onChange={e => setNewFeedUrl(e.target.value)} placeholder="Feed URL (e.g., https://example.com/feed.xml)" className="w-full px-2.5 py-1.5 rounded-md text-xs outline-none mb-3" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }} />
            <button onClick={addFeed} className="w-full py-1.5 rounded-md text-xs font-medium" style={{ background: 'var(--accent-primary)', color: '#fff' }}>Add Feed</button>
          </div>
        </div>
      )}
    </div>
  );
}

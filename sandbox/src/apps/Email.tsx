// ============================================================
// Email Client — Three-pane layout with compose, folders, search
// ============================================================

import { useState, useMemo, useCallback, memo } from 'react';
import {
  Inbox, Send, FileText, Trash2, ShieldAlert, Star, Search, RefreshCw,
  Reply, Forward, Mail, X
} from 'lucide-react';

// ---- Types ----
interface Email {
  id: string;
  from: string;
  fromEmail: string;
  to: string[];
  subject: string;
  body: string;
  date: string;
  folder: 'inbox' | 'sent' | 'drafts' | 'trash' | 'spam';
  isRead: boolean;
  isStarred: boolean;
  labels: string[];
}

// ---- Mock Data ----
const INITIAL_EMAILS: Email[] = [
  {
    id: '1', from: 'Dulus OS Team', fromEmail: 'team@Dulus OS.local',
    to: ['user@Dulus OS.local'], subject: 'Welcome to Dulus OS!',
    body: 'Welcome to your new Dulus OS web desktop experience.\n\nWe hope you enjoy exploring all the features and apps. This is a fully functional web-based operating system that runs entirely in your browser.\n\nFeatures include:\n- 50+ built-in applications\- Virtual file system with localStorage persistence\n- Window management with drag, resize, minimize, maximize\n- Customizable desktop with wallpapers and themes\n\nHappy computing!\nThe Dulus OS Team',
    date: '2024-01-15T09:00:00', folder: 'inbox', isRead: false, isStarred: true, labels: ['important'],
  },
  {
    id: '2', from: 'Alice Johnson', fromEmail: 'alice@example.com',
    to: ['user@Dulus OS.local'], subject: 'Meeting notes from today',
    body: 'Hey!\n\nHere are the notes from our meeting today:\n\n1. Review Q4 goals\n2. Update project timeline\n3. Schedule follow-up for next week\n\nLet me know if you have any questions!\n\n- Alice',
    date: '2024-01-15T14:30:00', folder: 'inbox', isRead: false, isStarred: false, labels: [],
  },
  {
    id: '3', from: 'GitHub', fromEmail: 'noreply@github.com',
    to: ['user@Dulus OS.local'], subject: 'Security alert for your repository',
    body: 'Hi there,\n\nWe noticed a new sign-in to your GitHub account from a new device. If this was you, you can disregard this email.\n\nIf you don\'t recognize this activity, please review your account security immediately.\n\nThanks,\nThe GitHub Team',
    date: '2024-01-14T22:15:00', folder: 'inbox', isRead: true, isStarred: false, labels: [],
  },
  {
    id: '4', from: 'Bob Smith', fromEmail: 'bob@example.com',
    to: ['user@Dulus OS.local'], subject: 'Project update - Phase 2 complete',
    body: 'Great news!\n\nPhase 2 of the project is now complete. All milestones have been hit on time and the deliverables are ready for review.\n\nKey achievements:\n- Backend API: 100% complete\n- Frontend integration: 95% complete\n- Testing coverage: 87%\n\nLet\'s schedule a demo for next week.\n\nCheers,\nBob',
    date: '2024-01-14T11:00:00', folder: 'inbox', isRead: true, isStarred: true, labels: ['work'],
  },
  {
    id: '5', from: 'Newsletter Weekly', fromEmail: 'newsletter@weekly digest.local',
    to: ['user@Dulus OS.local'], subject: 'Your weekly tech digest',
    body: 'This week in tech:\n\n- New AI models show impressive capabilities\n- Open source contributions hit record high\n- WebAssembly adoption growing steadily\n- New CSS features landing in browsers\n\nRead more at our website.',
    date: '2024-01-13T08:00:00', folder: 'inbox', isRead: true, isStarred: false, labels: [],
  },
  {
    id: '6', from: 'Carol White', fromEmail: 'carol@example.com',
    to: ['user@Dulus OS.local'], subject: 'Lunch next week?',
    body: 'Hi!\n\nIt\'s been a while since we caught up. Want to grab lunch next Tuesday? There\'s a great new place downtown I\'ve been wanting to try.\n\nLet me know what works for you!\n\nCarol',
    date: '2024-01-12T16:45:00', folder: 'inbox', isRead: true, isStarred: false, labels: [],
  },
  {
    id: '7', from: 'Amazon', fromEmail: 'orders@amazon.com',
    to: ['user@Dulus OS.local'], subject: 'Your order has shipped!',
    body: 'Your order #12345 has shipped and is on its way!\n\nEstimated delivery: January 18, 2024\n\nTrack your package at the link below.\n\nThank you for shopping with us.',
    date: '2024-01-12T09:30:00', folder: 'inbox', isRead: true, isStarred: false, labels: ['shopping'],
  },
  {
    id: '8', from: 'David Lee', fromEmail: 'david@example.com',
    to: ['user@Dulus OS.local'], subject: 'Code review feedback',
    body: 'Hey,\n\nI\'ve reviewed your PR. Overall looks great! Just a few minor comments:\n\n1. Consider extracting the utility function\n2. Add more test cases for edge conditions\n3. The error handling could be more specific\n\nLet me know when you\'ve updated it!\n\nDavid',
    date: '2024-01-11T13:20:00', folder: 'inbox', isRead: true, isStarred: false, labels: ['work'],
  },
  {
    id: '9', from: 'Netflix', fromEmail: 'info@netflix.com',
    to: ['user@Dulus OS.local'], subject: 'New releases this month',
    body: 'Check out what\'s new on Netflix this month!\n\n- Exciting new original series\n- Award-winning documentaries\n- Classic movie additions\n\nYour next favorite show is waiting.',
    date: '2024-01-10T10:00:00', folder: 'inbox', isRead: true, isStarred: false, labels: [],
  },
  {
    id: '10', from: 'Eva Martinez', fromEmail: 'eva@example.com',
    to: ['user@Dulus OS.local'], subject: 'Happy New Year!',
    body: 'Happy New Year!\n\nWishing you all the best for 2024. Hope we can catch up soon!\n\nEva',
    date: '2024-01-01T00:01:00', folder: 'inbox', isRead: true, isStarred: true, labels: [],
  },
  {
    id: '11', from: 'Security Team', fromEmail: 'security@Dulus OS.local',
    to: ['user@Dulus OS.local'], subject: 'Important: Password reset required',
    body: 'For security purposes, please reset your password within the next 7 days.\n\nThis is a routine security measure to keep your account safe.\n\nClick the link below to reset your password.',
    date: '2024-01-09T15:00:00', folder: 'spam', isRead: true, isStarred: false, labels: [],
  },
  {
    id: '12', from: 'Unknown Sender', fromEmail: 'suspicious@random.com',
    to: ['user@Dulus OS.local'], subject: 'You won a prize!',
    body: 'Congratulations! You have been selected as a winner. Click here to claim your prize.\n\nThis is clearly spam and has been filtered accordingly.',
    date: '2024-01-08T03:00:00', folder: 'spam', isRead: true, isStarred: false, labels: [],
  },
  {
    id: '13', from: 'me', fromEmail: 'user@Dulus OS.local',
    to: ['alice@example.com'], subject: 'Re: Meeting notes from today',
    body: 'Thanks Alice!\n\nThe notes look great. I\'ll review the timeline and get back to you by EOD.\n\nCheers!',
    date: '2024-01-15T15:00:00', folder: 'sent', isRead: true, isStarred: false, labels: [],
  },
  {
    id: '14', from: 'me', fromEmail: 'user@Dulus OS.local',
    to: ['team@project.local'], subject: 'Weekly status update',
    body: 'Team,\n\nHere is the weekly status update:\n\n- Completed: UI mockups\n- In progress: API integration\n- Blockers: None\n\nGreat work everyone!',
    date: '2024-01-12T17:00:00', folder: 'sent', isRead: true, isStarred: false, labels: [],
  },
  {
    id: '15', from: 'me', fromEmail: 'user@Dulus OS.local',
    to: ['draft@local'], subject: 'Draft: Proposal for new feature',
    body: 'This is a draft email about the new feature proposal...\n\n[Draft content incomplete]',
    date: '2024-01-15T10:00:00', folder: 'drafts', isRead: true, isStarred: false, labels: [],
  },
  {
    id: '16', from: 'Old Newsletter', fromEmail: 'old@newsletter.com',
    to: ['user@Dulus OS.local'], subject: 'Last month\'s deals',
    body: 'These deals have expired. This email was moved to trash.',
    date: '2023-12-01T00:00:00', folder: 'trash', isRead: true, isStarred: false, labels: [],
  },
];

// ---- Helpers ----
const formatDate = (dateStr: string): string => {
  const d = new Date(dateStr);
  const now = new Date();
  const diffDays = Math.floor((now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays}d ago`;
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
};

const getInitials = (name: string) => name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2);

const FOLDER_CONFIG = [
  { id: 'inbox' as const, label: 'Inbox', icon: Inbox },
  { id: 'sent' as const, label: 'Sent', icon: Send },
  { id: 'drafts' as const, label: 'Drafts', icon: FileText },
  { id: 'trash' as const, label: 'Trash', icon: Trash2 },
  { id: 'spam' as const, label: 'Spam', icon: ShieldAlert },
];

// ---- Compose Modal ----
const ComposeModal = memo(function ComposeModal({ onClose, onSend }: { onClose: () => void; onSend: (email: Omit<Email, 'id' | 'date' | 'isRead' | 'isStarred' | 'labels'>) => void }) {
  const [to, setTo] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');

  const handleSend = () => {
    if (!to.trim() || !subject.trim()) return;
    onSend({ from: 'me', fromEmail: 'user@Dulus OS.local', to: [to], subject, body, folder: 'sent' });
    onClose();
  };

  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)' }}>
      <div className="flex flex-col w-full h-full" style={{ maxWidth: 600, maxHeight: 520, background: 'var(--bg-window)', borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-xl)' }}>
        <div className="flex items-center justify-between px-4 shrink-0" style={{ height: 48, borderBottom: '1px solid var(--border-subtle)' }}>
          <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>New Message</h3>
          <button onClick={onClose} className="flex items-center justify-center rounded-lg hover:bg-[var(--bg-hover)]" style={{ width: 32, height: 32 }}>
            <X size={16} style={{ color: 'var(--text-secondary)' }} />
          </button>
        </div>
        <div className="flex flex-col gap-3 p-4 flex-1">
          <input
            type="text"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            placeholder="To"
            className="w-full px-3 outline-none"
            style={{ height: 36, borderRadius: 'var(--radius-md)', background: 'var(--bg-input)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', fontSize: '13px' }}
          />
          <input
            type="text"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="Subject"
            className="w-full px-3 outline-none"
            style={{ height: 36, borderRadius: 'var(--radius-md)', background: 'var(--bg-input)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', fontSize: '13px' }}
          />
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Write your message..."
            className="w-full flex-1 p-3 outline-none resize-none custom-scrollbar"
            style={{ borderRadius: 'var(--radius-md)', background: 'var(--bg-input)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', fontSize: '13px', lineHeight: 1.6 }}
          />
        </div>
        <div className="flex items-center justify-end gap-2 px-4 py-3 shrink-0" style={{ borderTop: '1px solid var(--border-subtle)' }}>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg transition-all hover:bg-[var(--bg-hover)]"
            style={{ fontSize: '13px', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }}
          >
            Discard
          </button>
          <button
            onClick={handleSend}
            className="px-4 py-2 rounded-lg transition-all hover:opacity-90 flex items-center gap-2"
            style={{ fontSize: '13px', fontWeight: 500, background: 'var(--accent-primary)', color: 'white' }}
          >
            <Send size={14} /> Send
          </button>
        </div>
      </div>
    </div>
  );
});

// ---- Main Email Component ----
export default function Email() {
  const [emails, setEmails] = useState<Email[]>(INITIAL_EMAILS);
  const [activeFolder, setActiveFolder] = useState<string>('inbox');
  const [selectedEmailId, setSelectedEmailId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showCompose, setShowCompose] = useState(false);

  const filteredEmails = useMemo(() => {
    let filtered = emails.filter((e) => e.folder === activeFolder);
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (e) => e.subject.toLowerCase().includes(q) || e.from.toLowerCase().includes(q) || e.body.toLowerCase().includes(q)
      );
    }
    return filtered.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
  }, [emails, activeFolder, searchQuery]);

  const selectedEmail = emails.find((e) => e.id === selectedEmailId);

  const unreadCount = useMemo(() => emails.filter((e) => e.folder === 'inbox' && !e.isRead).length, [emails]);

  const markAsRead = useCallback((id: string) => {
    setEmails((prev) => prev.map((e) => (e.id === id ? { ...e, isRead: true } : e)));
  }, []);

  const toggleStar = useCallback((id: string) => {
    setEmails((prev) => prev.map((e) => (e.id === id ? { ...e, isStarred: !e.isStarred } : e)));
  }, []);

  const moveToFolder = useCallback((id: string, folder: Email['folder']) => {
    setEmails((prev) => prev.map((e) => (e.id === id ? { ...e, folder } : e)));
    if (selectedEmailId === id) setSelectedEmailId(null);
  }, [selectedEmailId]);

  const handleSend = useCallback((newEmail: Omit<Email, 'id' | 'date' | 'isRead' | 'isStarred' | 'labels'>) => {
    const email: Email = {
      ...newEmail,
      id: Math.random().toString(36).slice(2),
      date: new Date().toISOString(),
      isRead: true,
      isStarred: false,
      labels: [],
    };
    setEmails((prev) => [email, ...prev]);
  }, []);

  const handleReply = useCallback(() => {
    if (!selectedEmail) return;
    setShowCompose(true);
  }, [selectedEmail]);

  const handleSelectEmail = useCallback((id: string) => {
    setSelectedEmailId(id);
    markAsRead(id);
  }, [markAsRead]);

  return (
    <div className="flex h-full" style={{ background: 'var(--bg-window)' }}>
      {/* Left Sidebar */}
      <div className="flex flex-col shrink-0" style={{ width: 200, background: 'var(--bg-titlebar)', borderRight: '1px solid var(--border-subtle)' }}>
        <div className="p-3">
          <button
            onClick={() => setShowCompose(true)}
            className="w-full flex items-center justify-center gap-2 transition-all hover:opacity-90"
            style={{
              height: 40, borderRadius: 20, background: 'var(--accent-primary)', color: 'white',
              fontSize: '14px', fontWeight: 500,
            }}
          >
            <Mail size={18} /> Compose
          </button>
        </div>

        <div className="flex flex-col gap-0.5 px-2">
          {FOLDER_CONFIG.map((folder) => {
            const Icon = folder.icon;
            const count = folder.id === 'inbox' ? unreadCount : 0;
            return (
              <button
                key={folder.id}
                onClick={() => { setActiveFolder(folder.id); setSelectedEmailId(null); }}
                className="flex items-center gap-3 px-3 py-2 rounded-lg transition-all"
                style={{
                  background: activeFolder === folder.id ? 'var(--bg-selected)' : 'transparent',
                  borderLeft: activeFolder === folder.id ? '3px solid var(--accent-primary)' : '3px solid transparent',
                }}
              >
                <Icon size={18} style={{ color: 'var(--text-secondary)' }} />
                <span className="flex-1 text-left" style={{ fontSize: '13px', color: 'var(--text-primary)' }}>{folder.label}</span>
                {count > 0 && (
                  <span
                    className="flex items-center justify-center rounded-full"
                    style={{ minWidth: 20, height: 20, background: 'var(--accent-error)', color: 'white', fontSize: '11px', fontWeight: 600, padding: '0 6px' }}
                  >
                    {count}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Middle Pane - Email List */}
      <div className="flex flex-col shrink-0" style={{ width: 340, borderRight: '1px solid var(--border-subtle)' }}>
        <div className="flex items-center gap-2 px-3 py-2 shrink-0" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
          <div className="flex items-center gap-2 px-3 flex-1" style={{ height: 32, borderRadius: 16, background: 'var(--bg-input)', border: '1px solid var(--border-default)' }}>
            <Search size={14} style={{ color: 'var(--text-disabled)', flexShrink: 0 }} />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search emails"
              className="flex-1 bg-transparent outline-none"
              style={{ color: 'var(--text-primary)', fontSize: '13px' }}
            />
          </div>
          <button className="flex items-center justify-center rounded-lg hover:bg-[var(--bg-hover)]" style={{ width: 28, height: 28 }}>
            <RefreshCw size={14} style={{ color: 'var(--text-secondary)' }} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar">
          {filteredEmails.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full gap-2">
              <Inbox size={32} style={{ color: 'var(--text-disabled)' }} />
              <span style={{ fontSize: '12px', color: 'var(--text-disabled)' }}>No emails</span>
            </div>
          ) : (
            filteredEmails.map((email) => (
              <div
                key={email.id}
                onClick={() => handleSelectEmail(email.id)}
                className="flex flex-col gap-1 px-3 py-2.5 cursor-pointer transition-all"
                style={{
                  borderBottom: '1px solid var(--border-subtle)',
                  background: selectedEmailId === email.id ? 'var(--bg-selected)' : 'transparent',
                  borderLeft: !email.isRead ? '3px solid var(--accent-primary)' : '3px solid transparent',
                }}
              >
                <div className="flex items-center gap-2">
                  <span
                    className="flex-1 truncate"
                    style={{
                      fontSize: '13px',
                      fontWeight: email.isRead ? 400 : 600,
                      color: 'var(--text-primary)',
                    }}
                  >
                    {email.from}
                  </span>
                  <button
                    onClick={(e) => { e.stopPropagation(); toggleStar(email.id); }}
                    className="flex items-center justify-center"
                    style={{ width: 20, height: 20 }}
                  >
                    <Star
                      size={14}
                      style={{ color: email.isStarred ? 'var(--accent-secondary)' : 'var(--text-disabled)' }}
                      fill={email.isStarred ? 'var(--accent-secondary)' : 'none'}
                    />
                  </button>
                  <span style={{ fontSize: '11px', color: 'var(--text-disabled)', flexShrink: 0 }}>{formatDate(email.date)}</span>
                </div>
                <span className="truncate" style={{ fontSize: '13px', fontWeight: email.isRead ? 400 : 600, color: 'var(--text-primary)' }}>
                  {email.subject}
                </span>
                <span className="truncate" style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                  {email.body.slice(0, 80)}...
                </span>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Right Pane - Reading */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {!selectedEmail ? (
          <div className="flex flex-col items-center justify-center h-full gap-3">
            <Mail size={48} style={{ color: 'var(--text-disabled)' }} />
            <span style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>Select an email to read</span>
          </div>
        ) : (
          <>
            {/* Reader Header */}
            <div className="flex items-center justify-between px-4 py-3 shrink-0" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
              <div className="flex items-center gap-2">
                <h2 className="truncate" style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', maxWidth: 400 }}>
                  {selectedEmail.subject}
                </h2>
              </div>
              <div className="flex items-center gap-1">
                <button onClick={handleReply} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all hover:bg-[var(--bg-hover)]" style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                  <Reply size={14} /> Reply
                </button>
                <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all hover:bg-[var(--bg-hover)]" style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                  <Forward size={14} /> Forward
                </button>
                <button onClick={() => moveToFolder(selectedEmail.id, 'trash')} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all hover:bg-[var(--bg-hover)]" style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                  <Trash2 size={14} /> Delete
                </button>
              </div>
            </div>

            {/* Sender Info */}
            <div className="flex items-start gap-3 px-4 py-3" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
              <div
                className="flex items-center justify-center rounded-full shrink-0"
                style={{ width: 40, height: 40, background: 'var(--accent-primary)', color: 'white', fontSize: '14px', fontWeight: 600 }}
              >
                {getInitials(selectedEmail.from)}
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-primary)' }}>{selectedEmail.from}</span>
                  <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>&lt;{selectedEmail.fromEmail}&gt;</span>
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                  To: {selectedEmail.to.join(', ')}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-disabled)', marginTop: 2 }}>
                  {new Date(selectedEmail.date).toLocaleString()}
                </div>
              </div>
              <button onClick={() => toggleStar(selectedEmail.id)}>
                <Star
                  size={18}
                  style={{ color: selectedEmail.isStarred ? 'var(--accent-secondary)' : 'var(--text-disabled)' }}
                  fill={selectedEmail.isStarred ? 'var(--accent-secondary)' : 'none'}
                />
              </button>
            </div>

            {/* Body */}
            <div className="flex-1 p-4 overflow-y-auto custom-scrollbar">
              <div style={{ fontSize: '14px', lineHeight: 1.7, color: 'var(--text-primary)', whiteSpace: 'pre-wrap' }}>
                {selectedEmail.body}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Compose Modal */}
      {showCompose && <ComposeModal onClose={() => setShowCompose(false)} onSend={handleSend} />}
    </div>
  );
}

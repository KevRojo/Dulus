import { useState, useEffect, useMemo } from 'react';
import {
  Users, Plus, X, Search, Star, Phone, Mail, MapPin, Edit2, Trash2, ChevronLeft, User
} from 'lucide-react';

interface Contact {
  id: string;
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  address: string;
  notes: string;
  group: 'personal' | 'work';
  favorite: boolean;
}

type GroupFilter = 'all' | 'favorites' | 'work' | 'personal';

const STORAGE_KEY = 'dulus_contacts';

const loadContacts = (): Contact[] => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) return JSON.parse(saved);
  } catch { /* ignore */ }
  // Default demo contacts
  return [
    { id: 'c1', firstName: 'Alice', lastName: 'Johnson', email: 'alice@example.com', phone: '+1 555-0101', address: '123 Maple St', notes: 'Team lead', group: 'work', favorite: true },
    { id: 'c2', firstName: 'Bob', lastName: 'Smith', email: 'bob@example.com', phone: '+1 555-0102', address: '456 Oak Ave', notes: 'Friend from college', group: 'personal', favorite: false },
    { id: 'c3', firstName: 'Carol', lastName: 'Williams', email: 'carol@example.com', phone: '+1 555-0103', address: '789 Pine Rd', notes: 'Designer', group: 'work', favorite: true },
  ];
};

const saveContacts = (contacts: Contact[]) => {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(contacts)); } catch { /* ignore */ }
};

const getInitials = (c: Contact) => `${c.firstName[0] || ''}${c.lastName[0] || ''}`.toUpperCase();

const stringColor = (str: string) => {
  const colors = ['#7C4DFF', '#4CAF50', '#FF9800', '#2196F3', '#F44336', '#9C27B0', '#00BCD4', '#795548'];
  let hash = 0;
  for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
  return colors[Math.abs(hash) % colors.length];
};

export default function Contacts() {
  const [contacts, setContacts] = useState<Contact[]>(loadContacts);
  const [search, setSearch] = useState('');
  const [groupFilter, setGroupFilter] = useState<GroupFilter>('all');
  const [viewContact, setViewContact] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [address, setAddress] = useState('');
  const [notes, setNotes] = useState('');
  const [group, setGroup] = useState<'personal' | 'work'>('personal');
  const [favorite, setFavorite] = useState(false);

  useEffect(() => { saveContacts(contacts); }, [contacts]);

  const filtered = useMemo(() => {
    let list = contacts;
    if (groupFilter === 'favorites') list = list.filter(c => c.favorite);
    else if (groupFilter === 'work') list = list.filter(c => c.group === 'work');
    else if (groupFilter === 'personal') list = list.filter(c => c.group === 'personal');
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(c =>
        c.firstName.toLowerCase().includes(q) ||
        c.lastName.toLowerCase().includes(q) ||
        c.email.toLowerCase().includes(q) ||
        c.phone.includes(q)
      );
    }
    return list.sort((a, b) => a.lastName.localeCompare(b.lastName));
  }, [contacts, groupFilter, search]);

  const selectedContact = viewContact ? contacts.find(c => c.id === viewContact) : null;

  const resetForm = () => {
    setFirstName(''); setLastName(''); setEmail(''); setPhone(''); setAddress(''); setNotes(''); setGroup('personal'); setFavorite(false); setEditingId(null);
  };

  const startEdit = (c: Contact) => {
    setEditingId(c.id); setFirstName(c.firstName); setLastName(c.lastName); setEmail(c.email); setPhone(c.phone); setAddress(c.address); setNotes(c.notes); setGroup(c.group); setFavorite(c.favorite); setShowForm(true);
  };

  const saveContact = () => {
    if (!firstName.trim() && !lastName.trim()) return;
    if (editingId) {
      setContacts(prev => prev.map(c => c.id === editingId ? { ...c, firstName: firstName.trim(), lastName: lastName.trim(), email, phone, address, notes, group, favorite } : c));
    } else {
      const newC: Contact = { id: Date.now().toString(36) + Math.random().toString(36).slice(2), firstName: firstName.trim(), lastName: lastName.trim(), email, phone, address, notes, group, favorite };
      setContacts(prev => [...prev, newC]);
    }
    setShowForm(false); resetForm();
  };

  const deleteContact = (id: string) => {
    setContacts(prev => prev.filter(c => c.id !== id));
    if (viewContact === id) setViewContact(null);
  };

  const toggleFavorite = (id: string) => {
    setContacts(prev => prev.map(c => c.id === id ? { ...c, favorite: !c.favorite } : c));
  };

  const groups: GroupFilter[] = ['all', 'favorites', 'work', 'personal'];
  const groupLabels: Record<GroupFilter, string> = { all: 'All', favorites: 'Favorites', work: 'Work', personal: 'Personal' };
  const groupCounts = useMemo(() => ({
    all: contacts.length, favorites: contacts.filter(c => c.favorite).length,
    work: contacts.filter(c => c.group === 'work').length, personal: contacts.filter(c => c.group === 'personal').length,
  }), [contacts]);

  if (selectedContact) {
    const c = selectedContact;
    return (
      <div className="flex flex-col h-full" style={{ background: 'var(--bg-window)' }}>
        <div className="flex items-center gap-2 px-3 py-2 border-b" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-panel)' }}>
          <button onClick={() => setViewContact(null)} className="p-1 rounded" style={{ color: 'var(--text-secondary)' }}><ChevronLeft size={16} /></button>
          <span className="text-sm font-medium flex-1" style={{ color: 'var(--text-primary)' }}>Contact Details</span>
          <button onClick={() => toggleFavorite(c.id)} className="p-1 rounded"><Star size={14} style={{ color: c.favorite ? 'var(--accent-secondary)' : 'var(--text-disabled)', fill: c.favorite ? 'var(--accent-secondary)' : 'none' }} /></button>
          <button onClick={() => startEdit(c)} className="p-1 rounded" style={{ color: 'var(--text-secondary)' }}><Edit2 size={14} /></button>
          <button onClick={() => deleteContact(c.id)} className="p-1 rounded" style={{ color: 'var(--accent-error)' }}><Trash2 size={14} /></button>
        </div>
        <div className="flex-1 overflow-auto custom-scrollbar p-4">
          <div className="flex flex-col items-center mb-4">
            <div className="w-16 h-16 rounded-full flex items-center justify-center text-lg font-bold mb-2" style={{ background: stringColor(c.id), color: '#fff' }}>{getInitials(c)}</div>
            <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>{c.firstName} {c.lastName}</h3>
            <span className="text-xs px-2 py-0.5 rounded-full mt-1 capitalize" style={{ background: 'var(--bg-hover)', color: 'var(--text-secondary)' }}>{c.group}</span>
          </div>
          <div className="space-y-2">
            {c.phone && (
              <div className="flex items-center gap-3 p-2 rounded-md" style={{ background: 'var(--bg-panel)' }}>
                <Phone size={14} style={{ color: 'var(--accent-primary)' }} />
                <div><p className="text-xs" style={{ color: 'var(--text-disabled)' }}>Phone</p><p className="text-sm" style={{ color: 'var(--text-primary)' }}>{c.phone}</p></div>
              </div>
            )}
            {c.email && (
              <div className="flex items-center gap-3 p-2 rounded-md" style={{ background: 'var(--bg-panel)' }}>
                <Mail size={14} style={{ color: 'var(--accent-primary)' }} />
                <div><p className="text-xs" style={{ color: 'var(--text-disabled)' }}>Email</p><p className="text-sm" style={{ color: 'var(--text-primary)' }}>{c.email}</p></div>
              </div>
            )}
            {c.address && (
              <div className="flex items-center gap-3 p-2 rounded-md" style={{ background: 'var(--bg-panel)' }}>
                <MapPin size={14} style={{ color: 'var(--accent-primary)' }} />
                <div><p className="text-xs" style={{ color: 'var(--text-disabled)' }}>Address</p><p className="text-sm" style={{ color: 'var(--text-primary)' }}>{c.address}</p></div>
              </div>
            )}
            {c.notes && (
              <div className="p-2 rounded-md" style={{ background: 'var(--bg-panel)' }}>
                <p className="text-xs mb-1" style={{ color: 'var(--text-disabled)' }}>Notes</p>
                <p className="text-sm" style={{ color: 'var(--text-primary)' }}>{c.notes}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-window)' }}>
      <div className="flex items-center gap-2 px-3 py-2 border-b" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-panel)' }}>
        <Users size={16} style={{ color: 'var(--accent-primary)' }} />
        <span className="text-sm font-medium flex-1" style={{ color: 'var(--text-primary)' }}>Contacts</span>
        <button onClick={() => { resetForm(); setShowForm(true); }} className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs" style={{ background: 'var(--accent-primary)', color: '#fff' }}><Plus size={12} /> Add</button>
      </div>
      <div className="px-3 py-2">
        <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-md" style={{ background: 'var(--bg-input)', border: '1px solid var(--border-subtle)' }}>
          <Search size={12} style={{ color: 'var(--text-disabled)' }} />
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search contacts..." className="flex-1 bg-transparent text-sm outline-none" style={{ color: 'var(--text-primary)' }} />
        </div>
      </div>
      <div className="flex gap-1 px-3 pb-2 overflow-x-auto">
        {groups.map(g => (
          <button key={g} onClick={() => setGroupFilter(g)} className="px-2.5 py-1 rounded-md text-xs whitespace-nowrap transition-colors capitalize" style={{ background: groupFilter === g ? 'var(--accent-primary)' : 'var(--bg-hover)', color: groupFilter === g ? '#fff' : 'var(--text-secondary)' }}>
            {groupLabels[g]} ({groupCounts[g]})
          </button>
        ))}
      </div>
      {showForm && (
        <div className="p-3 border-b" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-panel)' }}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{editingId ? 'Edit' : 'New'} Contact</span>
            <button onClick={() => { setShowForm(false); resetForm(); }} className="p-1 rounded"><X size={14} style={{ color: 'var(--text-secondary)' }} /></button>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <input value={firstName} onChange={e => setFirstName(e.target.value)} placeholder="First name" className="px-2 py-1 rounded-md text-xs outline-none" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }} />
            <input value={lastName} onChange={e => setLastName(e.target.value)} placeholder="Last name" className="px-2 py-1 rounded-md text-xs outline-none" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }} />
            <input value={email} onChange={e => setEmail(e.target.value)} placeholder="Email" className="px-2 py-1 rounded-md text-xs outline-none" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }} />
            <input value={phone} onChange={e => setPhone(e.target.value)} placeholder="Phone" className="px-2 py-1 rounded-md text-xs outline-none" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }} />
          </div>
          <input value={address} onChange={e => setAddress(e.target.value)} placeholder="Address" className="w-full px-2 py-1 rounded-md text-xs outline-none mt-2" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }} />
          <textarea value={notes} onChange={e => setNotes(e.target.value)} placeholder="Notes" rows={2} className="w-full px-2 py-1 rounded-md text-xs outline-none mt-2 resize-none" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }} />
          <div className="flex items-center gap-2 mt-2">
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>Group:</span>
            {(['personal', 'work'] as const).map(g => (
              <button key={g} onClick={() => setGroup(g)} className="px-2 py-0.5 rounded text-xs capitalize" style={{ background: group === g ? 'var(--accent-primary)' : 'var(--bg-hover)', color: group === g ? '#fff' : 'var(--text-secondary)' }}>{g}</button>
            ))}
            <button onClick={() => setFavorite(f => !f)} className="ml-auto"><Star size={14} style={{ color: favorite ? 'var(--accent-secondary)' : 'var(--text-disabled)', fill: favorite ? 'var(--accent-secondary)' : 'none' }} /></button>
          </div>
          <button onClick={saveContact} className="w-full py-1.5 rounded-md text-xs font-medium mt-2" style={{ background: 'var(--accent-primary)', color: '#fff' }}>Save Contact</button>
        </div>
      )}
      <div className="flex-1 overflow-auto custom-scrollbar">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-2" style={{ color: 'var(--text-secondary)' }}>
            <Users size={32} strokeWidth={1} />
            <p className="text-xs">{search ? 'No matches' : 'No contacts'}</p>
          </div>
        ) : (
          <div className="p-2 space-y-0.5">
            {filtered.map(c => (
              <button key={c.id} onClick={() => setViewContact(c.id)} className="flex items-center gap-3 w-full p-2 rounded-md text-left transition-colors" style={{ color: 'var(--text-primary)' }} onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')} onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0" style={{ background: stringColor(c.id), color: '#fff' }}>{getInitials(c)}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium truncate">{c.firstName} {c.lastName}</span>
                    {c.favorite && <Star size={10} style={{ color: 'var(--accent-secondary)', fill: 'var(--accent-secondary)' }} />}
                  </div>
                  <p className="text-xs truncate" style={{ color: 'var(--text-disabled)' }}>{c.email || c.phone}</p>
                </div>
                <span className="text-xs px-1.5 py-0.5 rounded capitalize flex-shrink-0" style={{ background: 'var(--bg-hover)', color: 'var(--text-secondary)' }}>{c.group}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

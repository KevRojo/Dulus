// ============================================================
// Calendar — Month/Week/Day views with events CRUD
// ============================================================

import { useState, useEffect, useMemo } from 'react';
import {
  ChevronLeft, ChevronRight, X, Clock, MapPin,
  AlignLeft, Trash2, Edit2,
} from 'lucide-react';

type ViewMode = 'month' | 'week' | 'day';

interface CalendarEvent {
  id: string;
  title: string;
  date: string; // YYYY-MM-DD
  time: string; // HH:MM
  duration: number; // minutes
  color: string;
  description: string;
  location: string;
}

const EVENT_COLORS = [
  '#7C4DFF', '#2196F3', '#4CAF50', '#FF9800', '#F44336',
];

const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'];
const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const DAY_NAMES_FULL = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

const generateId = () => Math.random().toString(36).slice(2) + Date.now().toString(36);

const loadEvents = (): CalendarEvent[] => {
  try {
    const saved = localStorage.getItem('dulus_calendar_events');
    if (saved) return JSON.parse(saved);
  } catch { /* ignore */ }
  // Sample events
  const today = new Date();
  const y = today.getFullYear();
  const m = String(today.getMonth() + 1).padStart(2, '0');
  const d = String(today.getDate()).padStart(2, '0');
  return [
    { id: generateId(), title: 'Project Review', date: `${y}-${m}-${d}`, time: '10:00', duration: 60, color: '#7C4DFF', description: 'Weekly project status review', location: 'Conference Room' },
    { id: generateId(), title: 'Lunch with Team', date: `${y}-${m}-${d}`, time: '12:30', duration: 60, color: '#4CAF50', description: '', location: 'Cafeteria' },
    { id: generateId(), title: 'Code Review', date: `${y}-${m}-${String(Math.min(31, Number(d) + 2)).padStart(2, '0')}`, time: '14:00', duration: 90, color: '#2196F3', description: 'Review PRs', location: '' },
  ];
};

const formatDateKey = (date: Date): string => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
};

const Calendar: React.FC = () => {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [view, setView] = useState<ViewMode>('month');
  const [events, setEvents] = useState<CalendarEvent[]>(loadEvents);
  const [showEventModal, setShowEventModal] = useState(false);
  const [editingEvent, setEditingEvent] = useState<CalendarEvent | null>(null);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [viewingEvent, setViewingEvent] = useState<CalendarEvent | null>(null);

  // Form state
  const [formTitle, setFormTitle] = useState('');
  const [formTime, setFormTime] = useState('09:00');
  const [formDuration, setFormDuration] = useState(60);
  const [formColor, setFormColor] = useState(EVENT_COLORS[0]);
  const [formDescription, setFormDescription] = useState('');
  const [formLocation, setFormLocation] = useState('');

  useEffect(() => {
    localStorage.setItem('dulus_calendar_events', JSON.stringify(events));
  }, [events]);

  const today = new Date();
  const todayKey = formatDateKey(today);

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  const monthDays = useMemo(() => {
    const firstDayOfMonth = new Date(year, month, 1);
    const lastDayOfMonth = new Date(year, month + 1, 0);
    const startDay = firstDayOfMonth.getDay();
    const daysInMonth = lastDayOfMonth.getDate();

    const days: { date: Date; dateKey: string; isCurrentMonth: boolean }[] = [];

    // Previous month filler
    const prevMonthDays = new Date(year, month, 0).getDate();
    for (let i = startDay - 1; i >= 0; i--) {
      const d = new Date(year, month - 1, prevMonthDays - i);
      days.push({ date: d, dateKey: formatDateKey(d), isCurrentMonth: false });
    }

    // Current month
    for (let i = 1; i <= daysInMonth; i++) {
      const d = new Date(year, month, i);
      days.push({ date: d, dateKey: formatDateKey(d), isCurrentMonth: true });
    }

    // Next month filler
    const remaining = 42 - days.length;
    for (let i = 1; i <= remaining; i++) {
      const d = new Date(year, month + 1, i);
      days.push({ date: d, dateKey: formatDateKey(d), isCurrentMonth: false });
    }

    return days;
  }, [year, month]);

  const getEventsForDate = (dateKey: string) =>
    events.filter(e => e.date === dateKey).sort((a, b) => a.time.localeCompare(b.time));

  const openNewEvent = (dateKey: string) => {
    setEditingEvent(null);
    setSelectedDate(dateKey);
    setFormTitle('');
    setFormTime('09:00');
    setFormDuration(60);
    setFormColor(EVENT_COLORS[0]);
    setFormDescription('');
    setFormLocation('');
    setShowEventModal(true);
  };

  const openEditEvent = (event: CalendarEvent) => {
    setEditingEvent(event);
    setSelectedDate(event.date);
    setFormTitle(event.title);
    setFormTime(event.time);
    setFormDuration(event.duration);
    setFormColor(event.color);
    setFormDescription(event.description);
    setFormLocation(event.location);
    setShowEventModal(true);
    setViewingEvent(null);
  };

  const saveEvent = () => {
    if (!formTitle.trim() || !selectedDate) return;
    if (editingEvent) {
      setEvents(prev => prev.map(e => e.id === editingEvent.id ? {
        ...e, title: formTitle, date: selectedDate, time: formTime,
        duration: formDuration, color: formColor, description: formDescription, location: formLocation,
      } : e));
    } else {
      setEvents(prev => [...prev, {
        id: generateId(), title: formTitle, date: selectedDate, time: formTime,
        duration: formDuration, color: formColor, description: formDescription, location: formLocation,
      }]);
    }
    setShowEventModal(false);
  };

  const deleteEvent = (id: string) => {
    setEvents(prev => prev.filter(e => e.id !== id));
    setViewingEvent(null);
  };

  const navigatePrev = () => {
    if (view === 'month') setCurrentDate(new Date(year, month - 1, 1));
    else if (view === 'week') setCurrentDate(new Date(year, month, currentDate.getDate() - 7));
    else setCurrentDate(new Date(year, month, currentDate.getDate() - 1));
  };

  const navigateNext = () => {
    if (view === 'month') setCurrentDate(new Date(year, month + 1, 1));
    else if (view === 'week') setCurrentDate(new Date(year, month, currentDate.getDate() + 7));
    else setCurrentDate(new Date(year, month, currentDate.getDate() + 1));
  };

  const goToday = () => setCurrentDate(new Date());

  // Mini month calendar for sidebar
  const miniMonthDays = useMemo(() => {
    const first = new Date(year, month, 1);
    const start = first.getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const days: { d: number; isCurrent: boolean; isToday: boolean }[] = [];
    for (let i = 0; i < start; i++) days.push({ d: 0, isCurrent: false, isToday: false });
    for (let i = 1; i <= daysInMonth; i++) {
      const dk = formatDateKey(new Date(year, month, i));
      days.push({ d: i, isCurrent: true, isToday: dk === todayKey });
    }
    return days;
  }, [year, month]);

  return (
    <div className="flex h-full" style={{ background: 'var(--bg-window)' }}>
      {/* Sidebar */}
      <div className="w-56 shrink-0 border-r flex flex-col" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-titlebar)' }}>
        <div className="p-3">
          <div className="text-xs text-[var(--text-secondary)] uppercase tracking-wider mb-2">{MONTH_NAMES[month]} {year}</div>
          <div className="grid grid-cols-7 gap-0 text-center">
            {DAY_NAMES.map(d => (
              <div key={d} className="text-[10px] text-[var(--text-disabled)] py-1">{d[0]}</div>
            ))}
            {miniMonthDays.map((day, i) => (
              <button
                key={i}
                onClick={() => day.isCurrent && setCurrentDate(new Date(year, month, day.d))}
                className="text-[10px] py-1 rounded-full transition-colors"
                style={{
                  color: day.isToday ? 'white' : day.isCurrent ? 'var(--text-primary)' : 'transparent',
                  background: day.isToday ? 'var(--accent-primary)' : 'transparent',
                }}
              >
                {day.d || ''}
              </button>
            ))}
          </div>
        </div>
        <div className="border-t p-3" style={{ borderColor: 'var(--border-subtle)' }}>
          <div className="text-xs text-[var(--text-secondary)] uppercase tracking-wider mb-2">Upcoming</div>
          {events
            .filter(e => e.date >= todayKey)
            .sort((a, b) => a.date.localeCompare(b.date) || a.time.localeCompare(b.time))
            .slice(0, 5)
            .map(e => (
              <button
                key={e.id}
                onClick={() => { setCurrentDate(new Date(e.date + 'T00:00:00')); setView('day'); }}
                className="flex items-start gap-2 w-full py-1.5 text-left hover:bg-[var(--bg-hover)] rounded px-1 transition-colors"
              >
                <div className="w-2 h-2 rounded-full mt-1 shrink-0" style={{ background: e.color }} />
                <div className="min-w-0">
                  <div className="text-xs text-[var(--text-primary)] truncate">{e.title}</div>
                  <div className="text-[10px] text-[var(--text-disabled)]">{e.date} {e.time}</div>
                </div>
              </button>
            ))}
        </div>
      </div>

      {/* Main calendar */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b shrink-0" style={{ borderColor: 'var(--border-subtle)' }}>
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-[var(--text-primary)]">
              {view === 'month' ? `${MONTH_NAMES[month]} ${year}` :
               view === 'week' ? `Week of ${MONTH_NAMES[month]} ${currentDate.getDate()}, ${year}` :
               `${DAY_NAMES_FULL[currentDate.getDay()]}, ${MONTH_NAMES[month]} ${currentDate.getDate()}, ${year}`}
            </h2>
          </div>
          <div className="flex items-center gap-1">
            <button onClick={navigatePrev} className="p-1.5 rounded hover:bg-[var(--bg-hover)] text-[var(--text-secondary)]">
              <ChevronLeft size={16} />
            </button>
            <button onClick={goToday} className="px-3 py-1.5 rounded text-xs font-medium hover:bg-[var(--bg-hover)] text-[var(--text-primary)]">
              Today
            </button>
            <button onClick={navigateNext} className="p-1.5 rounded hover:bg-[var(--bg-hover)] text-[var(--text-secondary)]">
              <ChevronRight size={16} />
            </button>
            <div className="w-px h-5 mx-2" style={{ background: 'var(--border-subtle)' }} />
            {(['month', 'week', 'day'] as ViewMode[]).map(v => (
              <button
                key={v}
                onClick={() => setView(v)}
                className="px-3 py-1.5 rounded text-xs capitalize font-medium transition-colors"
                style={{
                  background: view === v ? 'var(--accent-primary)' : 'transparent',
                  color: view === v ? 'white' : 'var(--text-primary)',
                }}
              >
                {v}
              </button>
            ))}
          </div>
        </div>

        {/* Month View */}
        {view === 'month' && (
          <>
            <div className="grid grid-cols-7 shrink-0">
              {DAY_NAMES.map(d => (
                <div key={d} className="text-center py-2 text-xs font-semibold text-[var(--text-secondary)] border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                  {d}
                </div>
              ))}
            </div>
            <div className="grid grid-cols-7 flex-1">
              {monthDays.map((day, i) => {
                const dayEvents = getEventsForDate(day.dateKey);
                const isToday = day.dateKey === todayKey;
                return (
                  <button
                    key={i}
                    onClick={() => { if (day.isCurrentMonth) openNewEvent(day.dateKey); }}
                    onDoubleClick={() => { if (day.isCurrentMonth) openNewEvent(day.dateKey); }}
                    className="border-r border-b p-1 text-left transition-colors relative overflow-hidden"
                    style={{
                      borderColor: 'var(--border-subtle)',
                      background: isToday ? 'rgba(124,77,255,0.08)' : 'transparent',
                      opacity: day.isCurrentMonth ? 1 : 0.3,
                    }}
                  >
                    <div className="flex items-center justify-center w-7 h-7 rounded-full text-xs mx-auto mb-1"
                      style={{
                        background: isToday ? 'var(--accent-primary)' : 'transparent',
                        color: isToday ? 'white' : 'var(--text-primary)',
                      }}
                    >
                      {day.date.getDate()}
                    </div>
                    <div className="space-y-0.5">
                      {dayEvents.slice(0, 3).map(e => (
                        <div
                          key={e.id}
                          onClick={ev => { ev.stopPropagation(); setViewingEvent(e); }}
                          className="text-[10px] truncate px-1 py-0.5 rounded"
                          style={{ background: e.color + '20', color: e.color, borderLeft: `2px solid ${e.color}` }}
                        >
                          {e.title}
                        </div>
                      ))}
                      {dayEvents.length > 3 && (
                        <div className="text-[10px] text-[var(--text-disabled)] px-1">+{dayEvents.length - 3} more</div>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </>
        )}

        {/* Week View */}
        {view === 'week' && (
          <div className="flex-1 overflow-auto custom-scrollbar">
            <div className="grid grid-cols-8">
              <div className="border-r" style={{ borderColor: 'var(--border-subtle)' }} />
              {Array.from({ length: 7 }, (_, i) => {
                const d = new Date(currentDate);
                d.setDate(d.getDate() - d.getDay() + i);
                const dk = formatDateKey(d);
                return (
                  <div key={i} className="text-center py-2 border-r border-b text-xs" style={{ borderColor: 'var(--border-subtle)' }}>
                    <div className="text-[var(--text-secondary)]">{DAY_NAMES[i]}</div>
                    <div className={`font-semibold ${dk === todayKey ? 'text-[var(--accent-primary)]' : 'text-[var(--text-primary)]'}`}>{d.getDate()}</div>
                  </div>
                );
              })}
            </div>
            {Array.from({ length: 24 }, (_, hour) => (
              <div key={hour} className="grid grid-cols-8" style={{ height: 48 }}>
                <div className="text-[10px] text-[var(--text-disabled)] text-right pr-2 pt-1 border-r" style={{ borderColor: 'var(--border-subtle)' }}>
                  {String(hour).padStart(2, '0')}:00
                </div>
                {Array.from({ length: 7 }, (_, day) => {
                  const d = new Date(currentDate);
                  d.setDate(d.getDate() - d.getDay() + day);
                  const dk = formatDateKey(d);
                  const hourEvents = getEventsForDate(dk).filter(e => parseInt(e.time) === hour);
                  return (
                    <div key={day} className="border-r border-b relative" style={{ borderColor: 'var(--border-subtle)' }}>
                      {hourEvents.map(e => (
                        <button
                          key={e.id}
                          onClick={() => setViewingEvent(e)}
                          className="absolute inset-x-0.5 top-0.5 bottom-0.5 rounded text-[10px] px-1 text-left truncate"
                          style={{ background: e.color + '30', color: e.color, borderLeft: `2px solid ${e.color}` }}
                        >
                          {e.title}
                        </button>
                      ))}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        )}

        {/* Day View */}
        {view === 'day' && (
          <div className="flex-1 overflow-auto custom-scrollbar">
            {Array.from({ length: 24 }, (_, hour) => {
              const dk = formatDateKey(currentDate);
              const hourEvents = getEventsForDate(dk).filter(e => parseInt(e.time) === hour);
              return (
                <div key={hour} className="flex border-b" style={{ borderColor: 'var(--border-subtle)', minHeight: 56 }}>
                  <div className="w-16 shrink-0 text-right pr-3 pt-2 text-xs text-[var(--text-disabled)]">
                    {String(hour).padStart(2, '0')}:00
                  </div>
                  <div className="flex-1 relative py-1">
                    {hourEvents.map(e => (
                      <button
                        key={e.id}
                        onClick={() => setViewingEvent(e)}
                        className="block w-full text-left px-3 py-2 rounded mx-1 mb-1 text-xs"
                        style={{ background: e.color + '20', color: e.color, borderLeft: `3px solid ${e.color}` }}
                      >
                        <span className="font-semibold">{e.title}</span>
                        <span className="ml-2 opacity-70">{e.time} ({e.duration}m)</span>
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Event Modal */}
      {showEventModal && (
        <div className="absolute inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.5)' }}>
          <div className="w-[400px] rounded-xl overflow-hidden flex flex-col" style={{ background: 'var(--bg-window)', boxShadow: 'var(--shadow-xl)' }}>
            <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">{editingEvent ? 'Edit Event' : 'New Event'}</h3>
              <button onClick={() => setShowEventModal(false)} className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
                <X size={16} />
              </button>
            </div>
            <div className="p-4 space-y-3">
              <input
                value={formTitle}
                onChange={e => setFormTitle(e.target.value)}
                placeholder="Event title"
                className="w-full h-9 px-3 rounded-lg text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-disabled)]"
                style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)' }}
                autoFocus
              />
              <div className="flex gap-2">
                <input
                  type="date"
                  value={selectedDate || ''}
                  onChange={e => setSelectedDate(e.target.value)}
                  className="flex-1 h-9 px-3 rounded-lg text-sm text-[var(--text-primary)] outline-none"
                  style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)' }}
                />
                <input
                  type="time"
                  value={formTime}
                  onChange={e => setFormTime(e.target.value)}
                  className="h-9 px-3 rounded-lg text-sm text-[var(--text-primary)] outline-none"
                  style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)' }}
                />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-[var(--text-secondary)]">Duration (min):</span>
                <input
                  type="number"
                  value={formDuration}
                  onChange={e => setFormDuration(Number(e.target.value))}
                  className="w-20 h-8 px-2 rounded-lg text-sm text-[var(--text-primary)] outline-none"
                  style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)' }}
                />
              </div>
              <div className="flex gap-2">
                {EVENT_COLORS.map(c => (
                  <button
                    key={c}
                    onClick={() => setFormColor(c)}
                    className="w-6 h-6 rounded-full transition-transform hover:scale-110"
                    style={{
                      background: c,
                      boxShadow: formColor === c ? `0 0 0 2px white, 0 0 0 4px ${c}` : 'none',
                    }}
                  />
                ))}
              </div>
              <input
                value={formLocation}
                onChange={e => setFormLocation(e.target.value)}
                placeholder="Location"
                className="w-full h-9 px-3 rounded-lg text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-disabled)]"
                style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)' }}
              />
              <textarea
                value={formDescription}
                onChange={e => setFormDescription(e.target.value)}
                placeholder="Description"
                rows={2}
                className="w-full px-3 py-2 rounded-lg text-sm text-[var(--text-primary)] outline-none resize-none placeholder:text-[var(--text-disabled)]"
                style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)' }}
              />
            </div>
            <div className="flex items-center justify-end gap-2 px-4 py-3 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
              {editingEvent && (
                <button
                  onClick={() => { deleteEvent(editingEvent.id); setShowEventModal(false); }}
                  className="px-4 py-2 rounded-lg text-xs font-medium text-[var(--accent-error)] hover:bg-[var(--bg-hover)]"
                >
                  Delete
                </button>
              )}
              <button onClick={() => setShowEventModal(false)} className="px-4 py-2 rounded-lg text-xs text-[var(--text-primary)] hover:bg-[var(--bg-hover)]">
                Cancel
              </button>
              <button
                onClick={saveEvent}
                className="px-4 py-2 rounded-lg text-xs font-medium text-white"
                style={{ background: 'var(--accent-primary)' }}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      {/* View Event Popup */}
      {viewingEvent && (
        <div className="absolute inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.5)' }}>
          <div className="w-[320px] rounded-xl overflow-hidden" style={{ background: 'var(--bg-window)', boxShadow: 'var(--shadow-xl)' }}>
            <div className="p-4">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{ background: viewingEvent.color }} />
                  <h3 className="text-sm font-semibold text-[var(--text-primary)]">{viewingEvent.title}</h3>
                </div>
                <button onClick={() => setViewingEvent(null)} className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
                  <X size={14} />
                </button>
              </div>
              <div className="mt-3 space-y-2">
                <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                  <Clock size={12} /> {viewingEvent.date} at {viewingEvent.time} ({viewingEvent.duration} min)
                </div>
                {viewingEvent.location && (
                  <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                    <MapPin size={12} /> {viewingEvent.location}
                  </div>
                )}
                {viewingEvent.description && (
                  <div className="flex items-start gap-2 text-xs text-[var(--text-secondary)]">
                    <AlignLeft size={12} className="mt-0.5 shrink-0" /> {viewingEvent.description}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2 mt-4">
                <button
                  onClick={() => openEditEvent(viewingEvent)}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
                >
                  <Edit2 size={12} /> Edit
                </button>
                <button
                  onClick={() => { deleteEvent(viewingEvent.id); }}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs text-[var(--accent-error)] hover:bg-[var(--bg-hover)]"
                >
                  <Trash2 size={12} /> Delete
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Calendar;

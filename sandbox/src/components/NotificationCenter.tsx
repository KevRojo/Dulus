// ============================================================
// NotificationCenter — Slide-out panel from right with calendar
// ============================================================

import { useState, memo, useCallback } from 'react';
import { format, startOfMonth, endOfMonth, startOfWeek, endOfWeek, addDays, isSameMonth, isSameDay, addMonths, subMonths } from 'date-fns';
import { Bell, X, ChevronLeft, ChevronRight } from 'lucide-react';
import { useOS } from '@/hooks/useOSStore';
import * as Icons from 'lucide-react';
import type { LucideProps } from 'lucide-react';

const DynamicIcon = ({ name, ...props }: { name: string } & LucideProps) => {
  const IconComp = (Icons as unknown as Record<string, React.ComponentType<LucideProps>>)[name];
  return IconComp ? <IconComp {...props} /> : null;
};

const NotificationCenter = memo(function NotificationCenter() {
  const { state, dispatch } = useOS();
  const { notificationCenterOpen, notifications } = state;
  const [calendarDate, setCalendarDate] = useState(new Date());

  const handleClose = useCallback(() => {
    dispatch({ type: 'TOGGLE_NOTIFICATION_CENTER' });
  }, [dispatch]);

  // Build calendar grid
  const monthStart = startOfMonth(calendarDate);
  const monthEnd = endOfMonth(monthStart);
  const calStart = startOfWeek(monthStart);
  const calEnd = endOfWeek(monthEnd);
  const days: Date[] = [];
  let day = calStart;
  while (day <= calEnd) {
    days.push(day);
    day = addDays(day, 1);
  }

  if (!notificationCenterOpen) return null;

  return (
    <div
      className="fixed top-[32px] right-0 bottom-0 z-[2500] flex flex-col"
      style={{
        width: 380,
        background: 'var(--bg-panel)',
        borderLeft: '1px solid var(--border-subtle)',
        animation: 'slideIn 300ms cubic-bezier(0, 0, 0.2, 1)',
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">Notifications</h2>
        <div className="flex items-center gap-2">
          <button
            onClick={() => dispatch({ type: 'CLEAR_NOTIFICATIONS' })}
            className="text-[10px] text-[var(--accent-primary)] hover:text-[var(--accent-primary-hover)] transition-colors"
          >
            Clear All
          </button>
          <button
            onClick={handleClose}
            className="w-7 h-7 rounded-lg flex items-center justify-center text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition-colors"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Do Not Disturb toggle */}
      <div className="flex items-center justify-between px-4 py-2 mb-2">
        <span className="text-xs text-[var(--text-primary)] font-medium">Do Not Disturb</span>
        <div className="w-10 h-6 rounded-full relative cursor-pointer" style={{ background: 'var(--border-default)' }}>
          <div className="absolute left-0.5 top-0.5 w-5 h-5 rounded-full bg-white shadow-sm" />
        </div>
      </div>

      {/* Calendar */}
      <div className="px-4 py-3 mx-4 rounded-xl" style={{ background: 'var(--bg-window)' }}>
        {/* Calendar header */}
        <div className="flex items-center justify-between mb-3">
          <button
            onClick={() => setCalendarDate(subMonths(calendarDate, 1))}
            className="w-6 h-6 rounded flex items-center justify-center text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
          >
            <ChevronLeft size={14} />
          </button>
          <span className="text-xs font-semibold text-[var(--text-primary)]">
            {format(calendarDate, 'MMMM yyyy')}
          </span>
          <button
            onClick={() => setCalendarDate(addMonths(calendarDate, 1))}
            className="w-6 h-6 rounded flex items-center justify-center text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
          >
            <ChevronRight size={14} />
          </button>
        </div>

        {/* Day names */}
        <div className="grid grid-cols-7 gap-0 mb-1">
          {['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map((d) => (
            <div key={d} className="text-center text-[10px] text-[var(--text-disabled)] py-1">{d}</div>
          ))}
        </div>

        {/* Days grid */}
        <div className="grid grid-cols-7 gap-0">
          {days.map((d, i) => {
            const isCurrentMonth = isSameMonth(d, calendarDate);
            const isToday = isSameDay(d, new Date());
            return (
              <button
                key={i}
                className="h-7 text-[10px] font-medium rounded-full flex items-center justify-center transition-colors"
                style={{
                  color: isToday ? 'white' : isCurrentMonth ? 'var(--text-primary)' : 'var(--text-disabled)',
                  background: isToday ? 'var(--accent-primary)' : 'transparent',
                }}
                onMouseEnter={(e) => {
                  if (!isToday) e.currentTarget.style.background = 'var(--bg-hover)';
                }}
                onMouseLeave={(e) => {
                  if (!isToday) e.currentTarget.style.background = 'transparent';
                }}
              >
                {format(d, 'd')}
              </button>
            );
          })}
        </div>
      </div>

      {/* Notifications list */}
      <div className="flex-1 overflow-y-auto px-4 py-3 mt-2 custom-scrollbar">
        {notifications.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-[var(--text-secondary)]">
            <Bell size={48} className="mb-3 opacity-30" />
            <p className="text-sm">No notifications</p>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {notifications.map((n) => (
              <div
                key={n.id}
                className="p-3 rounded-lg"
                style={{
                  background: 'var(--bg-window)',
                  boxShadow: 'var(--shadow-sm)',
                }}
              >
                <div className="flex items-center gap-2 mb-1">
                  <DynamicIcon name={n.appIcon} size={16} className="text-[var(--text-secondary)]" />
                  <span className="text-[10px] font-semibold text-[var(--text-primary)] flex-1">{n.appName}</span>
                  <span className="text-[10px] text-[var(--text-disabled)]">
                    {new Date(n.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                  <button
                    onClick={() => dispatch({ type: 'REMOVE_NOTIFICATION', id: n.id })}
                    className="w-4 h-4 rounded flex items-center justify-center text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                  >
                    <X size={10} />
                  </button>
                </div>
                <p className="text-xs font-semibold text-[var(--text-primary)]">{n.title}</p>
                <p className="text-[10px] text-[var(--text-secondary)] mt-0.5">{n.message}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      <style>{`
        @keyframes slideIn {
          from { transform: translateX(100%); }
          to { transform: translateX(0); }
        }
      `}</style>
    </div>
  );
});

export default NotificationCenter;

// ============================================================
// NotificationSystem — Toast notifications stack (top-right)
// ============================================================

import { useEffect, useState, memo } from 'react';
import { X } from 'lucide-react';
import * as Icons from 'lucide-react';
import type { LucideProps } from 'lucide-react';
import { useOS } from '@/hooks/useOSStore';

const DynamicIcon = ({ name, ...props }: { name: string } & LucideProps) => {
  const IconComp = (Icons as unknown as Record<string, React.ComponentType<LucideProps>>)[name];
  return IconComp ? <IconComp {...props} /> : null;
};

interface ToastProps {
  notification: {
    id: string;
    appName: string;
    appIcon: string;
    title: string;
    message: string;
    timestamp: number;
  };
  onClose: () => void;
  index: number;
}

const Toast = memo(function Toast({ notification, onClose, index }: ToastProps) {
  const [progress, setProgress] = useState(100);
  const [isHovered, setIsHovered] = useState(false);
  const [isExiting, setIsExiting] = useState(false);

  useEffect(() => {
    if (isHovered) return;
    const duration = 5000;
    const interval = 50;
    const step = (interval / duration) * 100;
    const timer = setInterval(() => {
      setProgress((prev) => {
        if (prev <= step) {
          clearInterval(timer);
          setIsExiting(true);
          setTimeout(onClose, 250);
          return 0;
        }
        return prev - step;
      });
    }, interval);
    return () => clearInterval(timer);
  }, [isHovered, onClose]);

  return (
    <div
      className="relative w-[360px] overflow-hidden"
      style={{
        background: 'var(--bg-notification)',
        borderRadius: 12,
        border: '1px solid var(--border-default)',
        boxShadow: 'var(--shadow-md)',
        padding: '12px 16px',
        animation: isExiting ? 'toastExit 250ms ease forwards' : 'toastEnter 300ms cubic-bezier(0.34, 1.56, 0.64, 1) forwards',
        marginBottom: 8,
        marginTop: index === 0 ? 8 : 0,
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Top row: app icon + name + time + close */}
      <div className="flex items-center gap-2">
        <DynamicIcon name={notification.appIcon} size={18} className="text-[var(--text-secondary)] shrink-0" />
        <span className="text-[10px] font-semibold text-[var(--text-primary)] flex-1">{notification.appName}</span>
        <span className="text-[10px] text-[var(--text-disabled)]">
          {new Date(notification.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
        <button
          onClick={() => { setIsExiting(true); setTimeout(onClose, 250); }}
          className="w-5 h-5 rounded flex items-center justify-center text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition-colors"
        >
          <X size={12} />
        </button>
      </div>

      {/* Title */}
      <p className="text-xs font-semibold text-[var(--text-primary)] mt-1">{notification.title}</p>

      {/* Message */}
      <p className="text-[10px] text-[var(--text-secondary)] mt-0.5 line-clamp-2">{notification.message}</p>

      {/* Progress bar */}
      <div
        className="absolute bottom-0 left-0 h-[2px] rounded-full"
        style={{
          width: `${progress}%`,
          background: 'var(--accent-primary)',
          transition: isHovered ? 'none' : 'width 50ms linear',
        }}
      />
    </div>
  );
});

const NotificationSystem = memo(function NotificationSystem() {
  const { state, dispatch } = useOS();
  const { notifications } = state;
  const toasts = notifications.filter((n) => !n.isRead).slice(0, 5);

  return (
    <div className="fixed top-[32px] right-2 z-[3500] flex flex-col items-end pointer-events-none">
      {toasts.map((toast, i) => (
        <div key={toast.id} className="pointer-events-auto"
          style={{ animationDelay: `${i * 50}ms` }}
        >
          <Toast
            notification={toast}
            onClose={() => dispatch({ type: 'REMOVE_NOTIFICATION', id: toast.id })}
            index={i}
          />
        </div>
      ))}

      <style>{`
        @keyframes toastEnter {
          from { opacity: 0; transform: translateX(120%); }
          to { opacity: 1; transform: translateX(0); }
        }
        @keyframes toastExit {
          from { opacity: 1; transform: translateX(0); }
          to { opacity: 0; transform: translateX(120%); }
        }
      `}</style>
    </div>
  );
});

export default NotificationSystem;

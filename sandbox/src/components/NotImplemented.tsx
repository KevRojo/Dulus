// ============================================================
// NotImplemented — Placeholder for unbuilt apps
// ============================================================

import { useEffect, useState } from 'react';
import { getAppById } from '@/apps/registry';
import * as Icons from 'lucide-react';
import type { LucideProps } from 'lucide-react';

interface Props {
  appId: string;
}

const DynamicIcon = ({ name, ...props }: { name: string } & LucideProps) => {
  const IconComp = (Icons as unknown as unknown as Record<string, React.ComponentType<LucideProps>>)[name];
  return IconComp ? <IconComp {...props} /> : <Icons.HelpCircle {...props} />;
};

export default function NotImplemented({ appId }: Props) {
  const app = getAppById(appId);
  const [dots, setDots] = useState('');

  useEffect(() => {
    const interval = setInterval(() => {
      setDots((prev) => (prev.length >= 3 ? '' : prev + '.'));
    }, 500);
    return () => clearInterval(interval);
  }, []);

  if (!app) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-[var(--text-secondary)]">
        <Icons.HelpCircle size={48} className="mb-4 opacity-50" />
        <p className="text-lg font-medium">Unknown App</p>
        <p className="text-sm mt-1">App ID: {appId}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center h-full text-[var(--text-primary)] select-none">
      <div className="w-20 h-20 rounded-2xl bg-[var(--bg-hover)] flex items-center justify-center mb-6">
        <DynamicIcon name={app.icon} size={40} className="text-[var(--accent-primary)]" />
      </div>
      <h2 className="text-xl font-semibold mb-2">{app.name}</h2>
      <p className="text-sm text-[var(--text-secondary)] mb-6 max-w-[280px] text-center">
        {app.description}
      </p>
      <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-[var(--bg-hover)] text-xs text-[var(--text-secondary)]">
        <Icons.Hammer size={14} />
        <span>Coming Soon{dots}</span>
      </div>
    </div>
  );
}

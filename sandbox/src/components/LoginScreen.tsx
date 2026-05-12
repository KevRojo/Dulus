// ============================================================
// LoginScreen v2 — Dulus OS branded login with editable user
// ============================================================

import { useState, useCallback, memo } from 'react';
import { LogOut, Moon, Power, User, ChevronDown } from 'lucide-react';
import { useOS } from '@/hooks/useOSStore';
import { getAssetPath } from '@/utils/assets';

/* Mini Dulus ASCII — 3 lines */
const DULUS_MINI = [
  '╔╦╗╦ ╦╦  ╦ ╦╔═╗',
  ' ║ ║ ║║  ║ ║╚═╗',
  ' ╩ ╚═╝╩═╝╚═╝╚═╝',
];

const LoginScreen = memo(function LoginScreen() {
  const { state, dispatch } = useOS();
  const [password, setPassword] = useState('');
  const [isUnlocking, setIsUnlocking] = useState(false);
  const [error, setError] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);

  // Default to KevRojo but allow switching
  const [selectedUser, setSelectedUser] = useState(state.auth.userName || 'KevRojo');

  const handleUnlock = useCallback(() => {
    setIsUnlocking(true);
    setError(false);
    setTimeout(() => {
      dispatch({ type: 'LOGIN', isGuest: false });
    }, 900);
  }, [dispatch]);

  const handleGuest = useCallback(() => {
    dispatch({ type: 'LOGIN', isGuest: true });
  }, [dispatch]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') handleUnlock();
    },
    [handleUnlock]
  );

  const users = ['KevRojo', 'Guest'];

  return (
    <div
      className="fixed inset-0 z-[9998] flex items-center justify-center"
      style={{
        backgroundImage: `url(${getAssetPath('/wallpapers/default.jpeg')})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
    >
      {/* Blur overlay with Dulus gradient tint */}
      <div
        className="absolute inset-0"
        style={{
          backdropFilter: 'blur(28px) saturate(1.2)',
          WebkitBackdropFilter: 'blur(28px) saturate(1.2)',
          background: 'linear-gradient(135deg, rgba(15,15,20,0.65) 0%, rgba(26,26,35,0.75) 100%)',
        }}
      />

      {/* Floating particles effect (subtle) */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        {[...Array(6)].map((_, i) => (
          <div
            key={i}
            className="absolute rounded-full"
            style={{
              width: 2 + (i % 3),
              height: 2 + (i % 3),
              background: 'rgba(99,102,241,0.3)',
              left: `${15 + i * 14}%`,
              top: `${20 + (i % 4) * 18}%`,
              animation: `floatParticle ${8 + i * 2}s ease-in-out infinite`,
              animationDelay: `${i * 1.5}s`,
            }}
          />
        ))}
      </div>

      {/* Login card */}
      <div
        className="relative z-10 w-[380px] rounded-[24px] p-10 flex flex-col items-center"
        style={{
          background: 'rgba(26,26,35,0.82)',
          boxShadow: '0 24px 64px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.04)',
          animation: 'loginEnter 500ms cubic-bezier(0.34, 1.56, 0.64, 1)',
          backdropFilter: 'blur(12px)',
        }}
      >
        {/* Dulus ASCII mini logo */}
        <pre
          className="mb-3 text-[8px] leading-[1.2] font-bold text-center"
          style={{
            color: 'var(--accent-primary)',
            textShadow: '0 0 12px rgba(99,102,241,0.35)',
            fontFamily: "'JetBrains Mono', monospace",
            opacity: 0.9,
          }}
        >
          {DULUS_MINI.join('\n')}
        </pre>

        {/* OS Tagline */}
        <div className="text-center mb-6">
          <h1
            className="text-[13px] font-bold tracking-[0.25em] uppercase"
            style={{ color: 'var(--text-primary)' }}
          >
            Dulus OS
          </h1>
          <p
            className="text-[10px] mt-1 tracking-wider"
            style={{ color: 'var(--text-secondary)' }}
          >
            Intelligent Agent Operating System
          </p>
        </div>

        {/* Avatar */}
        <div
          className="w-[72px] h-[72px] rounded-full flex items-center justify-center border-[2.5px] mb-3"
          style={{
            background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-primary-active))',
            borderColor: 'rgba(99,102,241,0.4)',
            boxShadow: '0 0 24px rgba(99,102,241,0.25)',
          }}
        >
          <User size={32} className="text-white" />
        </div>

        {/* Username selector */}
        <div className="relative mb-5">
          <button
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center gap-1.5 text-sm font-semibold transition-colors"
            style={{ color: 'var(--text-primary)' }}
          >
            {selectedUser}
            <ChevronDown size={14} style={{ color: 'var(--text-secondary)' }} />
          </button>

          {showUserMenu && (
            <div
              className="absolute top-full left-1/2 -translate-x-1/2 mt-2 py-1.5 rounded-xl z-50"
              style={{
                background: 'var(--bg-context-menu)',
                boxShadow: 'var(--shadow-lg)',
                border: '1px solid var(--border-default)',
                width: 160,
                animation: 'menuAppear 120ms cubic-bezier(0, 0, 0.2, 1)',
              }}
            >
              {users.map((u) => (
                <button
                  key={u}
                  onClick={() => {
                    setSelectedUser(u);
                    setShowUserMenu(false);
                  }}
                  className="w-full text-left px-3 py-2 text-sm transition-colors"
                  style={{
                    color: selectedUser === u ? 'var(--accent-primary)' : 'var(--text-primary)',
                    background: selectedUser === u ? 'var(--bg-selected)' : 'transparent',
                  }}
                >
                  {u}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Password input */}
        <div className="w-full relative">
          <input
            type="password"
            value={password}
            onChange={(e) => { setPassword(e.target.value); setError(false); }}
            onKeyDown={handleKeyDown}
            placeholder="Password"
            className="w-full h-11 rounded-xl px-5 text-sm outline-none transition-all"
            style={{
              background: 'var(--bg-input)',
              color: 'var(--text-primary)',
              border: `1px solid ${error ? 'var(--accent-error)' : 'var(--border-default)'}`,
              boxShadow: error ? '0 0 0 3px rgba(248,113,113,0.15)' : undefined,
            }}
            onFocus={(e) => {
              if (!error) e.currentTarget.style.borderColor = 'var(--accent-primary)';
              e.currentTarget.style.boxShadow = '0 0 0 3px rgba(99,102,241,0.12)';
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = error ? 'var(--accent-error)' : 'var(--border-default)';
              e.currentTarget.style.boxShadow = 'none';
            }}
          />
        </div>

        {/* Unlock button */}
        <button
          onClick={handleUnlock}
          disabled={isUnlocking}
          className="w-full h-11 rounded-xl mt-3 text-sm font-semibold text-white transition-all"
          style={{
            background: isUnlocking
              ? 'var(--accent-primary-active)'
              : 'linear-gradient(135deg, var(--accent-primary), var(--accent-primary-active))',
            transform: 'scale(1)',
          }}
          onMouseEnter={(e) => {
            if (!isUnlocking) e.currentTarget.style.background = 'linear-gradient(135deg, var(--accent-primary-hover), var(--accent-primary))';
          }}
          onMouseLeave={(e) => {
            if (!isUnlocking) e.currentTarget.style.background = 'linear-gradient(135deg, var(--accent-primary), var(--accent-primary-active))';
          }}
          onMouseDown={(e) => { e.currentTarget.style.transform = 'scale(0.97)'; }}
          onMouseUp={(e) => { e.currentTarget.style.transform = 'scale(1)'; }}
        >
          {isUnlocking ? (
            <div className="flex items-center justify-center gap-2">
              <div className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
              <span>Unlocking...</span>
            </div>
          ) : (
            'Unlock'
          )}
        </button>

        {/* Guest login */}
        <button
          onClick={handleGuest}
          className="mt-3 text-sm transition-colors"
          style={{ color: 'var(--text-secondary)' }}
          onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--accent-primary-hover)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-secondary)'; }}
        >
          Log in as Guest
        </button>

        {/* Power options */}
        <div
          className="flex items-center gap-3 mt-6 pt-4 w-full justify-center"
          style={{ borderTop: '1px solid var(--border-subtle)' }}
        >
          <button
            className="w-8 h-8 rounded-lg flex items-center justify-center transition-all"
            style={{ color: 'var(--text-secondary)' }}
            onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text-primary)'; e.currentTarget.style.background = 'var(--bg-hover)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-secondary)'; e.currentTarget.style.background = 'transparent'; }}
          >
            <Power size={15} />
          </button>
          <button
            className="w-8 h-8 rounded-lg flex items-center justify-center transition-all"
            style={{ color: 'var(--text-secondary)' }}
            onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text-primary)'; e.currentTarget.style.background = 'var(--bg-hover)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-secondary)'; e.currentTarget.style.background = 'transparent'; }}
          >
            <Moon size={15} />
          </button>
          <button
            className="w-8 h-8 rounded-lg flex items-center justify-center transition-all"
            style={{ color: 'var(--text-secondary)' }}
            onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text-primary)'; e.currentTarget.style.background = 'var(--bg-hover)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-secondary)'; e.currentTarget.style.background = 'transparent'; }}
          >
            <LogOut size={15} />
          </button>
        </div>
      </div>

      <style>{`
        @keyframes loginEnter {
          from { opacity: 0; transform: scale(0.92) translateY(16px); }
          to { opacity: 1; transform: scale(1) translateY(0); }
        }
        @keyframes loginShake {
          0%, 100% { transform: translateX(0); }
          25% { transform: translateX(-8px); }
          50% { transform: translateX(8px); }
          75% { transform: translateX(-8px); }
        }
        @keyframes floatParticle {
          0%, 100% { transform: translateY(0) translateX(0); opacity: 0.3; }
          50% { transform: translateY(-20px) translateX(8px); opacity: 0.7; }
        }
        @keyframes menuAppear {
          from { opacity: 0; transform: scale(0.95) translateY(-4px); }
          to { opacity: 1; transform: scale(1) translateY(0); }
        }
      `}</style>
    </div>
  );
});

export default LoginScreen;

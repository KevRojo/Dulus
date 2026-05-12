// ============================================================
// BootSequence v2 — Dulus OS kernel-style boot with ASCII logo
// ============================================================

import { useEffect, useState, memo } from 'react';
import { getAssetPath } from '@/utils/assets';

const PHASE_LOGO = 0;
const PHASE_KERNEL_LOGS = 1;
const PHASE_TRANSITION = 2;
const PHASE_DESKTOP = 3;
const PHASE_DONE = 4;

/* Dulus ASCII logo — 7 lines */
const DULUS_LOGO = [
  '██████╗ ██╗   ██╗██╗     ██╗   ██╗███████╗',
  '██╔══██╗██║   ██║██║     ██║   ██║██╔════╝',
  '██║  ██║██║   ██║██║     ██║   ██║███████╗',
  '██║  ██║██║   ██║██║     ██║   ██║╚════██║',
  '██████╔╝╚██████╔╝███████╗╚██████╔╝███████║',
  '╚═════╝  ╚═════╝ ╚══════╝ ╚═════╝ ╚══════╝',
];

const KERNEL_MESSAGES = [
  '[ OK ] Booting Dulus Kernel v2.0.1...',
  '[ OK ] Loading microcode: 0x0001a3f...',
  '[ OK ] Initializing memory subsystems...',
  '[ OK ] Mounting virtual filesystem (vfs)...',
  '[ OK ] Starting Dulus Agent Daemon...',
  '[ OK ] Loading skills registry: 12 modules...',
  '[ OK ] Connecting to backend bridge...',
  '[ OK ] Initializing window compositor...',
  '[ OK ] Loading user profile: KevRojo...',
  '[ OK ] Starting desktop environment...',
];

const BootSequence = memo(function BootSequence({ onComplete }: { onComplete: () => void }) {
  const [phase, setPhase] = useState<number>(PHASE_LOGO);
  const [progress, setProgress] = useState(0);
  const [visibleLogs, setVisibleLogs] = useState<number>(0);
  const [logoOpacity, setLogoOpacity] = useState(0);

  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = [];

    // Phase 0 → 1: Logo fade in, then start kernel logs
    timers.push(
      setTimeout(() => {
        setLogoOpacity(1);
      }, 200)
    );

    timers.push(
      setTimeout(() => {
        setPhase(PHASE_KERNEL_LOGS);
      }, 1400)
    );

    // Kernel log typing effect
    timers.push(
      setTimeout(() => {
        let logIdx = 0;
        const logInterval = setInterval(() => {
          logIdx += 1;
          if (logIdx >= KERNEL_MESSAGES.length) {
            clearInterval(logInterval);
          }
          setVisibleLogs(logIdx);
        }, 180);
        timers.push(logInterval as unknown as ReturnType<typeof setTimeout>);
      }, 1400)
    );

    // Progress bar fills during kernel logs
    timers.push(
      setTimeout(() => {
        let p = 0;
        const interval = setInterval(() => {
          p += Math.random() * 12 + 4;
          if (p >= 100) {
            p = 100;
            clearInterval(interval);
          }
          setProgress(p);
        }, 100);
        timers.push(interval as unknown as ReturnType<typeof setTimeout>);
      }, 1400)
    );

    timers.push(
      setTimeout(() => {
        setPhase(PHASE_TRANSITION);
      }, 3800)
    );

    timers.push(
      setTimeout(() => {
        setPhase(PHASE_DESKTOP);
      }, 4600)
    );

    timers.push(
      setTimeout(() => {
        setPhase(PHASE_DONE);
        onComplete();
      }, 5400)
    );

    return () => timers.forEach((t) => clearTimeout(t));
  }, [onComplete]);

  if (phase === PHASE_DONE) return null;

  const showContent = phase === PHASE_LOGO || phase === PHASE_KERNEL_LOGS || phase === PHASE_TRANSITION;

  return (
    <div
      className="fixed inset-0 z-[9999] flex flex-col items-center justify-center bg-black font-mono"
      style={{
        transition: 'clip-path 800ms cubic-bezier(0, 0, 0.2, 1)',
        pointerEvents: phase >= PHASE_TRANSITION ? 'none' : 'auto',
        clipPath:
          phase === PHASE_DESKTOP || phase === PHASE_TRANSITION
            ? phase === PHASE_DESKTOP
              ? 'circle(150% at 50% 50%)'
              : 'circle(0% at 50% 50%)'
            : undefined,
      }}
    >
      {phase === PHASE_TRANSITION && (
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{ backgroundImage: `url(${getAssetPath('/wallpapers/default.jpeg')})` }}
        />
      )}

      {showContent && (
        <div
          className="flex flex-col items-center justify-center relative z-10 w-full max-w-2xl px-6"
          style={{
            opacity: phase === PHASE_TRANSITION ? 0 : 1,
            transition: 'opacity 400ms ease',
          }}
        >
          {/* ASCII Logo */}
          <div
            className="mb-6 text-center"
            style={{
              opacity: logoOpacity,
              transform: `scale(${logoOpacity ? 1 : 0.95})`,
              transition: 'all 700ms cubic-bezier(0.34, 1.56, 0.64, 1)',
            }}
          >
            <pre
              className="text-[10px] sm:text-xs leading-[1.15] font-bold"
              style={{
                color: 'var(--accent-primary)',
                textShadow: '0 0 20px rgba(99,102,241,0.4)',
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              {DULUS_LOGO.join('\n')}
            </pre>
            <div
              className="mt-3 text-[10px] tracking-[0.3em] uppercase"
              style={{ color: 'var(--text-secondary)' }}
            >
              Operating System v2.0
            </div>
          </div>

          {/* Kernel Logs */}
          {phase >= PHASE_KERNEL_LOGS && (
            <div
              className="w-full mb-4 h-32 overflow-hidden"
              style={{
                opacity: phase >= PHASE_KERNEL_LOGS ? 1 : 0,
                transition: 'opacity 300ms ease',
              }}
            >
              <div className="flex flex-col gap-0.5">
                {KERNEL_MESSAGES.slice(0, visibleLogs).map((msg, i) => (
                  <div
                    key={i}
                    className="text-[10px] sm:text-[11px] font-mono truncate"
                    style={{
                      color: msg.includes('OK') ? '#34D399' : '#8E8EA0',
                      opacity: 0,
                      animation: 'logAppear 150ms ease forwards',
                      animationDelay: `${i * 30}ms`,
                    }}
                  >
                    {msg}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Progress bar */}
          {phase >= PHASE_KERNEL_LOGS && (
            <div className="w-full max-w-xs">
              <div
                className="w-full h-[2px] rounded-full overflow-hidden mb-2"
                style={{ background: 'rgba(99,102,241,0.15)' }}
              >
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${progress}%`,
                    background: 'linear-gradient(90deg, var(--accent-primary), var(--accent-secondary))',
                    transition: 'width 100ms linear',
                    boxShadow: '0 0 8px rgba(99,102,241,0.5)',
                  }}
                />
              </div>
              <div className="flex justify-between text-[10px]" style={{ color: 'var(--text-secondary)' }}>
                <span>{Math.floor(progress)}%</span>
                <span>{progress >= 100 ? 'Done' : 'Loading...'}</span>
              </div>
            </div>
          )}
        </div>
      )}

      <style>{`
        @keyframes logAppear {
          from { opacity: 0; transform: translateX(-8px); }
          to { opacity: 1; transform: translateX(0); }
        }
      `}</style>
    </div>
  );
});

export default BootSequence;

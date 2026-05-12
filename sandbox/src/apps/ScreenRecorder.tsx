// ============================================================
// Screen Recorder — Record screen with preview and controls
// ============================================================

import { useState, useRef, useEffect, memo } from 'react';
import {
  Monitor, AppWindow, Square, Play, Pause, Video, Download, Trash2, Circle
} from 'lucide-react';

// ---- Types ----
type RecordMode = 'screen' | 'window' | 'area';
type RecordQuality = 'low' | 'medium' | 'high';
type RecorderState = 'idle' | 'countdown' | 'recording' | 'paused';

interface ScreenRecording {
  id: string;
  name: string;
  duration: number;
  size: string;
  date: number;
  mode: RecordMode;
}

// ---- Helpers ----
const formatTime = (seconds: number): string => {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
};

const formatFileSize = (seconds: number, quality: RecordQuality): string => {
  const mbPerMin = quality === 'low' ? 20 : quality === 'medium' ? 50 : 120;
  const mb = Math.round((seconds / 60) * mbPerMin);
  if (mb < 1024) return `${mb} MB`;
  return `${(mb / 1024).toFixed(1)} GB`;
};

// ---- Countdown Overlay ----
const CountdownOverlay = memo(function CountdownOverlay({ count, onComplete }: { count: number; onComplete: () => void }) {
  const [current, setCurrent] = useState(count);

  useEffect(() => {
    if (current <= 0) { onComplete(); return; }
    const timer = setTimeout(() => setCurrent((c) => c - 1), 800);
    return () => clearTimeout(timer);
  }, [current, count, onComplete]);

  if (current <= 0) return null;

  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}>
      <span
        className="font-bold"
        style={{
          fontSize: '96px',
          color: 'white',
          animation: 'scaleIn 0.8s ease-out',
          textShadow: '0 4px 20px rgba(0,0,0,0.5)',
        }}
      >
        {current}
      </span>
    </div>
  );
});

// ---- REC Indicator ----
const RecIndicator = memo(function RecIndicator() {
  return (
    <div className="flex items-center gap-1.5 px-2 py-1 rounded-full" style={{ background: 'rgba(244,67,54,0.15)' }}>
      <div className="w-2.5 h-2.5 rounded-full animate-pulse" style={{ background: 'var(--accent-error)' }} />
      <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--accent-error)' }}>REC</span>
    </div>
  );
});

// ---- Mode Selector ----
const ModeButton = memo(function ModeButton({ mode, activeMode, icon: Icon, label, onClick }: {
  mode: RecordMode; activeMode: RecordMode; icon: typeof Monitor; label: string; onClick: () => void;
}) {
  const isActive = mode === activeMode;
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 px-4 py-2 rounded-lg transition-all"
      style={{
        background: isActive ? 'var(--accent-primary)' : 'var(--bg-hover)',
        color: isActive ? 'white' : 'var(--text-secondary)',
        fontSize: '13px',
        fontWeight: 500,
      }}
    >
      <Icon size={16} />
      {label}
    </button>
  );
});

// ---- Main Screen Recorder ----
export default function ScreenRecorder() {
  const [recorderState, setRecorderState] = useState<RecorderState>('idle');
  const [recordMode, setRecordMode] = useState<RecordMode>('screen');
  const [quality, setQuality] = useState<RecordQuality>('high');
  const [fps, setFps] = useState(30);
  const [recordAudio, setRecordAudio] = useState(true);
  const [showCursor, setShowCursor] = useState(true);
  const [countdownEnabled, setCountdownEnabled] = useState(true);
  const [countdownSeconds, setCountdownSeconds] = useState(3);
  const [elapsed, setElapsed] = useState(0);
  const [showCountdown, setShowCountdown] = useState(false);
  const [recordings, setRecordings] = useState<ScreenRecording[]>(() => {
    try {
      const saved = localStorage.getItem('dulus_screenrecordings');
      return saved ? JSON.parse(saved) : [];
    } catch { return []; }
  });
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Persist recordings
  useEffect(() => {
    localStorage.setItem('dulus_screenrecordings', JSON.stringify(recordings));
  }, [recordings]);

  // Recording timer
  useEffect(() => {
    if (recorderState === 'recording') {
      timerRef.current = setInterval(() => {
        setElapsed((prev) => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [recorderState]);

  const startRecording = () => {
    if (countdownEnabled) {
      setShowCountdown(true);
      setRecorderState('countdown');
    } else {
      beginRecording();
    }
  };

  const beginRecording = () => {
    setRecorderState('recording');
    setElapsed(0);
    setShowCountdown(false);
  };

  const pauseRecording = () => {
    setRecorderState('paused');
  };

  const resumeRecording = () => {
    setRecorderState('recording');
  };

  const stopRecording = () => {
    if (elapsed > 0) {
      const newRecording: ScreenRecording = {
        id: Math.random().toString(36).slice(2),
        name: `Screen Recording ${recordings.length + 1}`,
        duration: elapsed,
        size: formatFileSize(elapsed, quality),
        date: Date.now(),
        mode: recordMode,
      };
      setRecordings((prev) => [newRecording, ...prev]);
    }
    setRecorderState('idle');
    setElapsed(0);
  };

  const deleteRecording = (id: string) => {
    setRecordings((prev) => prev.filter((r) => r.id !== id));
  };

  const downloadRecording = (recording: ScreenRecording) => {
    const blob = new Blob([`Simulated screen recording: ${recording.name}\nDuration: ${formatTime(recording.duration)}\nMode: ${recording.mode}\nQuality: ${quality}`], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${recording.name}.webm`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const modeDescriptions: Record<RecordMode, string> = {
    screen: 'Will record your entire screen',
    window: 'Will record a specific application window',
    area: 'Will record a selected area of the screen',
  };

  return (
    <div className="flex flex-col h-full custom-scrollbar overflow-y-auto" style={{ background: 'var(--bg-window)' }}>
      {/* Countdown Overlay */}
      {showCountdown && recorderState === 'countdown' && (
        <CountdownOverlay count={countdownSeconds} onComplete={beginRecording} />
      )}

      {/* Mode Selection */}
      <div className="px-4 pt-4 pb-3">
        <h3 style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>Recording Mode</h3>
        <div className="flex gap-2">
          <ModeButton mode="screen" activeMode={recordMode} icon={Monitor} label="Full Screen" onClick={() => setRecordMode('screen')} />
          <ModeButton mode="window" activeMode={recordMode} icon={AppWindow} label="Window" onClick={() => setRecordMode('window')} />
          <ModeButton mode="area" activeMode={recordMode} icon={Square} label="Area" onClick={() => setRecordMode('area')} />
        </div>
      </div>

      {/* Settings */}
      <div className="px-4 py-3" style={{ borderTop: '1px solid var(--border-subtle)' }}>
        <h3 style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '10px' }}>Settings</h3>
        <div className="grid grid-cols-2 gap-3">
          {/* Quality */}
          <div>
            <label style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Quality</label>
            <select
              value={quality}
              onChange={(e) => setQuality(e.target.value as RecordQuality)}
              className="w-full px-2 py-1.5 rounded-md outline-none"
              style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', fontSize: '12px' }}
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </div>
          {/* FPS */}
          <div>
            <label style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>FPS</label>
            <select
              value={fps}
              onChange={(e) => setFps(Number(e.target.value))}
              className="w-full px-2 py-1.5 rounded-md outline-none"
              style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', fontSize: '12px' }}
            >
              <option value={15}>15 fps</option>
              <option value={30}>30 fps</option>
              <option value={60}>60 fps</option>
            </select>
          </div>
        </div>

        <div className="flex flex-col gap-2 mt-3">
          <Toggle label="Record Audio" value={recordAudio} onChange={setRecordAudio} />
          <Toggle label="Show Cursor" value={showCursor} onChange={setShowCursor} />
          <Toggle label="Countdown" value={countdownEnabled} onChange={setCountdownEnabled} />
          {countdownEnabled && (
            <input
              type="range"
              min={1}
              max={10}
              value={countdownSeconds}
              onChange={(e) => setCountdownSeconds(Number(e.target.value))}
              className="ml-5"
              style={{ accentColor: 'var(--accent-primary)', width: 120 }}
            />
          )}
        </div>
      </div>

      {/* Preview Area */}
      <div className="px-4 py-3" style={{ borderTop: '1px solid var(--border-subtle)' }}>
        <div
          className="flex flex-col items-center justify-center gap-2 rounded-lg"
          style={{
            height: 160,
            background: 'var(--bg-titlebar)',
            border: '2px dashed var(--border-default)',
          }}
        >
          {recorderState === 'recording' ? (
            <div className="flex flex-col items-center gap-3">
              <RecIndicator />
              <div className="flex items-center gap-4">
                <Monitor size={48} style={{ color: 'var(--accent-error)', opacity: 0.5 }} />
                <div>
                  <div style={{ fontSize: '24px', fontWeight: 300, color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>
                    {formatTime(elapsed)}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Recording {recordMode}...</div>
                </div>
              </div>
            </div>
          ) : (
            <>
              <Monitor size={36} style={{ color: 'var(--text-disabled)' }} />
              <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{modeDescriptions[recordMode]}</span>
            </>
          )}
        </div>
      </div>

      {/* Record Button */}
      <div className="px-4 py-3">
        {recorderState === 'idle' ? (
          <button
            onClick={startRecording}
            className="w-full flex items-center justify-center gap-2 transition-all hover:opacity-90"
            style={{ height: 48, borderRadius: 'var(--radius-md)', background: 'var(--accent-error)', color: 'white', fontSize: '14px', fontWeight: 600 }}
          >
            <Circle size={18} fill="white" /> Start Recording
          </button>
        ) : recorderState === 'recording' ? (
          <div className="flex gap-2">
            <button
              onClick={pauseRecording}
              className="flex-1 flex items-center justify-center gap-2 transition-all hover:opacity-90"
              style={{ height: 48, borderRadius: 'var(--radius-md)', background: 'var(--bg-hover)', color: 'var(--text-primary)', fontSize: '14px', fontWeight: 600, border: '1px solid var(--border-default)' }}
            >
              <Pause size={18} /> Pause
            </button>
            <button
              onClick={stopRecording}
              className="flex-[2] flex items-center justify-center gap-2 transition-all hover:opacity-90"
              style={{ height: 48, borderRadius: 'var(--radius-md)', background: 'var(--accent-error)', color: 'white', fontSize: '14px', fontWeight: 600 }}
            >
              <Square size={18} fill="white" /> Stop Recording
            </button>
          </div>
        ) : recorderState === 'paused' ? (
          <div className="flex gap-2">
            <button
              onClick={resumeRecording}
              className="flex-1 flex items-center justify-center gap-2 transition-all hover:opacity-90"
              style={{ height: 48, borderRadius: 'var(--radius-md)', background: 'var(--accent-primary)', color: 'white', fontSize: '14px', fontWeight: 600 }}
            >
              <Play size={18} className="ml-0.5" /> Resume
            </button>
            <button
              onClick={stopRecording}
              className="flex-1 flex items-center justify-center gap-2 transition-all hover:opacity-90"
              style={{ height: 48, borderRadius: 'var(--radius-md)', background: 'var(--accent-error)', color: 'white', fontSize: '14px', fontWeight: 600 }}
            >
              <Square size={18} fill="white" /> Stop
            </button>
          </div>
        ) : null}
      </div>

      {/* Recordings List */}
      <div className="flex-1 overflow-y-auto custom-scrollbar px-4" style={{ borderTop: '1px solid var(--border-subtle)' }}>
        <h3 style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.05em', padding: '12px 0 8px' }}>
          Recent Recordings ({recordings.length})
        </h3>
        {recordings.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 gap-2">
            <Video size={28} style={{ color: 'var(--text-disabled)' }} />
            <span style={{ fontSize: '12px', color: 'var(--text-disabled)' }}>No recordings yet</span>
          </div>
        ) : (
          recordings.map((recording) => (
            <div
              key={recording.id}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg mb-1 transition-all"
              style={{ background: 'var(--bg-titlebar)', border: '1px solid var(--border-subtle)' }}
            >
              <div className="flex items-center justify-center rounded-lg shrink-0" style={{ width: 40, height: 28, background: 'var(--bg-hover)' }}>
                <Video size={14} style={{ color: 'var(--accent-primary)' }} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="truncate" style={{ fontSize: '13px', color: 'var(--text-primary)' }}>{recording.name}</div>
                <div className="flex items-center gap-2">
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{formatTime(recording.duration)}</span>
                  <span style={{ fontSize: '11px', color: 'var(--text-disabled)' }}>{recording.size}</span>
                  <span style={{ fontSize: '10px', color: 'var(--text-disabled)', textTransform: 'capitalize' }}>{recording.mode}</span>
                </div>
              </div>
              <button
                onClick={() => downloadRecording(recording)}
                className="flex items-center justify-center rounded hover:bg-[var(--bg-hover)] shrink-0"
                style={{ width: 28, height: 28 }}
              >
                <Download size={14} style={{ color: 'var(--text-secondary)' }} />
              </button>
              <button
                onClick={() => deleteRecording(recording.id)}
                className="flex items-center justify-center rounded hover:bg-[var(--bg-hover)] shrink-0"
                style={{ width: 28, height: 28 }}
              >
                <Trash2 size={14} style={{ color: 'var(--text-secondary)' }} />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ---- Toggle Component ----
function Toggle({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer">
      <button
        onClick={() => onChange(!value)}
        className="relative transition-all"
        style={{
          width: 36, height: 20, borderRadius: 10,
          background: value ? 'var(--accent-primary)' : 'var(--border-default)',
        }}
      >
        <div
          className="absolute top-0.5 transition-all"
          style={{
            width: 16, height: 16, borderRadius: '50%', background: 'white',
            left: value ? 18 : 2,
          }}
        />
      </button>
      <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{label}</span>
    </label>
  );
}

// ============================================================
// Voice Recorder — Record, playback, waveform visualization
// ============================================================

import { useState, useRef, useEffect, memo } from 'react';
import {
  Mic, Play, Pause, Square, Trash2, Download
} from 'lucide-react';

// ---- Types ----
interface Recording {
  id: string;
  name: string;
  duration: number;
  date: number;
  waveformData: number[];
}

type RecorderState = 'idle' | 'recording' | 'paused' | 'playing';

// ---- Waveform Visualizer ----
const WaveformVisualizer = memo(function WaveformVisualizer({ isActive, isPlaying, waveformData }: { isActive: boolean; isPlaying?: boolean; waveformData?: number[] }) {
  const [bars, setBars] = useState<number[]>(Array(40).fill(4));

  useEffect(() => {
    if (!isActive) {
      if (waveformData && isPlaying) {
        // Replay the recorded waveform
        setBars(waveformData);
      } else {
        setBars(Array(40).fill(4));
      }
      return;
    }

    const interval = setInterval(() => {
      setBars(Array.from({ length: 40 }, () => Math.random() * 60 + 8));
    }, 80);
    return () => clearInterval(interval);
  }, [isActive, isPlaying, waveformData]);

  return (
    <div className="flex items-end justify-center gap-1" style={{ height: 80 }}>
      {bars.map((h, i) => (
        <div
          key={i}
          className="rounded-full transition-all"
          style={{
            width: 4,
            height: h,
            background: isPlaying
              ? 'linear-gradient(to top, var(--accent-primary), var(--accent-primary-hover))'
              : 'linear-gradient(to top, #4CAF50, #81C784)',
            opacity: 0.5 + (i / 40) * 0.5,
          }}
        />
      ))}
    </div>
  );
});

// ---- Audio Level Meter ----
const AudioLevelMeter = memo(function AudioLevelMeter({ isRecording }: { isRecording: boolean }) {
  const [level, setLevel] = useState(0);

  useEffect(() => {
    if (!isRecording) { setLevel(0); return; }
    const interval = setInterval(() => {
      setLevel(Math.random() * 100);
    }, 50);
    return () => clearInterval(interval);
  }, [isRecording]);

  return (
    <div className="flex items-center gap-0.5" style={{ height: 24 }}>
      {Array.from({ length: 20 }).map((_, i) => (
        <div
          key={i}
          className="rounded-full transition-all"
          style={{
            width: 3,
            height: Math.min(24, Math.max(4, (level / 100) * 24 * (i / 20))),
            background: level > 80 ? 'var(--accent-error)' : level > 50 ? 'var(--accent-warning)' : 'var(--accent-success)',
          }}
        />
      ))}
    </div>
  );
});

// ---- Helpers ----
const formatTime = (seconds: number): string => {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
};

const generateWaveform = () => Array.from({ length: 40 }, () => Math.random() * 60 + 8);

// ---- Main Voice Recorder ----
export default function VoiceRecorder() {
  const [recorderState, setRecorderState] = useState<RecorderState>('idle');
  const [elapsed, setElapsed] = useState(0);
  const [recordings, setRecordings] = useState<Recording[]>(() => {
    try {
      const saved = localStorage.getItem('dulus_recordings');
      return saved ? JSON.parse(saved) : [];
    } catch { return []; }
    });
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [playTime, setPlayTime] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const playTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Persist recordings
  useEffect(() => {
    localStorage.setItem('dulus_recordings', JSON.stringify(recordings));
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

  // Playback timer
  useEffect(() => {
    if (recorderState === 'playing' && playingId) {
      const recording = recordings.find((r) => r.id === playingId);
      if (!recording) return;
      playTimerRef.current = setInterval(() => {
        setPlayTime((prev) => {
          if (prev >= recording.duration) {
            setRecorderState('idle');
            setPlayingId(null);
            return 0;
          }
          return prev + 1;
        });
      }, 1000);
    }
    return () => { if (playTimerRef.current) clearInterval(playTimerRef.current); };
  }, [recorderState, playingId, recordings]);

  const startRecording = () => {
    setRecorderState('recording');
    setElapsed(0);
  };

  const pauseRecording = () => {
    setRecorderState('paused');
  };

  const resumeRecording = () => {
    setRecorderState('recording');
  };

  const stopRecording = () => {
    if (elapsed > 0) {
      const newRecording: Recording = {
        id: Math.random().toString(36).slice(2),
        name: `Recording ${recordings.length + 1}`,
        duration: elapsed,
        date: Date.now(),
        waveformData: generateWaveform(),
      };
      setRecordings((prev) => [newRecording, ...prev]);
    }
    setRecorderState('idle');
    setElapsed(0);
  };

  const playRecording = (recording: Recording) => {
    if (playingId === recording.id && recorderState === 'playing') {
      setRecorderState('idle');
      setPlayingId(null);
      setPlayTime(0);
    } else {
      setPlayingId(recording.id);
      setRecorderState('playing');
      setPlayTime(0);
    }
  };

  const deleteRecording = (id: string) => {
    setRecordings((prev) => prev.filter((r) => r.id !== id));
    if (playingId === id) {
      setPlayingId(null);
      setRecorderState('idle');
      setPlayTime(0);
    }
  };

  const downloadRecording = (recording: Recording) => {
    // Simulated download - create a text blob as placeholder
    const blob = new Blob([`Simulated audio recording: ${recording.name}\nDuration: ${formatTime(recording.duration)}`], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${recording.name}.webm`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const statusLabel = recorderState === 'idle' ? 'Ready to record' :
    recorderState === 'recording' ? 'Recording...' :
    recorderState === 'paused' ? 'Paused' :
    'Playing';

  const currentWaveform = playingId ? recordings.find((r) => r.id === playingId)?.waveformData : undefined;

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-window)' }}>
      {/* Visualizer Area */}
      <div
        className="flex flex-col items-center justify-center gap-4 px-6 py-5 shrink-0"
        style={{ background: 'var(--bg-titlebar)', borderBottom: '1px solid var(--border-subtle)' }}
      >
        <WaveformVisualizer
          isActive={recorderState === 'recording'}
          isPlaying={recorderState === 'playing'}
          waveformData={currentWaveform}
        />

        {/* Audio Level Meter */}
        {recorderState === 'recording' && <AudioLevelMeter isRecording={true} />}

        {/* Timer */}
        <div style={{ fontSize: '36px', fontWeight: 300, color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>
          {formatTime(recorderState === 'playing' ? playTime : elapsed)}
        </div>

        {/* Status */}
        <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
          {statusLabel}
          {recorderState === 'recording' && (
            <span className="inline-flex items-center gap-1.5 ml-2">
              <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: 'var(--accent-error)' }} />
              <span style={{ fontSize: '11px', color: 'var(--accent-error)' }}>REC</span>
            </span>
          )}
        </div>

        {/* Controls */}
        <div className="flex items-center gap-4">
          {recorderState === 'idle' ? (
            <button
              onClick={startRecording}
              className="flex items-center justify-center rounded-full transition-all hover:scale-105"
              style={{
                width: 64, height: 64,
                background: 'var(--accent-error)', color: 'white',
                boxShadow: '0 0 20px rgba(244,67,54,0.3)',
              }}
            >
              <Mic size={28} />
            </button>
          ) : recorderState === 'recording' ? (
            <>
              <button
                onClick={pauseRecording}
                className="flex items-center justify-center rounded-full transition-all hover:scale-105"
                style={{ width: 48, height: 48, background: 'var(--bg-hover)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }}
              >
                <Pause size={20} />
              </button>
              <button
                onClick={stopRecording}
                className="flex items-center justify-center rounded-full transition-all hover:scale-105"
                style={{
                  width: 64, height: 64,
                  background: 'var(--accent-error)', color: 'white',
                  animation: 'pulse 1s infinite',
                }}
              >
                <Square size={24} />
              </button>
            </>
          ) : recorderState === 'paused' ? (
            <>
              <button
                onClick={resumeRecording}
                className="flex items-center justify-center rounded-full transition-all hover:scale-105"
                style={{ width: 48, height: 48, background: 'var(--accent-primary)', color: 'white' }}
              >
                <Play size={20} className="ml-0.5" />
              </button>
              <button
                onClick={stopRecording}
                className="flex items-center justify-center rounded-full transition-all hover:scale-105"
                style={{ width: 64, height: 64, background: 'var(--accent-error)', color: 'white' }}
              >
                <Square size={24} />
              </button>
            </>
          ) : (
            <button
              onClick={() => { setRecorderState('idle'); setPlayingId(null); setPlayTime(0); }}
              className="flex items-center justify-center rounded-full transition-all hover:scale-105"
              style={{ width: 48, height: 48, background: 'var(--accent-error)', color: 'white' }}
            >
              <Square size={20} />
            </button>
          )}
        </div>
      </div>

      {/* Recordings List */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {recordings.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-2">
            <Mic size={32} style={{ color: 'var(--text-disabled)' }} />
            <span style={{ fontSize: '12px', color: 'var(--text-disabled)' }}>No recordings yet</span>
          </div>
        ) : (
          recordings.map((recording) => (
            <div
              key={recording.id}
              className="flex items-center gap-3 px-4 py-3 transition-all"
              style={{ borderBottom: '1px solid var(--border-subtle)' }}
            >
              <button
                onClick={() => playRecording(recording)}
                className="flex items-center justify-center rounded-full transition-all shrink-0"
                style={{
                  width: 36, height: 36,
                  background: playingId === recording.id && recorderState === 'playing' ? 'var(--accent-primary)' : 'var(--bg-hover)',
                  color: playingId === recording.id && recorderState === 'playing' ? 'white' : 'var(--text-secondary)',
                }}
              >
                {playingId === recording.id && recorderState === 'playing' ? <Pause size={16} /> : <Play size={16} className="ml-0.5" />}
              </button>

              <div className="flex-1 min-w-0">
                <div className="truncate" style={{ fontSize: '13px', color: 'var(--text-primary)' }}>{recording.name}</div>
                <div className="flex items-center gap-2">
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{formatTime(recording.duration)}</span>
                  <span style={{ fontSize: '11px', color: 'var(--text-disabled)' }}>{new Date(recording.date).toLocaleDateString()}</span>
                </div>
                {/* Mini waveform */}
                {playingId === recording.id && recorderState === 'playing' && (
                  <div className="flex items-end gap-px mt-1" style={{ height: 16 }}>
                    {recording.waveformData.slice(0, 30).map((h, i) => (
                      <div
                        key={i}
                        className="rounded-full"
                        style={{ width: 2, height: Math.max(2, h * 0.25), background: 'var(--accent-primary)', opacity: 0.6 }}
                      />
                    ))}
                  </div>
                )}
              </div>

              <button
                onClick={() => downloadRecording(recording)}
                className="flex items-center justify-center rounded-lg hover:bg-[var(--bg-hover)] shrink-0"
                style={{ width: 28, height: 28 }}
              >
                <Download size={14} style={{ color: 'var(--text-secondary)' }} />
              </button>
              <button
                onClick={() => deleteRecording(recording.id)}
                className="flex items-center justify-center rounded-lg hover:bg-[var(--bg-hover)] shrink-0"
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

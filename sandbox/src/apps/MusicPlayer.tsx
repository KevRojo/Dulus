// ============================================================
// Music Player — Audio player with playlist and visualizer
// ============================================================

import { useState, useRef, useEffect, useCallback, memo } from 'react';
import {
  Play, Pause, SkipBack, SkipForward, Shuffle, Repeat, Repeat1, Volume2, VolumeX, ListMusic, Music
} from 'lucide-react';

// ---- Types ----
interface Track {
  id: string;
  title: string;
  artist: string;
  album: string;
  duration: number; // seconds
}

// ---- Demo Tracks ----
const DEMO_TRACKS: Track[] = [
  { id: '1', title: 'Midnight Drive', artist: 'Neon Horizons', album: 'Night Moves', duration: 222 },
  { id: '2', title: 'Electric Dreams', artist: 'Purple Rain', album: 'Synthwave Vol.1', duration: 255 },
  { id: '3', title: 'Urban Sunrise', artist: 'City Lights', album: 'Metropolitan', duration: 208 },
  { id: '4', title: 'Deep Focus', artist: 'Ambient Works', album: 'Flow State', duration: 301 },
  { id: '5', title: 'Summer Breeze', artist: 'Chill Wave', album: 'Coastal Vibes', duration: 235 },
  { id: '6', title: 'Digital Frontier', artist: 'Synth Masters', album: 'Cyberpunk', duration: 273 },
  { id: '7', title: 'Ocean Waves', artist: 'Nature Sounds', album: 'Serenity', duration: 372 },
  { id: '8', title: 'Night Crawler', artist: 'Bass Collective', album: 'Underground', duration: 198 },
];

// ---- Visualizer Bars ----
const VisualizerBars = memo(function VisualizerBars({ isPlaying }: { isPlaying: boolean }) {
  const [bars, setBars] = useState<number[]>(Array(32).fill(4));

  useEffect(() => {
    if (!isPlaying) {
      setBars(Array(32).fill(4));
      return;
    }
    const interval = setInterval(() => {
      setBars(Array.from({ length: 32 }, () => Math.random() * 40 + 4));
    }, 100);
    return () => clearInterval(interval);
  }, [isPlaying]);

  return (
    <div className="flex items-end justify-center gap-[2px]" style={{ height: 50 }}>
      {bars.map((h, i) => (
        <div
          key={i}
          className="rounded-full transition-all"
          style={{
            width: 4,
            height: h,
            background: `linear-gradient(to top, var(--accent-primary), var(--accent-secondary))`,
            opacity: 0.6 + (i / 32) * 0.4,
          }}
        />
      ))}
    </div>
  );
});

// ---- Helpers ----
const formatTime = (seconds: number): string => {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
};

// ---- Main Music Player ----
export default function MusicPlayer() {
  const [tracks] = useState<Track[]>(DEMO_TRACKS);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [volume, setVolume] = useState(0.7);
  const [isShuffle, setIsShuffle] = useState(false);
  const [repeatMode, setRepeatMode] = useState<'off' | 'one' | 'all'>('off');
  const [showPlaylist, setShowPlaylist] = useState(false);
  const progressInterval = useRef<ReturnType<typeof setInterval> | null>(null);

  const currentTrack = tracks[currentIndex];

  // Simulated playback timer
  useEffect(() => {
    if (isPlaying) {
      progressInterval.current = setInterval(() => {
        setCurrentTime((prev) => {
          if (prev >= currentTrack.duration) {
            handleNext();
            return 0;
          }
          return prev + 1;
        });
      }, 1000);
    }
    return () => {
      if (progressInterval.current) clearInterval(progressInterval.current);
    };
  }, [isPlaying, currentTrack]);

  const handlePlayPause = useCallback(() => setIsPlaying((p) => !p), []);

  const handleNext = useCallback(() => {
    if (isShuffle) {
      setCurrentIndex(Math.floor(Math.random() * tracks.length));
    } else {
      setCurrentIndex((prev) => (prev + 1) % tracks.length);
    }
    setCurrentTime(0);
    setIsPlaying(true);
  }, [isShuffle, tracks.length]);

  const handlePrev = useCallback(() => {
    if (currentTime > 3) {
      setCurrentTime(0);
    } else {
      setCurrentIndex((prev) => (prev - 1 + tracks.length) % tracks.length);
      setCurrentTime(0);
    }
    setIsPlaying(true);
  }, [currentTime, tracks.length]);

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCurrentTime(Number(e.target.value));
  };

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setVolume(Number(e.target.value));
  };

  const toggleRepeat = () => {
    setRepeatMode((prev) => prev === 'off' ? 'all' : prev === 'all' ? 'one' : 'off');
  };

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.code === 'Space' && e.target === document.body) {
        e.preventDefault();
        setIsPlaying((p) => !p);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return (
    <div className="flex flex-col h-full relative overflow-hidden" style={{ background: 'var(--bg-window)' }}>
      {/* Album Art Area */}
      <div className="flex flex-col items-center pt-6 pb-4">
        {/* Album Art */}
        <div
          className="flex items-center justify-center rounded-xl mb-4 transition-transform"
          style={{
            width: 200, height: 200,
            background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))',
            boxShadow: 'var(--shadow-lg)',
            animation: isPlaying ? 'pulse 2s infinite' : 'none',
          }}
        >
          <Music size={80} style={{ color: 'rgba(255,255,255,0.3)' }} />
        </div>

        {/* Track Info */}
        <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '4px' }}>
          {currentTrack.title}
        </h2>
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '2px' }}>
          {currentTrack.artist}
        </p>
        <p style={{ fontSize: '11px', color: 'var(--text-disabled)', marginTop: '1px' }}>
          {currentTrack.album}
        </p>
      </div>

      {/* Visualizer */}
      <div className="px-6 mb-2">
        <VisualizerBars isPlaying={isPlaying} />
      </div>

      {/* Progress Bar */}
      <div className="px-6 mb-2">
        <input
          type="range"
          min={0}
          max={currentTrack.duration}
          value={currentTime}
          onChange={handleSeek}
          className="w-full"
          style={{
            accentColor: 'var(--accent-primary)',
            height: 4,
          }}
        />
        <div className="flex justify-between mt-1">
          <span style={{ fontSize: '11px', color: 'var(--text-disabled)' }}>{formatTime(currentTime)}</span>
          <span style={{ fontSize: '11px', color: 'var(--text-disabled)' }}>{formatTime(currentTrack.duration)}</span>
        </div>
      </div>

      {/* Controls Row */}
      <div className="flex items-center justify-center gap-5 px-6 py-2">
        <button
          onClick={() => setIsShuffle((s) => !s)}
          className="transition-all hover:scale-110"
          style={{ color: isShuffle ? 'var(--accent-primary)' : 'var(--text-secondary)' }}
        >
          <Shuffle size={20} />
        </button>
        <button onClick={handlePrev} className="transition-all hover:scale-110" style={{ color: 'var(--text-primary)' }}>
          <SkipBack size={28} />
        </button>
        <button
          onClick={handlePlayPause}
          className="flex items-center justify-center rounded-full transition-all hover:scale-105"
          style={{
            width: 56, height: 56,
            background: 'var(--accent-primary)', color: 'white',
          }}
        >
          {isPlaying ? <Pause size={24} /> : <Play size={24} className="ml-0.5" />}
        </button>
        <button onClick={handleNext} className="transition-all hover:scale-110" style={{ color: 'var(--text-primary)' }}>
          <SkipForward size={28} />
        </button>
        <button
          onClick={toggleRepeat}
          className="transition-all hover:scale-110"
          style={{ color: repeatMode !== 'off' ? 'var(--accent-primary)' : 'var(--text-secondary)' }}
        >
          {repeatMode === 'one' ? <Repeat1 size={20} /> : <Repeat size={20} />}
        </button>
      </div>

      {/* Volume + Playlist Row */}
      <div className="flex items-center justify-between px-6 py-2">
        <div className="flex items-center gap-2 flex-1">
          <button onClick={() => setVolume(v => v === 0 ? 0.7 : 0)} className="transition-all" style={{ color: 'var(--text-secondary)' }}>
            {volume === 0 ? <VolumeX size={18} /> : <Volume2 size={18} />}
          </button>
          <input
            type="range"
            min={0}
            max={1}
            step={0.01}
            value={volume}
            onChange={handleVolumeChange}
            className="flex-1"
            style={{ accentColor: 'var(--accent-primary)', height: 4, maxWidth: 100 }}
          />
        </div>
        <button
          onClick={() => setShowPlaylist((s) => !s)}
          className="flex items-center justify-center rounded-lg transition-all hover:bg-[var(--bg-hover)]"
          style={{ width: 32, height: 32, color: showPlaylist ? 'var(--accent-primary)' : 'var(--text-secondary)' }}
        >
          <ListMusic size={20} />
        </button>
      </div>

      {/* Playlist Panel */}
      {showPlaylist && (
        <div
          className="absolute bottom-0 left-0 right-0 z-10 overflow-y-auto custom-scrollbar"
          style={{
            height: '55%',
            background: 'var(--bg-titlebar)',
            borderRadius: '12px 12px 0 0',
            boxShadow: '0 -4px 16px rgba(0,0,0,0.3)',
          }}
        >
          <div className="flex items-center justify-between px-4 py-3 sticky top-0" style={{ background: 'var(--bg-titlebar)', borderBottom: '1px solid var(--border-subtle)' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>Playlist</span>
            <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{tracks.length} tracks</span>
          </div>
          {tracks.map((track, i) => (
            <div
              key={track.id}
              onClick={() => { setCurrentIndex(i); setCurrentTime(0); setIsPlaying(true); }}
              className="flex items-center gap-3 px-4 py-2.5 cursor-pointer transition-all"
              style={{
                background: i === currentIndex ? 'var(--bg-selected)' : 'transparent',
                borderLeft: i === currentIndex ? '3px solid var(--accent-primary)' : '3px solid transparent',
              }}
            >
              <span style={{ fontSize: '11px', color: 'var(--text-disabled)', width: 20, textAlign: 'center' }}>
                {i === currentIndex && isPlaying ? <Music size={12} style={{ color: 'var(--accent-primary)' }} /> : i + 1}
              </span>
              <div className="flex-1 min-w-0">
                <div className="truncate" style={{ fontSize: '13px', fontWeight: i === currentIndex ? 600 : 400, color: 'var(--text-primary)' }}>
                  {track.title}
                </div>
                <div className="truncate" style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                  {track.artist}
                </div>
              </div>
              <span style={{ fontSize: '11px', color: 'var(--text-disabled)', flexShrink: 0 }}>{formatTime(track.duration)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

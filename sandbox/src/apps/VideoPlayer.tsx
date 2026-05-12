// ============================================================
// Video Player — File picker, playback controls, fullscreen
// ============================================================

import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Play, Pause, SkipBack, SkipForward, Volume2, VolumeX, Maximize, Minimize, Settings, Film
} from 'lucide-react';

// ---- Types ----
interface VideoFile {
  id: string;
  name: string;
  duration: number;
  size: string;
}

// ---- Demo Videos ----
const DEMO_VIDEOS: VideoFile[] = [
  { id: '1', name: 'Nature Documentary.mp4', duration: 765, size: '1.2 GB' },
  { id: '2', name: 'Tutorial - Getting Started.mp4', duration: 512, size: '850 MB' },
  { id: '3', name: 'Concert Highlights.mp4', duration: 920, size: '2.1 GB' },
  { id: '4', name: 'Movie Trailer.mp4', duration: 150, size: '320 MB' },
  { id: '5', name: 'Time Lapse - City.mp4', duration: 315, size: '680 MB' },
];

const SPEED_OPTIONS = [0.5, 0.75, 1, 1.25, 1.5, 2];

// ---- Helpers ----
const formatTime = (seconds: number): string => {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  return `${m}:${s.toString().padStart(2, '0')}`;
};

// ---- Main Video Player ----
export default function VideoPlayer() {
  const [currentVideo, setCurrentVideo] = useState<VideoFile | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [volume, setVolume] = useState(0.7);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [showSpeedMenu, setShowSpeedMenu] = useState(false);
  const [showControls, setShowControls] = useState(true);
  const playlist = DEMO_VIDEOS;
  const controlsTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const videoContainerRef = useRef<HTMLDivElement>(null);
  const progressInterval = useRef<ReturnType<typeof setInterval> | null>(null);

  const currentDuration = currentVideo?.duration || 0;

  // Simulated playback
  useEffect(() => {
    if (isPlaying && currentVideo) {
      progressInterval.current = setInterval(() => {
        setCurrentTime((prev) => {
          const next = prev + playbackSpeed;
          if (next >= currentDuration) {
            setIsPlaying(false);
            return currentDuration;
          }
          return next;
        });
      }, 1000);
    }
    return () => { if (progressInterval.current) clearInterval(progressInterval.current); };
  }, [isPlaying, currentVideo, playbackSpeed, currentDuration]);

  // Auto-hide controls
  const handleMouseMove = useCallback(() => {
    setShowControls(true);
    if (controlsTimeout.current) clearTimeout(controlsTimeout.current);
    controlsTimeout.current = setTimeout(() => {
      if (isPlaying) setShowControls(false);
    }, 3000);
  }, [isPlaying]);

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCurrentTime(Number(e.target.value));
  };

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setVolume(Number(e.target.value));
  };

  const toggleFullscreen = useCallback(() => {
    if (!document.fullscreenElement) {
      videoContainerRef.current?.requestFullscreen();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  }, []);

  const selectVideo = (video: VideoFile) => {
    setCurrentVideo(video);
    setCurrentTime(0);
    setIsPlaying(true);
  };

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.code === 'Space' && e.target === document.body) {
        e.preventDefault();
        setIsPlaying((p) => !p);
      }
      if (e.code === 'ArrowRight') setCurrentTime((t) => Math.min(t + 5, currentDuration));
      if (e.code === 'ArrowLeft') setCurrentTime((t) => Math.max(t - 5, 0));
      if (e.code === 'ArrowUp') setVolume((v) => Math.min(v + 0.1, 1));
      if (e.code === 'ArrowDown') setVolume((v) => Math.max(v - 0.1, 0));
      if (e.code === 'KeyF') toggleFullscreen();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [currentDuration, toggleFullscreen]);

  return (
    <div
      ref={videoContainerRef}
      className="flex flex-col h-full relative"
      style={{ background: '#000' }}
      onMouseMove={handleMouseMove}
    >
      {/* Video Display Area */}
      <div className="flex-1 flex items-center justify-center relative" style={{ background: '#0A0A0A' }}>
        {!currentVideo ? (
          /* No video selected */
          <div className="flex flex-col items-center justify-center gap-4">
            <Film size={64} style={{ color: 'var(--text-disabled)' }} />
            <p style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>Select a video to play</p>
            <div className="flex flex-col gap-2 mt-2" style={{ maxWidth: 300, width: '100%' }}>
              {playlist.map((video) => (
                <button
                  key={video.id}
                  onClick={() => selectVideo(video)}
                  className="flex items-center gap-3 px-4 py-3 rounded-lg transition-all hover:bg-[var(--bg-hover)] text-left"
                  style={{ background: 'var(--bg-window)', border: '1px solid var(--border-subtle)' }}
                >
                  <Film size={20} style={{ color: 'var(--accent-primary)', flexShrink: 0 }} />
                  <div className="flex-1 min-w-0">
                    <div className="truncate" style={{ fontSize: '13px', color: 'var(--text-primary)' }}>{video.name}</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-disabled)' }}>{formatTime(video.duration)} · {video.size}</div>
                  </div>
                  <Play size={16} style={{ color: 'var(--accent-primary)' }} />
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* Video playing */
          <>
            {/* Placeholder for video content */}
            <div
              className="w-full h-full flex items-center justify-center"
              style={{ background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)' }}
              onClick={() => setIsPlaying((p) => !p)}
            >
              <div className="flex flex-col items-center gap-3">
                <Film size={48} style={{ color: 'rgba(255,255,255,0.2)' }} />
                <span style={{ fontSize: '14px', color: 'rgba(255,255,255,0.3)' }}>{currentVideo.name}</span>
                {!isPlaying && (
                  <button
                    onClick={(e) => { e.stopPropagation(); setIsPlaying(true); }}
                    className="flex items-center justify-center rounded-full"
                    style={{ width: 64, height: 64, background: 'rgba(0,0,0,0.6)' }}
                  >
                    <Play size={32} style={{ color: 'white' }} />
                  </button>
                )}
              </div>
            </div>

            {/* Controls Overlay */}
            {showControls && (
              <div
                className="absolute bottom-0 left-0 right-0 flex flex-col gap-1 px-3 pb-3 pt-8 transition-opacity"
                style={{ background: 'linear-gradient(transparent, rgba(0,0,0,0.8))' }}
              >
                {/* Progress bar */}
                <input
                  type="range"
                  min={0}
                  max={currentDuration}
                  value={currentTime}
                  onChange={handleSeek}
                  className="w-full cursor-pointer"
                  style={{ accentColor: 'var(--accent-primary)', height: 4 }}
                />
                {/* Control buttons */}
                <div className="flex items-center justify-between mt-1">
                  <div className="flex items-center gap-2">
                    <button onClick={() => setIsPlaying((p) => !p)} className="flex items-center justify-center rounded-full hover:bg-[rgba(255,255,255,0.1)]" style={{ width: 36, height: 36 }}>
                      {isPlaying ? <Pause size={20} style={{ color: 'white' }} /> : <Play size={20} style={{ color: 'white' }} className="ml-0.5" />}
                    </button>
                    <button onClick={() => setCurrentTime((t) => Math.max(t - 10, 0))} className="flex items-center justify-center rounded-full hover:bg-[rgba(255,255,255,0.1)]" style={{ width: 28, height: 28 }}>
                      <SkipBack size={16} style={{ color: 'white' }} />
                    </button>
                    <button onClick={() => setCurrentTime((t) => Math.min(t + 10, currentDuration))} className="flex items-center justify-center rounded-full hover:bg-[rgba(255,255,255,0.1)]" style={{ width: 28, height: 28 }}>
                      <SkipForward size={16} style={{ color: 'white' }} />
                    </button>
                    <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.8)', marginLeft: 8 }}>
                      {formatTime(currentTime)} / {formatTime(currentDuration)}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    {/* Volume */}
                    <button onClick={() => setVolume((v) => v === 0 ? 0.7 : 0)} className="flex items-center justify-center rounded-full hover:bg-[rgba(255,255,255,0.1)]" style={{ width: 28, height: 28 }}>
                      {volume === 0 ? <VolumeX size={16} style={{ color: 'white' }} /> : <Volume2 size={16} style={{ color: 'white' }} />}
                    </button>
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.01}
                      value={volume}
                      onChange={handleVolumeChange}
                      style={{ width: 60, accentColor: 'white', height: 3 }}
                    />
                    {/* Speed */}
                    <div className="relative">
                      <button
                        onClick={() => setShowSpeedMenu((s) => !s)}
                        className="flex items-center justify-center rounded-full hover:bg-[rgba(255,255,255,0.1)]"
                        style={{ width: 28, height: 28 }}
                      >
                        <Settings size={16} style={{ color: 'white' }} />
                      </button>
                      {showSpeedMenu && (
                        <div
                          className="absolute bottom-8 right-0 rounded-lg overflow-hidden z-20"
                          style={{ background: 'rgba(30,30,30,0.95)', border: '1px solid rgba(255,255,255,0.1)', boxShadow: '0 4px 16px rgba(0,0,0,0.5)' }}
                        >
                          {SPEED_OPTIONS.map((s) => (
                            <button
                              key={s}
                              onClick={() => { setPlaybackSpeed(s); setShowSpeedMenu(false); }}
                              className="block w-full px-4 py-2 text-left transition-all hover:bg-[rgba(255,255,255,0.1)]"
                              style={{ fontSize: '12px', color: s === playbackSpeed ? 'var(--accent-primary)' : 'white' }}
                            >
                              {s}x
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                    {/* Fullscreen */}
                    <button onClick={toggleFullscreen} className="flex items-center justify-center rounded-full hover:bg-[rgba(255,255,255,0.1)]" style={{ width: 28, height: 28 }}>
                      {isFullscreen ? <Minimize size={16} style={{ color: 'white' }} /> : <Maximize size={16} style={{ color: 'white' }} />}
                    </button>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Playlist sidebar (when video selected) */}
      {currentVideo && (
        <div
          className="shrink-0 overflow-x-auto custom-scrollbar"
          style={{
            height: 80,
            background: 'var(--bg-titlebar)',
            borderTop: '1px solid var(--border-subtle)',
          }}
        >
          <div className="flex gap-2 p-2">
            {playlist.map((video) => (
              <button
                key={video.id}
                onClick={() => selectVideo(video)}
                className="flex items-center gap-2 px-3 py-2 rounded-lg transition-all shrink-0"
                style={{
                  background: video.id === currentVideo.id ? 'var(--bg-selected)' : 'var(--bg-hover)',
                  border: video.id === currentVideo.id ? '1px solid var(--accent-primary)' : '1px solid var(--border-subtle)',
                }}
              >
                <Film size={16} style={{ color: 'var(--accent-primary)', flexShrink: 0 }} />
                <div className="text-left">
                  <div className="truncate" style={{ fontSize: '12px', color: 'var(--text-primary)', maxWidth: 140 }}>{video.name}</div>
                  <div style={{ fontSize: '10px', color: 'var(--text-disabled)' }}>{formatTime(video.duration)}</div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================
// Image Viewer — Zoom, pan, slideshow, thumbnail strip
// ============================================================

import { useState, useRef, useEffect, useCallback } from 'react';
import {
  ZoomIn, ZoomOut, Maximize2, ChevronLeft, ChevronRight, Play, Square, Info, X, RotateCcw
} from 'lucide-react';

// ---- Types ----
interface ImageItem {
  id: string;
  name: string;
  src: string;
  width: number;
  height: number;
  size: string;
}

// ---- Demo Images ----
const DEMO_IMAGES: ImageItem[] = [
  { id: '1', name: 'mountain-lake.jpg', src: 'https://picsum.photos/seed/ubuntu1/800/600', width: 800, height: 600, size: '245 KB' },
  { id: '2', name: 'city-sunset.jpg', src: 'https://picsum.photos/seed/ubuntu2/800/600', width: 800, height: 600, size: '312 KB' },
  { id: '3', name: 'forest-trail.jpg', src: 'https://picsum.photos/seed/ubuntu3/800/600', width: 800, height: 600, size: '189 KB' },
  { id: '4', name: 'ocean-beach.jpg', src: 'https://picsum.photos/seed/ubuntu4/800/600', width: 800, height: 600, size: '278 KB' },
  { id: '5', name: 'desert-dunes.jpg', src: 'https://picsum.photos/seed/ubuntu5/800/600', width: 800, height: 600, size: '356 KB' },
  { id: '6', name: 'snow-cabin.jpg', src: 'https://picsum.photos/seed/ubuntu6/800/600', width: 800, height: 600, size: '198 KB' },
];

// ---- Main Image Viewer ----
export default function ImageViewer() {
  const [images] = useState<ImageItem[]>(DEMO_IMAGES);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [isSlideshow, setIsSlideshow] = useState(false);
  const [showInfo, setShowInfo] = useState(false);
  const showThumbnails = true;
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [panOffset, setPanOffset] = useState({ x: 0, y: 0 });
  const [viewMode, setViewMode] = useState<'fit' | 'actual'>('fit');
  const slideshowTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const currentImage = images[currentIndex];

  // Slideshow
  useEffect(() => {
    if (isSlideshow) {
      slideshowTimer.current = setInterval(() => {
        setCurrentIndex((prev) => (prev + 1) % images.length);
        setZoom(1);
        setPanOffset({ x: 0, y: 0 });
      }, 3000);
    }
    return () => { if (slideshowTimer.current) clearInterval(slideshowTimer.current); };
  }, [isSlideshow, images.length]);

  const goNext = useCallback(() => {
    setCurrentIndex((prev) => (prev + 1) % images.length);
    setZoom(1);
    setPanOffset({ x: 0, y: 0 });
  }, [images.length]);

  const goPrev = useCallback(() => {
    setCurrentIndex((prev) => (prev - 1 + images.length) % images.length);
    setZoom(1);
    setPanOffset({ x: 0, y: 0 });
  }, [images.length]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.code === 'ArrowRight') goNext();
      if (e.code === 'ArrowLeft') goPrev();
      if (e.code === 'Equal' && e.shiftKey) setZoom((z) => Math.min(z + 0.25, 5));
      if (e.code === 'Minus') setZoom((z) => Math.max(z - 0.25, 0.1));
      if (e.code === 'Space') { e.preventDefault(); setIsSlideshow((s) => !s); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [goNext, goPrev]);

  const handleZoomIn = () => setZoom((z) => Math.min(z + 0.25, 5));
  const handleZoomOut = () => setZoom((z) => Math.max(z - 0.25, 0.1));

  const handleMouseDown = (e: React.MouseEvent) => {
    if (zoom > 1) {
      setIsDragging(true);
      setDragStart({ x: e.clientX - panOffset.x, y: e.clientY - panOffset.y });
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging && zoom > 1) {
      setPanOffset({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
    }
  };

  const handleMouseUp = () => setIsDragging(false);

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.1 : 0.1;
    setZoom((z) => Math.max(0.1, Math.min(5, z + delta)));
  };

  const zoomPercent = Math.round(zoom * 100);

  return (
    <div className="flex flex-col h-full relative" style={{ background: '#0A0A0A' }}>
      {/* Top Toolbar */}
      <div
        className="absolute top-0 left-0 right-0 z-20 flex items-center justify-between px-3 transition-opacity"
        style={{
          height: 40,
          background: 'rgba(0,0,0,0.6)',
          opacity: isSlideshow ? 0 : 1,
          pointerEvents: isSlideshow ? 'none' : 'auto',
        }}
      >
        <div className="flex items-center gap-1">
          <button onClick={handleZoomOut} className="flex items-center justify-center rounded hover:bg-[rgba(255,255,255,0.1)]" style={{ width: 28, height: 28 }}>
            <ZoomOut size={16} style={{ color: 'white' }} />
          </button>
          <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.7)', minWidth: 36, textAlign: 'center' }}>{zoomPercent}%</span>
          <button onClick={handleZoomIn} className="flex items-center justify-center rounded hover:bg-[rgba(255,255,255,0.1)]" style={{ width: 28, height: 28 }}>
            <ZoomIn size={16} style={{ color: 'white' }} />
          </button>
          <div style={{ width: 1, height: 20, background: 'rgba(255,255,255,0.2)', margin: '0 4px' }} />
          <button onClick={() => { setViewMode('fit'); setZoom(1); setPanOffset({ x: 0, y: 0 }); }} className="flex items-center justify-center rounded hover:bg-[rgba(255,255,255,0.1)]" style={{ width: 28, height: 28 }}>
            <Maximize2 size={16} style={{ color: viewMode === 'fit' ? 'var(--accent-primary)' : 'white' }} />
          </button>
          <button onClick={() => setViewMode('actual')} className="flex items-center justify-center rounded hover:bg-[rgba(255,255,255,0.1)]" style={{ width: 28, height: 28 }}>
            <RotateCcw size={16} style={{ color: viewMode === 'actual' ? 'var(--accent-primary)' : 'white' }} />
          </button>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => setIsSlideshow((s) => !s)} className="flex items-center justify-center rounded hover:bg-[rgba(255,255,255,0.1)]" style={{ width: 28, height: 28 }}>
            {isSlideshow ? <Square size={16} style={{ color: 'var(--accent-primary)' }} /> : <Play size={16} style={{ color: 'white' }} />}
          </button>
          <button onClick={() => setShowInfo((s) => !s)} className="flex items-center justify-center rounded hover:bg-[rgba(255,255,255,0.1)]" style={{ width: 28, height: 28 }}>
            <Info size={16} style={{ color: showInfo ? 'var(--accent-primary)' : 'white' }} />
          </button>
        </div>
      </div>

      {/* Image Display Area */}
      <div
        ref={containerRef}
        className="flex-1 flex items-center justify-center overflow-hidden cursor-grab active:cursor-grabbing"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
      >
        {currentImage && (
          <img
            src={currentImage.src}
            alt={currentImage.name}
            className="transition-transform select-none pointer-events-none"
            style={{
              transform: `scale(${zoom}) translate(${panOffset.x / zoom}px, ${panOffset.y / zoom}px)`,
              maxWidth: viewMode === 'fit' ? '100%' : 'none',
              maxHeight: viewMode === 'fit' ? '100%' : 'none',
              objectFit: viewMode === 'fit' ? 'contain' : undefined,
            }}
            draggable={false}
          />
        )}

        {/* Navigation Arrows */}
        {!isSlideshow && (
          <>
            <button
              onClick={goPrev}
              className="absolute left-3 flex items-center justify-center rounded-full transition-all hover:bg-[rgba(255,255,255,0.2)] z-10"
              style={{ width: 48, height: 48, background: 'rgba(255,255,255,0.1)', backdropFilter: 'blur(4px)' }}
            >
              <ChevronLeft size={24} style={{ color: 'white' }} />
            </button>
            <button
              onClick={goNext}
              className="absolute right-3 flex items-center justify-center rounded-full transition-all hover:bg-[rgba(255,255,255,0.2)] z-10"
              style={{ width: 48, height: 48, background: 'rgba(255,255,255,0.1)', backdropFilter: 'blur(4px)' }}
            >
              <ChevronRight size={24} style={{ color: 'white' }} />
            </button>
          </>
        )}

        {/* Info Panel */}
        {showInfo && currentImage && (
          <div
            className="absolute top-12 right-3 z-30 p-4 rounded-xl"
            style={{ background: 'rgba(0,0,0,0.8)', backdropFilter: 'blur(8px)', width: 220, border: '1px solid rgba(255,255,255,0.1)' }}
          >
            <div className="flex items-center justify-between mb-3">
              <span style={{ fontSize: '13px', fontWeight: 600, color: 'white' }}>Image Info</span>
              <button onClick={() => setShowInfo(false)}><X size={14} style={{ color: 'rgba(255,255,255,0.6)' }} /></button>
            </div>
            <div className="flex flex-col gap-2">
              <InfoRow label="Name" value={currentImage.name} />
              <InfoRow label="Dimensions" value={`${currentImage.width} x ${currentImage.height}`} />
              <InfoRow label="Size" value={currentImage.size} />
              <InfoRow label="Type" value="image/jpeg" />
              <InfoRow label="Index" value={`${currentIndex + 1} / ${images.length}`} />
            </div>
          </div>
        )}

        {/* Slideshow indicator */}
        {isSlideshow && (
          <div className="absolute top-12 left-1/2 -translate-x-1/2 flex items-center gap-2 px-3 py-1.5 rounded-full" style={{ background: 'rgba(0,0,0,0.6)' }}>
            <div className="w-2 h-2 rounded-full animate-pulse" style={{ background: 'var(--accent-error)' }} />
            <span style={{ fontSize: '11px', color: 'white' }}>Slideshow</span>
          </div>
        )}
      </div>

      {/* Bottom Info Bar */}
      <div
        className="absolute bottom-0 left-0 right-0 z-20 flex items-center justify-between px-4 transition-opacity"
        style={{
          height: 32,
          background: 'rgba(0,0,0,0.6)',
          backdropFilter: 'blur(8px)',
          opacity: isSlideshow ? 0 : 1,
        }}
      >
        <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.8)' }}>{currentImage?.name}</span>
        <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.6)' }}>{currentIndex + 1} / {images.length}</span>
        <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.6)' }}>{currentImage?.width} x {currentImage?.height}</span>
      </div>

      {/* Thumbnail Strip */}
      {showThumbnails && !isSlideshow && (
        <div
          className="shrink-0 overflow-x-auto custom-scrollbar z-20"
          style={{ height: 80, background: 'var(--bg-titlebar)', borderTop: '1px solid var(--border-subtle)' }}
        >
          <div className="flex gap-2 p-2">
            {images.map((img, i) => (
              <button
                key={img.id}
                onClick={() => { setCurrentIndex(i); setZoom(1); setPanOffset({ x: 0, y: 0 }); }}
                className="relative rounded-lg overflow-hidden transition-all shrink-0"
                style={{
                  width: 60, height: 60,
                  border: i === currentIndex ? '2px solid var(--accent-primary)' : '2px solid transparent',
                  opacity: i === currentIndex ? 1 : 0.6,
                }}
              >
                <img src={img.src} alt={img.name} className="w-full h-full object-cover" />
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.5)' }}>{label}</span>
      <span style={{ fontSize: '11px', color: 'white' }} className="truncate ml-2">{value}</span>
    </div>
  );
}

// ============================================================
// Image Gallery — Browse images from virtual file system
// ============================================================

import { useState, useCallback, useMemo, useRef } from 'react';
import {
  Image, Plus, Trash2, X, ChevronLeft, ChevronRight,
  LayoutGrid, LayoutList, Search,
} from 'lucide-react';

interface GalleryImage {
  id: string;
  name: string;
  src: string;
  size: number;
  date: number;
  type: 'photo' | 'screenshot' | 'download';
}

type SortMode = 'name' | 'date' | 'size';
type FilterMode = 'all' | 'photos' | 'screenshots' | 'downloads';
type ViewMode = 'grid' | 'masonry';

const DEMO_IMAGES: GalleryImage[] = [
  { id: 'demo-1', name: 'mountains.jpg', src: 'https://picsum.photos/seed/mountains/400/300', size: 2450000, date: Date.now() - 86400000 * 5, type: 'photo' },
  { id: 'demo-2', name: 'cityscape.jpg', src: 'https://picsum.photos/seed/city/400/500', size: 1890000, date: Date.now() - 86400000 * 4, type: 'photo' },
  { id: 'demo-3', name: 'ocean.jpg', src: 'https://picsum.photos/seed/ocean/400/250', size: 2100000, date: Date.now() - 86400000 * 3, type: 'photo' },
  { id: 'demo-4', name: 'forest.jpg', src: 'https://picsum.photos/seed/forest/400/400', size: 1560000, date: Date.now() - 86400000 * 2, type: 'photo' },
  { id: 'demo-5', name: 'flowers.jpg', src: 'https://picsum.photos/seed/flowers/400/350', size: 1340000, date: Date.now() - 86400000, type: 'photo' },
  { id: 'demo-6', name: 'architecture.jpg', src: 'https://picsum.photos/seed/arch/400/600', size: 2780000, date: Date.now() - 86400000 * 7, type: 'photo' },
  { id: 'demo-7', name: 'screenshot-1.png', src: 'https://picsum.photos/seed/screen1/400/300', size: 890000, date: Date.now() - 86400000 * 1, type: 'screenshot' },
  { id: 'demo-8', name: 'download-1.jpg', src: 'https://picsum.photos/seed/dl1/400/300', size: 1200000, date: Date.now() - 86400000 * 10, type: 'download' },
];

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ImageGallery() {
  const [images, setImages] = useState<GalleryImage[]>(DEMO_IMAGES);
  const [sortMode, setSortMode] = useState<SortMode>('date');
  const [filterMode, setFilterMode] = useState<FilterMode>('all');
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [searchQuery, setSearchQuery] = useState('');
  const [lightboxImage, setLightboxImage] = useState<GalleryImage | null>(null);
  const [lightboxIndex, setLightboxIndex] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const filteredImages = useMemo(() => {
    let result = [...images];

    if (filterMode !== 'all') {
      result = result.filter((img) =>
        filterMode === 'photos' ? img.type === 'photo' :
        filterMode === 'screenshots' ? img.type === 'screenshot' :
        img.type === 'download'
      );
    }

    if (searchQuery) {
      result = result.filter((img) => img.name.toLowerCase().includes(searchQuery.toLowerCase()));
    }

    switch (sortMode) {
      case 'name': result.sort((a, b) => a.name.localeCompare(b.name)); break;
      case 'date': result.sort((a, b) => b.date - a.date); break;
      case 'size': result.sort((a, b) => b.size - a.size); break;
    }

    return result;
  }, [images, filterMode, searchQuery, sortMode]);

  const totalSize = useMemo(() => images.reduce((sum, img) => sum + img.size, 0), [images]);

  const deleteImage = useCallback((id: string) => {
    setImages((prev) => prev.filter((img) => img.id !== id));
    if (lightboxImage?.id === id) setLightboxImage(null);
  }, [lightboxImage]);

  const handleFileUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;
    Array.from(files).forEach((file) => {
      const reader = new FileReader();
      reader.onload = () => {
        const newImage: GalleryImage = {
          id: `upload-${Date.now()}-${Math.random().toString(36).slice(2)}`,
          name: file.name,
          src: reader.result as string,
          size: file.size,
          date: Date.now(),
          type: 'photo',
        };
        setImages((prev) => [newImage, ...prev]);
      };
      reader.readAsDataURL(file);
    });
    e.target.value = '';
  }, []);

  const openLightbox = useCallback((img: GalleryImage, index: number) => {
    setLightboxImage(img);
    setLightboxIndex(index);
  }, []);

  const navigateLightbox = useCallback((dir: number) => {
    const newIndex = lightboxIndex + dir;
    if (newIndex >= 0 && newIndex < filteredImages.length) {
      setLightboxIndex(newIndex);
      setLightboxImage(filteredImages[newIndex]);
    }
  }, [lightboxIndex, filteredImages]);

  return (
    <div className="h-full flex flex-col" style={{ background: 'var(--bg-window)' }}>
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-3 py-1.5 shrink-0" style={{ background: 'var(--bg-titlebar)', borderBottom: '1px solid var(--border-subtle)' }}>
        <button onClick={() => fileInputRef.current?.click()} className="flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium" style={{ background: 'var(--accent-primary)', color: 'white' }}>
          <Plus size={12} /> Add Images
        </button>
        <input ref={fileInputRef} type="file" accept="image/*" multiple onChange={handleFileUpload} className="hidden" />

        <div className="w-px h-5 mx-1" style={{ background: 'var(--border-subtle)' }} />

        {/* View toggle */}
        <button onClick={() => setViewMode('grid')} className="p-1 rounded" style={{ background: viewMode === 'grid' ? 'var(--bg-active)' : 'transparent' }}>
          <LayoutGrid size={14} style={{ color: viewMode === 'grid' ? 'var(--accent-primary)' : 'var(--text-secondary)' }} />
        </button>
        <button onClick={() => setViewMode('masonry')} className="p-1 rounded" style={{ background: viewMode === 'masonry' ? 'var(--bg-active)' : 'transparent' }}>
          <LayoutList size={14} style={{ color: viewMode === 'masonry' ? 'var(--accent-primary)' : 'var(--text-secondary)' }} />
        </button>

        <div className="w-px h-5 mx-1" style={{ background: 'var(--border-subtle)' }} />

        {/* Sort */}
        <select
          value={sortMode}
          onChange={(e) => setSortMode(e.target.value as SortMode)}
          className="text-xs px-1 py-0.5 rounded outline-none"
          style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }}
        >
          <option value="date">Date</option>
          <option value="name">Name</option>
          <option value="size">Size</option>
        </select>

        {/* Filter */}
        <select
          value={filterMode}
          onChange={(e) => setFilterMode(e.target.value as FilterMode)}
          className="text-xs px-1 py-0.5 rounded outline-none"
          style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }}
        >
          <option value="all">All</option>
          <option value="photos">Photos</option>
          <option value="screenshots">Screenshots</option>
          <option value="downloads">Downloads</option>
        </select>

        {/* Search */}
        <div className="flex items-center gap-1 ml-auto">
          <Search size={12} style={{ color: 'var(--text-secondary)' }} />
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search..."
            className="text-xs px-1.5 py-0.5 rounded outline-none w-28"
            style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }}
          />
        </div>

        {/* Stats */}
        <span className="text-xs" style={{ color: 'var(--text-disabled)' }}>{images.length} images | {formatSize(totalSize)}</span>
      </div>

      {/* Main grid */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-3">
        {filteredImages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-3">
            <Image size={48} className="text-[var(--text-disabled)]" />
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>No images found</p>
            <button onClick={() => fileInputRef.current?.click()} className="flex items-center gap-1 px-3 py-1.5 rounded text-xs" style={{ background: 'var(--accent-primary)', color: 'white' }}>
              <Plus size={12} /> Upload Images
            </button>
          </div>
        ) : viewMode === 'grid' ? (
          <div className="grid gap-2" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))' }}>
            {filteredImages.map((img, i) => (
              <div
                key={img.id}
                className="group relative rounded-lg overflow-hidden cursor-pointer"
                style={{ aspectRatio: '1' }}
                onClick={() => openLightbox(img, i)}
              >
                <img
                  src={img.src}
                  alt={img.name}
                  className="w-full h-full object-cover transition-transform group-hover:scale-105"
                  loading="lazy"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                <div className="absolute bottom-0 left-0 right-0 p-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                  <p className="text-[10px] text-white truncate">{img.name}</p>
                  <p className="text-[9px] text-white/60">{formatSize(img.size)}</p>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); deleteImage(img.id); }}
                  className="absolute top-1 right-1 p-1 rounded bg-black/40 text-white opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <Trash2 size={10} />
                </button>
              </div>
            ))}
          </div>
        ) : (
          /* Masonry */
          <div className="columns-3 gap-2">
            {filteredImages.map((img, i) => (
              <div
                key={img.id}
                className="group relative rounded-lg overflow-hidden cursor-pointer mb-2 break-inside-avoid"
                onClick={() => openLightbox(img, i)}
              >
                <img
                  src={img.src}
                  alt={img.name}
                  className="w-full object-cover transition-transform group-hover:scale-105"
                  loading="lazy"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                <div className="absolute bottom-0 left-0 right-0 p-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                  <p className="text-[10px] text-white truncate">{img.name}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Lightbox */}
      {lightboxImage && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.9)' }} onClick={() => setLightboxImage(null)}>
          <button className="absolute top-3 right-3 p-2 rounded-full text-white hover:bg-white/20" onClick={() => setLightboxImage(null)}>
            <X size={20} />
          </button>
          <button
            className="absolute left-3 p-2 rounded-full text-white hover:bg-white/20 disabled:opacity-30"
            disabled={lightboxIndex === 0}
            onClick={(e) => { e.stopPropagation(); navigateLightbox(-1); }}
          >
            <ChevronLeft size={24} />
          </button>
          <button
            className="absolute right-3 p-2 rounded-full text-white hover:bg-white/20 disabled:opacity-30"
            disabled={lightboxIndex === filteredImages.length - 1}
            onClick={(e) => { e.stopPropagation(); navigateLightbox(1); }}
          >
            <ChevronRight size={24} />
          </button>
          <img
            src={lightboxImage.src}
            alt={lightboxImage.name}
            className="max-w-[90vw] max-h-[85vh] object-contain rounded-lg"
            onClick={(e) => e.stopPropagation()}
          />
          <div className="absolute bottom-3 left-1/2 -translate-x-1/2 text-center">
            <p className="text-xs text-white font-medium">{lightboxImage.name}</p>
            <p className="text-[10px] text-white/60">{formatSize(lightboxImage.size)} | {lightboxIndex + 1} / {filteredImages.length}</p>
          </div>
        </div>
      )}
    </div>
  );
}

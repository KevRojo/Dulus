import { useState, useCallback } from 'react';
import {
  RefreshCw, Play, Download, FileVideo, FileAudio, FileImage,
  Settings2, Check, X, Trash2
} from 'lucide-react';
import { useFileSystem } from '@/hooks/useFileSystem';

interface ConversionJob {
  id: string;
  fileName: string;
  inputFormat: string;
  outputFormat: string;
  quality: string;
  resolution: string;
  progress: number;
  status: 'pending' | 'running' | 'completed' | 'error';
  createdAt: number;
}

const VIDEO_FORMATS = ['MP4', 'AVI', 'MKV', 'MOV', 'WEBM'];
const AUDIO_FORMATS = ['MP3', 'WAV', 'FLAC', 'AAC', 'OGG'];
const IMAGE_FORMATS = ['PNG', 'JPG', 'GIF', 'WEBP', 'BMP'];
const ALL_FORMATS = [...VIDEO_FORMATS, ...AUDIO_FORMATS, ...IMAGE_FORMATS];

const RESOLUTIONS = ['Original', '4K (3840x2160)', '1080p (1920x1080)', '720p (1280x720)', '480p (854x480)'];
const QUALITIES = ['High', 'Medium', 'Low'];

const detectType = (ext: string) => {
  if (VIDEO_FORMATS.includes(ext)) return 'video';
  if (AUDIO_FORMATS.includes(ext)) return 'audio';
  if (IMAGE_FORMATS.includes(ext)) return 'image';
  return 'video';
};

const getIcon = (type: string) => {
  if (type === 'audio') return <FileAudio size={16} />;
  if (type === 'image') return <FileImage size={16} />;
  return <FileVideo size={16} />;
};

export default function MediaConverter() {
  const { fs } = useFileSystem();
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [selectedFileName, setSelectedFileName] = useState('');
  const [selectedFileFormat, setSelectedFileFormat] = useState('');
  const [outputFormat, setOutputFormat] = useState('MP4');
  const [quality, setQuality] = useState('High');
  const [resolution, setResolution] = useState('Original');
  const [showFilePicker, setShowFilePicker] = useState(false);
  const [jobs, setJobs] = useState<ConversionJob[]>([]);
  const [showSettings, setShowSettings] = useState(false);

  const mediaFiles = Object.values(fs.nodes).filter(n => {
    if (n.type !== 'file') return false;
    const ext = n.name.split('.').pop()?.toUpperCase();
    return ext && ALL_FORMATS.includes(ext);
  });

  const selectFile = (id: string, name: string) => {
    const ext = name.split('.').pop()?.toUpperCase() || 'MP4';
    setSelectedFile(id);
    setSelectedFileName(name);
    setSelectedFileFormat(ext);
    // Set default output
    const type = detectType(ext);
    if (type === 'video') setOutputFormat('MP4');
    else if (type === 'audio') setOutputFormat('MP3');
    else setOutputFormat('PNG');
    setShowFilePicker(false);
  };

  const startConversion = () => {
    if (!selectedFile) return;
    const job: ConversionJob = {
      id: Date.now().toString(),
      fileName: selectedFileName,
      inputFormat: selectedFileFormat,
      outputFormat,
      quality,
      resolution,
      progress: 0,
      status: 'running',
      createdAt: Date.now(),
    };
    setJobs(prev => [job, ...prev]);
    // Simulate progress
    let progress = 0;
    const interval = setInterval(() => {
      progress += Math.random() * 10 + 3;
      if (progress >= 100) {
        progress = 100;
        clearInterval(interval);
        setJobs(prev => prev.map(j => j.id === job.id ? { ...j, progress: 100, status: 'completed' } : j));
      } else {
        setJobs(prev => prev.map(j => j.id === job.id ? { ...j, progress } : j));
      }
    }, 400);
  };

  const clearCompleted = () => setJobs(prev => prev.filter(j => j.status !== 'completed'));
  const deleteJob = (id: string) => setJobs(prev => prev.filter(j => j.id !== id));

  const formatTime = (ts: number) => new Date(ts).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-window)' }}>
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-panel)' }}>
        <RefreshCw size={16} style={{ color: 'var(--accent-primary)' }} />
        <span className="text-sm font-medium flex-1" style={{ color: 'var(--text-primary)' }}>Media Converter</span>
        {jobs.some(j => j.status === 'completed') && (
          <button onClick={clearCompleted} className="flex items-center gap-1 px-2 py-1 rounded-md text-xs" style={{ color: 'var(--text-secondary)' }}><Trash2 size={10} /> Clear</button>
        )}
      </div>

      <div className="flex-1 overflow-auto custom-scrollbar">
        {/* File Selection */}
        <div className="p-3">
          <div className="p-3 rounded-lg border" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-panel)' }}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>Source File</span>
              <button onClick={() => setShowFilePicker(true)} className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs" style={{ background: 'var(--accent-primary)', color: '#fff' }}>
                {selectedFile ? 'Change' : 'Select'} File
              </button>
            </div>
            {selectedFile ? (
              <div className="flex items-center gap-2">
                {getIcon(detectType(selectedFileFormat))}
                <span className="text-sm" style={{ color: 'var(--text-primary)' }}>{selectedFileName}</span>
                <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-hover)', color: 'var(--text-secondary)' }}>{selectedFileFormat}</span>
              </div>
            ) : (
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Select a media file from your file system</p>
            )}
          </div>
        </div>

        {/* Conversion Settings */}
        {selectedFile && (
          <div className="px-3 pb-3">
            <div className="p-3 rounded-lg border" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-panel)' }}>
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>Output Settings</span>
                <button onClick={() => setShowSettings(!showSettings)} className="p-0.5 rounded" style={{ color: 'var(--text-secondary)' }}><Settings2 size={12} /></button>
              </div>
              <div className="grid grid-cols-3 gap-2 mb-3">
                <div>
                  <label className="text-[10px] block mb-1" style={{ color: 'var(--text-secondary)' }}>Format</label>
                  <select value={outputFormat} onChange={e => setOutputFormat(e.target.value)} className="w-full px-2 py-1 rounded text-xs outline-none" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}>
                    {detectType(selectedFileFormat) === 'video' && VIDEO_FORMATS.map(f => <option key={f} value={f}>{f}</option>)}
                    {detectType(selectedFileFormat) === 'audio' && AUDIO_FORMATS.map(f => <option key={f} value={f}>{f}</option>)}
                    {detectType(selectedFileFormat) === 'image' && IMAGE_FORMATS.map(f => <option key={f} value={f}>{f}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-[10px] block mb-1" style={{ color: 'var(--text-secondary)' }}>Quality</label>
                  <select value={quality} onChange={e => setQuality(e.target.value)} className="w-full px-2 py-1 rounded text-xs outline-none" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}>
                    {QUALITIES.map(q => <option key={q} value={q}>{q}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-[10px] block mb-1" style={{ color: 'var(--text-secondary)' }}>Resolution</label>
                  <select value={resolution} onChange={e => setResolution(e.target.value)} className="w-full px-2 py-1 rounded text-xs outline-none" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}>
                    {RESOLUTIONS.map(r => <option key={r} value={r}>{r}</option>)}
                  </select>
                </div>
              </div>
              <button onClick={startConversion} className="w-full flex items-center justify-center gap-2 py-2 rounded-md text-xs font-medium" style={{ background: 'var(--accent-primary)', color: '#fff' }}>
                <Play size={12} /> Start Conversion
              </button>
            </div>
          </div>
        )}

        {/* Format Support Info */}
        <div className="px-3 pb-3">
          <div className="grid grid-cols-3 gap-2 text-[10px]" style={{ color: 'var(--text-secondary)' }}>
            <div className="p-2 rounded" style={{ background: 'var(--bg-panel)' }}>
              <span className="font-medium block mb-1" style={{ color: 'var(--text-primary)' }}>Video</span>
              {VIDEO_FORMATS.join(', ')}
            </div>
            <div className="p-2 rounded" style={{ background: 'var(--bg-panel)' }}>
              <span className="font-medium block mb-1" style={{ color: 'var(--text-primary)' }}>Audio</span>
              {AUDIO_FORMATS.join(', ')}
            </div>
            <div className="p-2 rounded" style={{ background: 'var(--bg-panel)' }}>
              <span className="font-medium block mb-1" style={{ color: 'var(--text-primary)' }}>Image</span>
              {IMAGE_FORMATS.join(', ')}
            </div>
          </div>
        </div>

        {/* Conversion History */}
        {jobs.length > 0 && (
          <div className="px-3 pb-3">
            <div className="p-3 rounded-lg border" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-panel)' }}>
              <span className="text-xs font-medium block mb-2" style={{ color: 'var(--text-primary)' }}>Conversion History</span>
              <div className="space-y-2">
                {jobs.map(job => (
                  <div key={job.id} className="flex items-center gap-2 p-2 rounded" style={{ background: 'var(--bg-window)' }}>
                    {getIcon(detectType(job.inputFormat))}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1">
                        <span className="text-xs truncate" style={{ color: 'var(--text-primary)' }}>{job.fileName}</span>
                        <span className="text-[9px]" style={{ color: 'var(--text-disabled)' }}>{job.inputFormat} → {job.outputFormat}</span>
                      </div>
                      <div className="flex items-center gap-2 mt-1">
                        <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--bg-hover)' }}>
                          <div className="h-full rounded-full transition-all" style={{ width: `${job.progress}%`, background: job.status === 'completed' ? 'var(--accent-success)' : job.status === 'running' ? 'var(--accent-primary)' : 'var(--accent-error)' }} />
                        </div>
                        <span className="text-[9px] w-8 text-right">{Math.round(job.progress)}%</span>
                        <span className="text-[9px]" style={{ color: job.status === 'completed' ? 'var(--accent-success)' : job.status === 'error' ? 'var(--accent-error)' : 'var(--text-secondary)' }}>{job.status}</span>
                      </div>
                    </div>
                    {job.status === 'completed' && (
                      <button className="p-1 rounded flex-shrink-0" style={{ color: 'var(--accent-primary)' }} title="Download"><Download size={12} /></button>
                    )}
                    <button onClick={() => deleteJob(job.id)} className="p-1 rounded flex-shrink-0" style={{ color: 'var(--text-disabled)' }}><X size={10} /></button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* File Picker Modal */}
      {showFilePicker && (
        <div className="absolute inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.5)' }}>
          <div className="rounded-lg shadow-xl overflow-hidden" style={{ width: '480px', maxHeight: '400px', background: 'var(--bg-window)' }}>
            <div className="flex items-center justify-between px-4 py-2 border-b" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-panel)' }}>
              <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>Select Media File</span>
              <button onClick={() => setShowFilePicker(false)} className="p-1 rounded"><X size={14} /></button>
            </div>
            <div className="overflow-auto custom-scrollbar p-2" style={{ maxHeight: '320px' }}>
              {mediaFiles.map(file => {
                const ext = file.name.split('.').pop()?.toUpperCase() || '';
                return (
                  <button key={file.id} onClick={() => selectFile(file.id, file.name)} className="flex items-center gap-2 w-full px-3 py-2 rounded-md text-left text-xs transition-colors" style={{ color: 'var(--text-primary)' }} onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')} onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                    {getIcon(detectType(ext))}
                    <span className="flex-1">{file.name}</span>
                    <span className="text-[10px]" style={{ color: 'var(--text-disabled)' }}>{ext}</span>
                  </button>
                );
              })}
              {mediaFiles.length === 0 && <div className="text-center py-8 text-xs" style={{ color: 'var(--text-secondary)' }}>No media files found</div>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

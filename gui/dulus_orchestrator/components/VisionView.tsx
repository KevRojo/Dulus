import React, { useState } from 'react';
import { Wand2, Download, Loader2, Image as ImageIcon } from 'lucide-react';
import { generateImage } from '../services/ai.ts';
import { cn } from '../utils.ts';

export const VisionView: React.FC = () => {
  const [prompt, setPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [images, setImages] = useState<{id: string, url: string, prompt: string}[]>([]);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || isGenerating) return;

    setIsGenerating(true);
    setError(null);

    try {
      const url = await generateImage(prompt);
      setImages(prev => [{ id: Date.now().toString(), url, prompt }, ...prev]);
    } catch (err: any) {
      console.error("Image generation error:", err);
      setError(err.message || "Failed to manifest image. The cosmic energies are unstable.");
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="flex flex-col h-full w-full p-6 overflow-y-auto">
      <div className="mb-8">
        <h2 className="text-3xl font-bold text-white mb-2 flex items-center">
          <ImageIcon className="w-8 h-8 mr-3 text-dulus-accent" />
          Vision Forge
        </h2>
        <p className="text-dulus-muted">Describe your vision, and Dulus shall manifest it into reality.</p>
      </div>

      <div className="glass-panel rounded-2xl p-6 mb-8 shadow-xl">
        <form onSubmit={handleGenerate} className="flex flex-col gap-4">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="A hooded figure woven from starlight, holding a glowing geometric artifact..."
            className="w-full glass-input rounded-xl p-4 resize-none min-h-[100px]"
          />
          
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={!prompt.trim() || isGenerating}
              className="flex items-center px-8 py-3 bg-gradient-to-br from-zinc-800 to-black border border-zinc-700 hover:border-dulus-accent text-white rounded-xl font-bold tracking-wide transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-[0_0_15px_rgba(251,191,36,0.2)]"
            >
              {isGenerating ? (
                <><Loader2 className="w-5 h-5 mr-2 animate-spin" /> Manifesting...</>
              ) : (
                <><Wand2 className="w-5 h-5 mr-2" /> Generate Vision</>
              )}
            </button>
          </div>
        </form>
        {error && <div className="mt-4 text-red-400 text-sm bg-red-900/20 p-3 rounded-lg border border-red-500/20">{error}</div>}
      </div>

      {/* Gallery */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {images.map((img) => (
          <div key={img.id} className="group relative rounded-2xl overflow-hidden border border-white/10 bg-black/50 aspect-video">
            <img src={img.url} alt={img.prompt} className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105" />
            
            <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/40 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex flex-col justify-end p-4">
              <p className="text-sm text-slate-200 line-clamp-2 mb-3">{img.prompt}</p>
              <a 
                href={img.url}
                download={`dulus-vision-${img.id}.jpg`}
                className="flex items-center justify-center w-full py-2 bg-white/10 hover:bg-white/20 backdrop-blur-md rounded-lg text-white transition-colors border border-white/10"
              >
                <Download className="w-4 h-4 mr-2" /> Download
              </a>
            </div>
          </div>
        ))}
        
        {images.length === 0 && !isGenerating && (
          <div className="col-span-full flex flex-col items-center justify-center py-20 text-slate-500">
            <ImageIcon className="w-16 h-16 mb-4 opacity-20" />
            <p>The gallery is empty. Speak your vision to fill it.</p>
          </div>
        )}
      </div>
    </div>
  );
};


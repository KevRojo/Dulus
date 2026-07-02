import React, { useState } from 'react';
import { Wand2, Download, Loader2, Image as ImageIcon } from 'lucide-react';
import { generateImage } from '../services/ai.ts';
import { GeneratedImage } from '../types.ts';

export const ImageGenView: React.FC = () => {
  const [prompt, setPrompt] = useState('');
  const [aspectRatio, setAspectRatio] = useState('1:1');
  const [isGenerating, setIsGenerating] = useState(false);
  const [images, setImages] = useState<GeneratedImage[]>([]);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || isGenerating) return;

    setIsGenerating(true);
    setError(null);

    try {
      const url = await generateImage(prompt, aspectRatio);
      const newImage: GeneratedImage = {
        id: Date.now().toString(),
        url,
        prompt
      };
      setImages(prev => [newImage, ...prev]);
    } catch (err: any) {
      console.error("Image generation error:", err);
      setError(err.message || "Failed to manifest image. The cosmic energies are unstable.");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDownload = (url: string, id: string) => {
    const a = document.createElement('a');
    a.href = url;
    a.download = `dulus-vision-${id}.jpg`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <div className="flex flex-col h-full max-w-6xl mx-auto w-full p-4 md:p-8 overflow-y-auto">
      <div className="mb-8 text-center">
        <h2 className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-white to-dulus-accent mb-2">
          Vision Forge
        </h2>
        <p className="text-slate-400">Describe your vision, and Dulus shall manifest it into reality.</p>
      </div>

      <div className="bg-dulus-panel/50 border border-white/10 rounded-2xl p-6 backdrop-blur-sm mb-8 shadow-xl">
        <form onSubmit={handleGenerate} className="flex flex-col gap-4">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="A hooded figure woven from starlight, holding a glowing geometric artifact..."
            className="w-full bg-black/30 border border-white/10 rounded-xl p-4 text-white placeholder-slate-500 focus:outline-none focus:border-dulus-accent/50 focus:ring-1 focus:ring-dulus-accent/50 resize-none min-h-[100px]"
          />
          
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center space-x-2 bg-black/30 rounded-lg p-1 border border-white/5">
              {['1:1', '16:9', '9:16', '4:3'].map(ratio => (
                <button
                  key={ratio}
                  type="button"
                  onClick={() => setAspectRatio(ratio)}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    aspectRatio === ratio 
                      ? 'bg-white/10 text-white shadow-sm' 
                      : 'text-slate-400 hover:text-white hover:bg-white/5'
                  }`}
                >
                  {ratio}
                </button>
              ))}
            </div>
            
            <button
              type="submit"
              disabled={!prompt.trim() || isGenerating}
              className="flex items-center px-6 py-3 bg-gradient-to-r from-dulus-primary to-blue-600 hover:from-blue-500 hover:to-blue-400 text-white rounded-xl font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-[0_0_15px_rgba(59,130,246,0.4)]"
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
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {images.map((img) => (
          <div key={img.id} className="group relative rounded-2xl overflow-hidden border border-white/10 bg-black/50 aspect-square">
            <img src={img.url} alt={img.prompt} className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" />
            
            <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/40 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex flex-col justify-end p-4">
              <p className="text-sm text-slate-200 line-clamp-3 mb-3">{img.prompt}</p>
              <button 
                onClick={() => handleDownload(img.url, img.id)}
                className="flex items-center justify-center w-full py-2 bg-white/10 hover:bg-white/20 backdrop-blur-md rounded-lg text-white transition-colors border border-white/10"
              >
                <Download className="w-4 h-4 mr-2" /> Download
              </button>
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


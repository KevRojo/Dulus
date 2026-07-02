import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Mic, Square, Activity, AlertCircle } from 'lucide-react';
import { GoogleGenAI, LiveServerMessage, Modality } from '@google/genai';
import { decode, decodeAudioData, createPcmBlob, cn } from '../utils.ts';

const ai = new GoogleGenAI({ apiKey: process.env.API_KEY, vertexai: true });

export const VoiceView: React.FC = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [volume, setVolume] = useState(0);
  
  const sessionRef = useRef<any>(null);
  const audioContextsRef = useRef<{ input?: AudioContext; output?: AudioContext }>({});
  const streamRef = useRef<MediaStream | null>(null);
  const sourcesRef = useRef<Set<AudioBufferSourceNode>>(new Set());
  const nextStartTimeRef = useRef<number>(0);
  const visualizerIntervalRef = useRef<number | null>(null);

  const cleanup = useCallback(() => {
    if (sessionRef.current) {
      try { sessionRef.current.close(); } catch (e) {}
      sessionRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    if (audioContextsRef.current.input) {
      audioContextsRef.current.input.close();
    }
    if (audioContextsRef.current.output) {
      audioContextsRef.current.output.close();
    }
    audioContextsRef.current = {};
    
    sourcesRef.current.forEach(source => {
      try { source.stop(); } catch (e) {}
    });
    sourcesRef.current.clear();
    nextStartTimeRef.current = 0;
    
    if (visualizerIntervalRef.current) {
      window.clearInterval(visualizerIntervalRef.current);
    }
    
    setIsConnected(false);
    setIsConnecting(false);
    setVolume(0);
  }, []);

  useEffect(() => {
    return cleanup;
  }, [cleanup]);

  const startSession = async () => {
    setIsConnecting(true);
    setError(null);
    
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const inputAudioContext = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 16000 });
      const outputAudioContext = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 24000 });
      
      audioContextsRef.current = { input: inputAudioContext, output: outputAudioContext };
      const outputNode = outputAudioContext.createGain();
      outputNode.connect(outputAudioContext.destination);

      visualizerIntervalRef.current = window.setInterval(() => {
        setVolume(Math.random() * 0.4 + 0.1);
      }, 100);

      const sessionPromise = ai.live.connect({
        model: 'gemini-live-2.5-flash-native-audio',
        callbacks: {
          onopen: () => {
            setIsConnected(true);
            setIsConnecting(false);
            
            const source = inputAudioContext.createMediaStreamSource(stream);
            const scriptProcessor = inputAudioContext.createScriptProcessor(4096, 1, 1);
            
            scriptProcessor.onaudioprocess = (audioProcessingEvent) => {
              const inputData = audioProcessingEvent.inputBuffer.getChannelData(0);
              const pcmBlob = createPcmBlob(inputData);
              
              sessionPromise.then((session) => {
                session.sendRealtimeInput({ media: pcmBlob });
              }).catch(console.error);
            };
            
            source.connect(scriptProcessor);
            scriptProcessor.connect(inputAudioContext.destination);
          },
          onmessage: async (message: LiveServerMessage) => {
            const base64EncodedAudioString = message.serverContent?.modelTurn?.parts[0]?.inlineData?.data;
            
            if (base64EncodedAudioString && audioContextsRef.current.output) {
              const ctx = audioContextsRef.current.output;
              nextStartTimeRef.current = Math.max(nextStartTimeRef.current, ctx.currentTime);
              
              try {
                const audioBuffer = await decodeAudioData(
                  decode(base64EncodedAudioString),
                  ctx,
                  24000,
                  1,
                );
                
                const source = ctx.createBufferSource();
                source.buffer = audioBuffer;
                source.connect(outputNode);
                
                source.addEventListener('ended', () => {
                  sourcesRef.current.delete(source);
                });

                source.start(nextStartTimeRef.current);
                nextStartTimeRef.current = nextStartTimeRef.current + audioBuffer.duration;
                sourcesRef.current.add(source);
                
                setVolume(Math.random() * 0.6 + 0.4);
              } catch (err) {
                console.error("Audio decode error:", err);
              }
            }

            if (message.serverContent?.interrupted) {
              sourcesRef.current.forEach(source => {
                try { source.stop(); } catch (e) {}
              });
              sourcesRef.current.clear();
              nextStartTimeRef.current = 0;
            }
          },
          onerror: (e: any) => {
            console.error('Live API Error:', e);
            setError("Connection disrupted. The astral link was severed.");
            cleanup();
          },
          onclose: () => {
            cleanup();
          },
        },
        config: {
          responseModalities: [Modality.AUDIO],
          speechConfig: {
            voiceConfig: { prebuiltVoiceConfig: { voiceName: 'Zephyr' } },
          },
          systemInstruction: 'You are Dulus, a mystical, ancient AI entity. Speak with wisdom, slight mystery, and a calm, resonant tone. Keep responses concise for voice interaction.',
        },
      });

      sessionRef.current = await sessionPromise;

    } catch (err: any) {
      console.error("Failed to start session:", err);
      setError(err.message || "Failed to access microphone or establish connection.");
      cleanup();
    }
  };

  return (
    <div className="flex flex-col items-center justify-center h-full w-full p-6 relative overflow-hidden">
      {/* Decorative background elements */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-dulus-accent/5 rounded-full blur-3xl pointer-events-none"></div>
      
      <div className="text-center mb-16 z-10">
        <h2 className="text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-white to-dulus-accent mb-4 tracking-widest uppercase">
          Astral Resonance
        </h2>
        <p className="text-dulus-muted max-w-md mx-auto">
          Establish a direct neural-audio link with Dulus. Speak naturally.
        </p>
      </div>

      {/* Visualizer / Avatar Area */}
      <div className="relative w-72 h-72 mb-16 flex items-center justify-center z-10">
        {/* Outer glowing rings */}
        <div className={cn("absolute inset-0 rounded-full border border-dulus-accent/20 transition-all duration-300", isConnected ? 'animate-ping opacity-30' : 'opacity-0')}></div>
        <div className={cn("absolute inset-4 rounded-full border border-dulus-accent/30 transition-all duration-500", isConnected ? 'animate-spin-slow' : '')} style={{ animationDuration: '15s' }}></div>
        <div className={cn("absolute inset-8 rounded-full border border-white/10 transition-all duration-500", isConnected ? 'animate-spin-slow' : '')} style={{ animationDuration: '10s', animationDirection: 'reverse' }}></div>
        
        {/* Core entity representation */}
        <div 
          className="relative z-10 w-40 h-40 rounded-full bg-gradient-to-br from-dulus-panel to-black border-2 flex items-center justify-center transition-all duration-100 overflow-hidden shadow-[0_0_40px_rgba(251,191,36,0.1)]"
          style={{
            borderColor: isConnected ? `rgba(251, 191, 36, ${0.3 + volume * 0.5})` : 'rgba(255,255,255,0.1)',
            transform: isConnected ? `scale(${1 + volume * 0.15})` : 'scale(1)',
            boxShadow: isConnected ? `0 0 ${30 + volume * 50}px rgba(251, 191, 36, ${0.2 + volume * 0.4})` : ''
          }}
        >
          {isConnected ? (
            <Activity className="w-16 h-16 text-dulus-accent animate-pulse" />
          ) : (
            <Mic className="w-12 h-12 text-slate-600" />
          )}
          
          {/* Inner glow */}
          <div className="absolute inset-0 bg-dulus-accent mix-blend-overlay opacity-20"></div>
        </div>
      </div>

      {error && (
        <div className="mb-8 flex items-center text-red-400 bg-red-900/20 px-4 py-3 rounded-xl border border-red-500/20 z-10">
          <AlertCircle className="w-5 h-5 mr-2" />
          {error}
        </div>
      )}

      {/* Controls */}
      <button
        onClick={isConnected ? cleanup : startSession}
        disabled={isConnecting}
        className={cn(
          "group relative overflow-hidden rounded-2xl px-10 py-4 font-bold tracking-widest uppercase transition-all duration-300 z-10",
          isConnected 
            ? "bg-red-500/10 text-red-400 border border-red-500/30 hover:bg-red-500/20 hover:shadow-[0_0_20px_rgba(239,68,68,0.3)]" 
            : "bg-zinc-800/50 text-white border border-zinc-600 hover:border-dulus-accent hover:bg-zinc-800 hover:shadow-[0_0_20px_rgba(251,191,36,0.2)]",
          "disabled:opacity-50 disabled:cursor-not-allowed"
        )}
      >
        <div className="flex items-center space-x-3">
          {isConnecting ? (
            <>
              <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
              <span>ESTABLISHING LINK...</span>
            </>
          ) : isConnected ? (
            <>
              <Square className="w-5 h-5 fill-current" />
              <span>SEVER CONNECTION</span>
            </>
          ) : (
            <>
              <Mic className="w-5 h-5" />
              <span>INITIATE LINK</span>
            </>
          )}
        </div>
      </button>
    </div>
  );
};


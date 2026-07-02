import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Mic, Square, Activity, AlertCircle } from 'lucide-react';
import { GoogleGenAI, LiveServerMessage, Modality } from '@google/genai';
import { decode, decodeAudioData, createPcmBlob } from '../utils.ts';

const ai = new GoogleGenAI({ apiKey: process.env.API_KEY, vertexai: true });

export const LiveVoiceView: React.FC = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [volume, setVolume] = useState(0); // For visualizer
  
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

      // Simple volume visualizer simulation based on connection state
      visualizerIntervalRef.current = window.setInterval(() => {
        setVolume(Math.random() * 0.5 + 0.2); // Random pulse when connected
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
                
                // Boost visualizer when speaking
                setVolume(Math.random() * 0.5 + 0.5);
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
            voiceConfig: { prebuiltVoiceConfig: { voiceName: 'Zephyr' } }, // Mystical sounding voice
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
    <div className="flex flex-col items-center justify-center h-full w-full p-4">
      <div className="text-center mb-12">
        <h2 className="text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-white to-dulus-accent mb-4">
          Astral Resonance
        </h2>
        <p className="text-slate-400 max-w-md mx-auto">
          Establish a direct neural-audio link with Dulus. Speak naturally.
        </p>
      </div>

      {/* Visualizer / Avatar Area */}
      <div className="relative w-64 h-64 mb-12 flex items-center justify-center">
        {/* Outer glowing rings */}
        <div className={`absolute inset-0 rounded-full border-2 border-dulus-accent/20 transition-all duration-300 ${isConnected ? 'animate-ping opacity-20' : 'opacity-0'}`}></div>
        <div className={`absolute inset-4 rounded-full border border-dulus-primary/30 transition-all duration-500 ${isConnected ? 'animate-spin-slow' : ''}`} style={{ animationDuration: '10s' }}></div>
        
        {/* Core entity representation */}
        <div 
          className={`relative z-10 w-32 h-32 rounded-full bg-gradient-to-br from-dulus-panel to-black border-2 flex items-center justify-center transition-all duration-100 overflow-hidden shadow-[0_0_30px_rgba(59,130,246,0.2)]`}
          style={{
            borderColor: isConnected ? `rgba(251, 191, 36, ${0.3 + volume * 0.5})` : 'rgba(255,255,255,0.1)',
            transform: isConnected ? `scale(${1 + volume * 0.1})` : 'scale(1)',
            boxShadow: isConnected ? `0 0 ${20 + volume * 40}px rgba(251, 191, 36, ${0.2 + volume * 0.3})` : ''
          }}
        >
          {isConnected ? (
            <Activity className="w-12 h-12 text-dulus-accent animate-pulse" />
          ) : (
            <Mic className="w-10 h-10 text-slate-600" />
          )}
          
          {/* Inner glow */}
          <div className="absolute inset-0 bg-dulus-accent mix-blend-overlay opacity-20"></div>
        </div>
      </div>

      {error && (
        <div className="mb-8 flex items-center text-red-400 bg-red-900/20 px-4 py-3 rounded-xl border border-red-500/20">
          <AlertCircle className="w-5 h-5 mr-2" />
          {error}
        </div>
      )}

      {/* Controls */}
      <button
        onClick={isConnected ? cleanup : startSession}
        disabled={isConnecting}
        className={`group relative overflow-hidden rounded-full px-8 py-4 font-bold tracking-wider transition-all duration-300 ${
          isConnected 
            ? 'bg-red-500/10 text-red-400 border border-red-500/30 hover:bg-red-500/20 hover:shadow-[0_0_20px_rgba(239,68,68,0.3)]' 
            : 'bg-dulus-primary/20 text-white border border-dulus-primary/50 hover:bg-dulus-primary/30 hover:shadow-[0_0_20px_rgba(59,130,246,0.4)]'
        } disabled:opacity-50 disabled:cursor-not-allowed`}
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


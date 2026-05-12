import { useState, useEffect, useRef, useCallback } from 'react';
import { Play, RotateCcw, Trophy } from 'lucide-react';

const GRAVITY = 0.5;
const FLAP_POWER = -8;
const PIPE_WIDTH = 60;
const PIPE_GAP = 160;
const PIPE_SPEED = 3;
const BIRD_SIZE = 28;
const CANVAS_WIDTH = 400;
const CANVAS_HEIGHT = 520;

interface Pipe {
  x: number;
  topHeight: number;
  passed: boolean;
}

export default function FlappyBird() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [gameState, setGameState] = useState<'menu' | 'playing' | 'over'>('menu');
  const [score, setScore] = useState(0);
  const [highScore, setHighScore] = useState(() => {
    try { return parseInt(localStorage.getItem('flappy_highscore') || '0', 10); } catch { return 0; }
  });

  // Game refs (avoid re-renders during game loop)
  const birdY = useRef(CANVAS_HEIGHT / 2);
  const birdVel = useRef(0);
  const pipesRef = useRef<Pipe[]>([]);
  const frameRef = useRef(0);
  const scoreRef = useRef(0);
  const gameStateRef = useRef(gameState);
  const animationRef = useRef<number>(0);

  useEffect(() => { gameStateRef.current = gameState; }, [gameState]);

  const resetGame = () => {
    birdY.current = CANVAS_HEIGHT / 2;
    birdVel.current = 0;
    pipesRef.current = [];
    frameRef.current = 0;
    scoreRef.current = 0;
    setScore(0);
  };

  const flap = useCallback(() => {
    if (gameStateRef.current === 'menu') {
      resetGame();
      setGameState('playing');
      return;
    }
    if (gameStateRef.current === 'over') return;
    birdVel.current = FLAP_POWER;
  }, []);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const state = gameStateRef.current;

    // Sky
    ctx.fillStyle = '#4FC3F7';
    ctx.fillRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);

    // Ground
    ctx.fillStyle = '#8D6E63';
    ctx.fillRect(0, CANVAS_HEIGHT - 40, CANVAS_WIDTH, 40);
    ctx.fillStyle = '#66BB6A';
    ctx.fillRect(0, CANVAS_HEIGHT - 45, CANVAS_WIDTH, 8);

    // Clouds
    ctx.fillStyle = 'rgba(255,255,255,0.6)';
    [60, 200, 320].forEach((cx, i) => {
      const offset = (frameRef.current * 0.3 + i * 80) % (CANVAS_WIDTH + 60) - 30;
      ctx.beginPath();
      ctx.ellipse(offset, 60 + i * 30, 30, 15, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.beginPath();
      ctx.ellipse(offset + 20, 55 + i * 30, 22, 12, 0, 0, Math.PI * 2);
      ctx.fill();
    });

    // Pipes
    pipesRef.current.forEach(pipe => {
      ctx.fillStyle = '#4CAF50';
      ctx.strokeStyle = '#2E7D32';
      ctx.lineWidth = 2;
      // Top pipe
      ctx.fillRect(pipe.x, 0, PIPE_WIDTH, pipe.topHeight);
      ctx.strokeRect(pipe.x, 0, PIPE_WIDTH, pipe.topHeight);
      ctx.fillStyle = '#388E3C';
      ctx.fillRect(pipe.x - 2, pipe.topHeight - 24, PIPE_WIDTH + 4, 24);
      ctx.strokeRect(pipe.x - 2, pipe.topHeight - 24, PIPE_WIDTH + 4, 24);
      // Bottom pipe
      ctx.fillStyle = '#4CAF50';
      const bottomY = pipe.topHeight + PIPE_GAP;
      const bottomH = CANVAS_HEIGHT - 45 - bottomY;
      ctx.fillRect(pipe.x, bottomY, PIPE_WIDTH, bottomH);
      ctx.strokeRect(pipe.x, bottomY, PIPE_WIDTH, bottomH);
      ctx.fillStyle = '#388E3C';
      ctx.fillRect(pipe.x - 2, bottomY, PIPE_WIDTH + 4, 24);
      ctx.strokeRect(pipe.x - 2, bottomY, PIPE_WIDTH + 4, 24);
    });

    // Bird
    ctx.save();
    ctx.translate(80, birdY.current);
    ctx.rotate(Math.min(Math.max(birdVel.current * 0.05, -0.5), 0.5));
    // Body
    ctx.fillStyle = '#FFEB3B';
    ctx.beginPath();
    ctx.ellipse(0, 0, BIRD_SIZE / 2, BIRD_SIZE / 2.5, 0, 0, Math.PI * 2);
    ctx.fill();
    // Eye
    ctx.fillStyle = '#fff';
    ctx.beginPath();
    ctx.arc(6, -6, 7, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#212121';
    ctx.beginPath();
    ctx.arc(8, -6, 3, 0, Math.PI * 2);
    ctx.fill();
    // Beak
    ctx.fillStyle = '#FF9800';
    ctx.beginPath();
    ctx.moveTo(10, 0);
    ctx.lineTo(22, 4);
    ctx.lineTo(10, 8);
    ctx.closePath();
    ctx.fill();
    // Wing
    ctx.fillStyle = '#FBC02D';
    ctx.beginPath();
    ctx.ellipse(-4, 4, 10, 6, -0.3, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    // Score
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 36px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.strokeStyle = '#000';
    ctx.lineWidth = 3;
    ctx.strokeText(String(scoreRef.current), CANVAS_WIDTH / 2, 50);
    ctx.fillText(String(scoreRef.current), CANVAS_WIDTH / 2, 50);

    // Game over overlay
    if (state === 'over') {
      ctx.fillStyle = 'rgba(0,0,0,0.5)';
      ctx.fillRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);
      ctx.fillStyle = '#fff';
      ctx.font = 'bold 28px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Game Over', CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2 - 30);
      ctx.font = '16px Inter, sans-serif';
      ctx.fillText(`Score: ${scoreRef.current}`, CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2 + 10);
      if (scoreRef.current >= highScore && scoreRef.current > 0) {
        ctx.fillStyle = '#FFD700';
        ctx.fillText('New High Score!', CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2 + 35);
      }
    }

    // Menu overlay
    if (state === 'menu') {
      ctx.fillStyle = 'rgba(0,0,0,0.3)';
      ctx.fillRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);
      ctx.fillStyle = '#fff';
      ctx.font = 'bold 24px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Flappy Bird', CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2 - 20);
      ctx.font = '12px Inter, sans-serif';
      ctx.fillText('Click or press Space to start', CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2 + 15);
    }
  }, [highScore]);

  // Game loop
  useEffect(() => {
    const loop = () => {
      const state = gameStateRef.current;
      if (state === 'playing') {
        frameRef.current++;
        birdVel.current += GRAVITY;
        birdY.current += birdVel.current;

        // Generate pipes
        if (frameRef.current % 100 === 0) {
          const minH = 60;
          const maxH = CANVAS_HEIGHT - PIPE_GAP - 45 - 60;
          pipesRef.current.push({
            x: CANVAS_WIDTH,
            topHeight: minH + Math.random() * (maxH - minH),
            passed: false,
          });
        }

        // Move pipes
        pipesRef.current = pipesRef.current.filter(pipe => {
          pipe.x -= PIPE_SPEED;
          // Score
          if (!pipe.passed && pipe.x + PIPE_WIDTH < 80) {
            pipe.passed = true;
            scoreRef.current++;
            setScore(scoreRef.current);
          }
          return pipe.x > -PIPE_WIDTH;
        });

        // Collision with ground
        if (birdY.current + BIRD_SIZE / 2 > CANVAS_HEIGHT - 45) {
          birdY.current = CANVAS_HEIGHT - 45 - BIRD_SIZE / 2;
          gameStateRef.current = 'over';
          setGameState('over');
          if (scoreRef.current > highScore) {
            setHighScore(scoreRef.current);
            try { localStorage.setItem('flappy_highscore', String(scoreRef.current)); } catch { /* ignore */ }
          }
        }

        // Collision with ceiling
        if (birdY.current - BIRD_SIZE / 2 < 0) {
          birdY.current = BIRD_SIZE / 2;
          birdVel.current = 0;
        }

        // Collision with pipes
        pipesRef.current.forEach(pipe => {
          if (80 + BIRD_SIZE / 2 > pipe.x && 80 - BIRD_SIZE / 2 < pipe.x + PIPE_WIDTH) {
            if (birdY.current - BIRD_SIZE / 2 < pipe.topHeight || birdY.current + BIRD_SIZE / 2 > pipe.topHeight + PIPE_GAP) {
              gameStateRef.current = 'over';
              setGameState('over');
              if (scoreRef.current > highScore) {
                setHighScore(scoreRef.current);
                try { localStorage.setItem('flappy_highscore', String(scoreRef.current)); } catch { /* ignore */ }
              }
            }
          }
        });
      }

      draw();
      animationRef.current = requestAnimationFrame(loop);
    };

    animationRef.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(animationRef.current);
  }, [draw, highScore]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.code === 'Space') {
        e.preventDefault();
        if (gameStateRef.current === 'over') {
          resetGame();
          setGameState('playing');
        } else {
          flap();
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [flap]);

  return (
    <div className="flex flex-col items-center h-full" style={{ background: 'var(--bg-window)' }}>
      {/* Score bar */}
      <div className="w-full flex items-center justify-between px-3 py-1.5 border-b" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-panel)' }}>
        <div className="flex items-center gap-1"><Trophy size={12} style={{ color: 'var(--accent-secondary)' }} /><span className="text-xs" style={{ color: 'var(--text-secondary)' }}>Best: {highScore}</span></div>
        <span className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>{score}</span>
        {gameState === 'over' && (
          <button onClick={() => { resetGame(); setGameState('playing'); }} className="flex items-center gap-1 px-2 py-0.5 rounded-md text-xs" style={{ background: 'var(--accent-primary)', color: '#fff' }}>
            <RotateCcw size={10} /> Restart
          </button>
        )}
        {gameState === 'playing' && (
          <button onClick={() => { setGameState('menu'); resetGame(); }} className="flex items-center gap-1 px-2 py-0.5 rounded-md text-xs" style={{ color: 'var(--text-secondary)' }}>
            Stop
          </button>
        )}
      </div>
      <div className="flex-1 flex items-center justify-center p-2">
        <canvas
          ref={canvasRef}
          width={CANVAS_WIDTH}
          height={CANVAS_HEIGHT}
          onClick={flap}
          className="rounded-lg shadow-lg"
          style={{ maxWidth: '100%', maxHeight: '100%', imageRendering: 'pixelated', cursor: 'pointer' }}
        />
      </div>
    </div>
  );
}

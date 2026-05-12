import { useState, useEffect, useRef, useCallback } from 'react';
import { Circle, RotateCcw, User, Users } from 'lucide-react';

const CANVAS_W = 600;
const CANVAS_H = 360;
const PADDLE_W = 12;
const PADDLE_H = 60;
const BALL_SIZE = 12;
const WIN_SCORE = 7;
const INITIAL_SPEED = 5;

interface Ball {
  x: number;
  y: number;
  vx: number;
  vy: number;
  speed: number;
}

interface Paddle {
  y: number;
  score: number;
}

type GameMode = 'menu' | 'playing' | 'paused' | 'over';
type AIDifficulty = 'easy' | 'medium' | 'hard';

export default function Pong() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [mode, setMode] = useState<'1p' | '2p' | null>(null);
  const [aiDifficulty, setAiDifficulty] = useState<AIDifficulty>('medium');
  const [gameState, setGameState] = useState<GameMode>('menu');
  const [leftScore, setLeftScore] = useState(0);
  const [rightScore, setRightScore] = useState(0);
  const [winner, setWinner] = useState<string | null>(null);
  const [servingPlayer, setServingPlayer] = useState<'left' | 'right'>('left');

  const gameStateRef = useRef(gameState);
  const modeRef = useRef(mode);
  const aiDiffRef = useRef(aiDifficulty);
  const servingRef = useRef(servingPlayer);
  
  useEffect(() => { gameStateRef.current = gameState; }, [gameState]);
  useEffect(() => { modeRef.current = mode; }, [mode]);
  useEffect(() => { aiDiffRef.current = aiDifficulty; }, [aiDifficulty]);
  useEffect(() => { servingRef.current = servingPlayer; }, [servingPlayer]);

  const leftPaddle = useRef<Paddle>({ y: CANVAS_H / 2 - PADDLE_H / 2, score: 0 });
  const rightPaddle = useRef<Paddle>({ y: CANVAS_H / 2 - PADDLE_H / 2, score: 0 });
  const ball = useRef<Ball>({
    x: CANVAS_W / 2,
    y: CANVAS_H / 2,
    vx: INITIAL_SPEED,
    vy: INITIAL_SPEED * 0.6,
    speed: INITIAL_SPEED,
  });
  const keys = useRef<Record<string, boolean>>({});
  const waitingForServe = useRef(true);
  const animFrameRef = useRef<number>(0);

  const resetBall = useCallback((server: 'left' | 'right') => {
    ball.current = {
      x: CANVAS_W / 2,
      y: CANVAS_H / 2,
      vx: server === 'left' ? INITIAL_SPEED : -INITIAL_SPEED,
      vy: (Math.random() - 0.5) * INITIAL_SPEED * 1.2,
      speed: INITIAL_SPEED,
    };
    waitingForServe.current = true;
  }, []);

  const startGame = useCallback((gameMode: '1p' | '2p') => {
    setMode(gameMode);
    modeRef.current = gameMode;
    setGameState('playing');
    gameStateRef.current = 'playing';
    setLeftScore(0);
    setRightScore(0);
    leftPaddle.current = { y: CANVAS_H / 2 - PADDLE_H / 2, score: 0 };
    rightPaddle.current = { y: CANVAS_H / 2 - PADDLE_H / 2, score: 0 };
    setWinner(null);
    setServingPlayer('left');
    servingRef.current = 'left';
    resetBall('left');
  }, [resetBall]);

  // Game loop
  useEffect(() => {
    if (gameState !== 'playing') return;

    const update = () => {
      if (gameStateRef.current !== 'playing') {
        animFrameRef.current = requestAnimationFrame(update);
        return;
      }

      const ctx = canvasRef.current?.getContext('2d');
      if (!ctx) { animFrameRef.current = requestAnimationFrame(update); return; }

      // Move paddles
      const paddleSpeed = 6;
      if (keys.current['w'] || keys.current['W']) leftPaddle.current.y = Math.max(0, leftPaddle.current.y - paddleSpeed);
      if (keys.current['s'] || keys.current['S']) leftPaddle.current.y = Math.min(CANVAS_H - PADDLE_H, leftPaddle.current.y + paddleSpeed);
      
      if (modeRef.current === '2p') {
        if (keys.current['ArrowUp']) rightPaddle.current.y = Math.max(0, rightPaddle.current.y - paddleSpeed);
        if (keys.current['ArrowDown']) rightPaddle.current.y = Math.min(CANVAS_H - PADDLE_H, rightPaddle.current.y + paddleSpeed);
      } else {
        // AI
        const diff = aiDiffRef.current;
        const aiSpeed = diff === 'easy' ? 3 : diff === 'medium' ? 4.5 : 6;
        const reactionDelay = diff === 'easy' ? 40 : diff === 'medium' ? 20 : 5;
        const targetY = ball.current.y - PADDLE_H / 2;
        if (ball.current.vx > 0 || Math.random() > 0.3) {
          const dy = targetY - rightPaddle.current.y;
          if (Math.abs(dy) > reactionDelay) {
            rightPaddle.current.y += Math.sign(dy) * Math.min(Math.abs(dy), aiSpeed);
          }
        }
        rightPaddle.current.y = Math.max(0, Math.min(CANVAS_H - PADDLE_H, rightPaddle.current.y));
      }

      // Move ball if not waiting for serve
      if (!waitingForServe.current) {
        ball.current.x += ball.current.vx;
        ball.current.y += ball.current.vy;

        // Wall bounce (top/bottom)
        if (ball.current.y <= 0 || ball.current.y >= CANVAS_H - BALL_SIZE) {
          ball.current.vy *= -1;
          ball.current.y = ball.current.y <= 0 ? 0 : CANVAS_H - BALL_SIZE;
        }

        // Paddle collisions
        // Left paddle
        if (
          ball.current.x <= PADDLE_W + 10 &&
          ball.current.y + BALL_SIZE >= leftPaddle.current.y &&
          ball.current.y <= leftPaddle.current.y + PADDLE_H &&
          ball.current.vx < 0
        ) {
          const hitPos = (ball.current.y + BALL_SIZE / 2 - leftPaddle.current.y) / PADDLE_H;
          const angle = (hitPos - 0.5) * Math.PI * 0.8;
          ball.current.speed = Math.min(ball.current.speed + 0.3, 12);
          ball.current.vx = Math.abs(ball.current.speed * Math.cos(angle));
          ball.current.vy = ball.current.speed * Math.sin(angle);
          ball.current.x = PADDLE_W + 11;
        }

        // Right paddle
        if (
          ball.current.x + BALL_SIZE >= CANVAS_W - PADDLE_W - 10 &&
          ball.current.y + BALL_SIZE >= rightPaddle.current.y &&
          ball.current.y <= rightPaddle.current.y + PADDLE_H &&
          ball.current.vx > 0
        ) {
          const hitPos = (ball.current.y + BALL_SIZE / 2 - rightPaddle.current.y) / PADDLE_H;
          const angle = (hitPos - 0.5) * Math.PI * 0.8;
          ball.current.speed = Math.min(ball.current.speed + 0.3, 12);
          ball.current.vx = -Math.abs(ball.current.speed * Math.cos(angle));
          ball.current.vy = ball.current.speed * Math.sin(angle);
          ball.current.x = CANVAS_W - PADDLE_W - 10 - BALL_SIZE;
        }

        // Score
        if (ball.current.x < -BALL_SIZE) {
          rightPaddle.current.score++;
          setRightScore(rightPaddle.current.score);
          if (rightPaddle.current.score >= WIN_SCORE) {
            setWinner(modeRef.current === '1p' ? 'Computer' : 'Player 2');
            setGameState('over');
            gameStateRef.current = 'over';
          } else {
            setServingPlayer('left');
            servingRef.current = 'left';
            resetBall('left');
          }
        } else if (ball.current.x > CANVAS_W) {
          leftPaddle.current.score++;
          setLeftScore(leftPaddle.current.score);
          if (leftPaddle.current.score >= WIN_SCORE) {
            setWinner('Player 1');
            setGameState('over');
            gameStateRef.current = 'over';
          } else {
            setServingPlayer('right');
            servingRef.current = 'right';
            resetBall('right');
          }
        }
      }

      // Render
      ctx.fillStyle = '#000';
      ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);

      // Net
      ctx.setLineDash([8, 8]);
      ctx.strokeStyle = 'rgba(255,255,255,0.3)';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(CANVAS_W / 2, 0);
      ctx.lineTo(CANVAS_W / 2, CANVAS_H);
      ctx.stroke();
      ctx.setLineDash([]);

      // Paddles
      ctx.fillStyle = '#fff';
      ctx.fillRect(10, leftPaddle.current.y, PADDLE_W, PADDLE_H);
      ctx.fillRect(CANVAS_W - 10 - PADDLE_W, rightPaddle.current.y, PADDLE_W, PADDLE_H);

      // Ball
      ctx.fillStyle = '#fff';
      ctx.beginPath();
      ctx.arc(ball.current.x + BALL_SIZE / 2, ball.current.y + BALL_SIZE / 2, BALL_SIZE / 2, 0, Math.PI * 2);
      ctx.fill();

      // Score
      ctx.font = 'bold 36px Inter, sans-serif';
      ctx.fillStyle = 'rgba(255,255,255,0.5)';
      ctx.textAlign = 'center';
      ctx.fillText(`${leftPaddle.current.score} - ${rightPaddle.current.score}`, CANVAS_W / 2, 40);

      // Serve indicator
      if (waitingForServe.current) {
        ctx.font = '14px Inter, sans-serif';
        ctx.fillStyle = 'rgba(255,255,255,0.6)';
        ctx.fillText('Press SPACE to serve', CANVAS_W / 2, CANVAS_H / 2 + 50);
      }

      animFrameRef.current = requestAnimationFrame(update);
    };

    animFrameRef.current = requestAnimationFrame(update);
    return () => cancelAnimationFrame(animFrameRef.current);
  }, [gameState, resetBall]);

  // Keyboard
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      keys.current[e.key] = true;
      if (e.key === ' ' && gameStateRef.current === 'playing' && waitingForServe.current) {
        e.preventDefault();
        waitingForServe.current = false;
      }
      if ((e.key === 'p' || e.key === 'P') && gameStateRef.current === 'playing') {
        setGameState('paused');
        gameStateRef.current = 'paused';
      } else if ((e.key === 'p' || e.key === 'P') && gameStateRef.current === 'paused') {
        setGameState('playing');
        gameStateRef.current = 'playing';
      }
    };
    const handleKeyUp = (e: KeyboardEvent) => {
      keys.current[e.key] = false;
    };
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, []);

  return (
    <div className="flex flex-col items-center h-full" style={{ background: 'var(--bg-window)', padding: 8 }}>
      {mode === null ? (
        <div className="flex flex-col items-center justify-center h-full gap-4">
          <Circle size={36} style={{ color: 'var(--accent-primary)' }} />
          <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--accent-primary)' }}>Pong</div>
          <button onClick={() => startGame('1p')} className="flex items-center gap-2" style={{ padding: '12px 32px', background: 'var(--accent-primary)', color: '#fff', borderRadius: 10, border: 'none', fontSize: 15, fontWeight: 600, cursor: 'pointer', width: 220 }}>
            <User size={18} /> 1 Player
          </button>
          <button onClick={() => startGame('2p')} className="flex items-center gap-2" style={{ padding: '12px 32px', background: 'var(--bg-hover)', color: 'var(--text-primary)', borderRadius: 10, border: '1px solid var(--border-default)', fontSize: 15, fontWeight: 600, cursor: 'pointer', width: 220 }}>
            <Users size={18} /> 2 Players
          </button>
        </div>
      ) : (
        <>
          {/* HUD */}
          <div className="flex items-center justify-between w-full mb-2" style={{ maxWidth: CANVAS_W }}>
            <div className="flex items-center gap-2">
              {mode === '1p' && (
                <div className="flex gap-1">
                  {(['easy', 'medium', 'hard'] as AIDifficulty[]).map(d => (
                    <button key={d} onClick={() => { setAiDifficulty(d); startGame('1p'); }}
                      style={{ padding: '2px 8px', borderRadius: 4, border: 'none', fontSize: 10, cursor: 'pointer', background: aiDifficulty === d ? 'var(--accent-primary)' : 'var(--bg-hover)', color: aiDifficulty === d ? '#fff' : 'var(--text-secondary)' }}>
                      {d.charAt(0).toUpperCase() + d.slice(1)}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div className="flex gap-2">
              {gameState === 'playing' && (
                <button onClick={() => { setGameState('paused'); gameStateRef.current = 'paused'; }} style={{ padding: '4px 12px', background: 'var(--bg-hover)', color: 'var(--text-primary)', borderRadius: 6, border: '1px solid var(--border-default)', fontSize: 12, cursor: 'pointer' }}>
                  Pause
                </button>
              )}
              {gameState === 'paused' && (
                <button onClick={() => { setGameState('playing'); gameStateRef.current = 'playing'; }} style={{ padding: '4px 12px', background: 'var(--accent-primary)', color: '#fff', borderRadius: 6, border: 'none', fontSize: 12, cursor: 'pointer' }}>
                  Resume
                </button>
              )}
              <button onClick={() => { setMode(null); setGameState('menu'); gameStateRef.current = 'menu'; }} style={{ padding: '4px 12px', background: 'var(--bg-hover)', color: 'var(--text-primary)', borderRadius: 6, border: '1px solid var(--border-default)', fontSize: 12, cursor: 'pointer' }}>
                <RotateCcw size={14} />
              </button>
            </div>
          </div>

          <canvas
            ref={canvasRef}
            width={CANVAS_W}
            height={CANVAS_H}
            style={{ border: '2px solid var(--border-default)', borderRadius: 4 }}
          />

          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
            W/S: Left paddle {mode === '2p' ? '| ↑/↓: Right paddle' : ''} | Space: Serve | P: Pause
          </div>

          {/* Game Over overlay */}
          {gameState === 'over' && (
            <div className="absolute inset-0 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.7)', zIndex: 20, borderRadius: 12 }}>
              <div className="flex flex-col items-center" style={{ background: 'var(--bg-window)', padding: 24, borderRadius: 16 }}>
                <span style={{ fontSize: 22, fontWeight: 700, color: winner === 'Player 1' ? 'var(--accent-success)' : 'var(--accent-error)' }}>
                  {winner === 'Player 1' ? 'You Win!' : `${winner} Wins!`}
                </span>
                <span style={{ fontSize: 16, color: 'var(--text-primary)', marginTop: 4 }}>{leftScore} - {rightScore}</span>
                <button onClick={() => startGame(mode)} style={{ marginTop: 12, padding: '8px 24px', background: 'var(--accent-primary)', color: '#fff', borderRadius: 8, border: 'none', fontSize: 14, fontWeight: 600, cursor: 'pointer' }}>
                  Play Again
                </button>
              </div>
            </div>
          )}

          {/* Pause overlay */}
          {gameState === 'paused' && (
            <div className="absolute inset-0 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.5)', zIndex: 10, borderRadius: 12 }}>
              <div className="flex flex-col items-center" style={{ background: 'var(--bg-window)', padding: 20, borderRadius: 12 }}>
                <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)' }}>Paused</span>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

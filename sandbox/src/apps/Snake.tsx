import { useState, useEffect, useCallback, useRef } from 'react';

const GRID_SIZE = 20;
const CELL_SIZE = 18;
const INITIAL_SPEED = 150;

interface Position {
  x: number;
  y: number;
}

type Direction = 'UP' | 'DOWN' | 'LEFT' | 'RIGHT';

function getHighScore(): number {
  const val = localStorage.getItem('snake_highscore');
  return val ? parseInt(val, 10) : 0;
}
function setHighScore(score: number) {
  const current = getHighScore();
  if (score > current) localStorage.setItem('snake_highscore', String(score));
}

function randomFood(snake: Position[]): Position {
  let pos: Position;
  do {
    pos = { x: Math.floor(Math.random() * GRID_SIZE), y: Math.floor(Math.random() * GRID_SIZE) };
  } while (snake.some(s => s.x === pos.x && s.y === pos.y));
  return pos;
}

export default function Snake() {
  const [snake, setSnake] = useState<Position[]>([{ x: 10, y: 10 }, { x: 9, y: 10 }, { x: 8, y: 10 }]);
  const [direction, setDirection] = useState<Direction>('RIGHT');
  const [food, setFood] = useState<Position>({ x: 15, y: 10 });
  const [specialFood, setSpecialFood] = useState<Position | null>(null);
  const [specialTimer, setSpecialTimer] = useState(0);
  const [gameState, setGameState] = useState<'menu' | 'playing' | 'paused' | 'over'>('menu');
  const [score, setScore] = useState(0);
  const [speed, setSpeed] = useState(INITIAL_SPEED);
  const dirRef = useRef<Direction>('RIGHT');
  const snakeRef = useRef<Position[]>(snake);
  const foodRef = useRef<Position>(food);
  const specialRef = useRef<Position | null>(null);
  const gameStateRef = useRef(gameState);
  const scoreRef = useRef(0);
  const speedRef = useRef(INITIAL_SPEED);

  useEffect(() => { dirRef.current = direction; }, [direction]);
  useEffect(() => { snakeRef.current = snake; }, [snake]);
  useEffect(() => { foodRef.current = food; }, [food]);
  useEffect(() => { specialRef.current = specialFood; }, [specialFood]);
  useEffect(() => { gameStateRef.current = gameState; }, [gameState]);
  useEffect(() => { scoreRef.current = score; }, [score]);
  useEffect(() => { speedRef.current = speed; }, [speed]);

  const resetGame = useCallback(() => {
    const startSnake = [{ x: 10, y: 10 }, { x: 9, y: 10 }, { x: 8, y: 10 }];
    setSnake(startSnake);
    snakeRef.current = startSnake;
    setDirection('RIGHT');
    dirRef.current = 'RIGHT';
    const startFood = randomFood(startSnake);
    setFood(startFood);
    foodRef.current = startFood;
    setSpecialFood(null);
    specialRef.current = null;
    setScore(0);
    scoreRef.current = 0;
    setSpeed(INITIAL_SPEED);
    speedRef.current = INITIAL_SPEED;
    setGameState('playing');
    gameStateRef.current = 'playing';
  }, []);

  // Game loop
  useEffect(() => {
    if (gameState !== 'playing') return;
    const interval = setInterval(() => {
      const currentSnake = snakeRef.current;
      const currentDir = dirRef.current;
      const head = { ...currentSnake[0] };
      switch (currentDir) {
        case 'UP': head.y--; break;
        case 'DOWN': head.y++; break;
        case 'LEFT': head.x--; break;
        case 'RIGHT': head.x++; break;
      }
      // Wall collision
      if (head.x < 0 || head.x >= GRID_SIZE || head.y < 0 || head.y >= GRID_SIZE) {
        setGameState('over');
        gameStateRef.current = 'over';
        setHighScore(scoreRef.current);
        return;
      }
      // Self collision
      if (currentSnake.some((s, i) => i > 0 && s.x === head.x && s.y === head.y)) {
        setGameState('over');
        gameStateRef.current = 'over';
        setHighScore(scoreRef.current);
        return;
      }
      const newSnake = [head, ...currentSnake];
      const currentFood = foodRef.current;
      const currentSpecial = specialRef.current;
      // Eat food
      if (head.x === currentFood.x && head.y === currentFood.y) {
        const newScore = scoreRef.current + 10;
        scoreRef.current = newScore;
        setScore(newScore);
        const newFood = randomFood(newSnake);
        setFood(newFood);
        foodRef.current = newFood;
        if (newScore % 50 === 0) {
          const sf = randomFood(newSnake);
          setSpecialFood(sf);
          specialRef.current = sf;
          setSpecialTimer(5);
        }
        const newSpeed = Math.max(60, INITIAL_SPEED - Math.floor(newScore / 50) * 15);
        speedRef.current = newSpeed;
        setSpeed(newSpeed);
      } else if (currentSpecial && head.x === currentSpecial.x && head.y === currentSpecial.y) {
        const newScore = scoreRef.current + 50;
        scoreRef.current = newScore;
        setScore(newScore);
        setSpecialFood(null);
        specialRef.current = null;
      } else {
        newSnake.pop();
      }
      setSnake(newSnake);
      snakeRef.current = newSnake;
    }, speed);
    return () => clearInterval(interval);
  }, [gameState, speed]);

  // Special food timer
  useEffect(() => {
    if (specialFood && gameState === 'playing') {
      const timer = setInterval(() => {
        setSpecialTimer(t => {
          if (t <= 1) {
            setSpecialFood(null);
            specialRef.current = null;
            return 0;
          }
          return t - 1;
        });
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [specialFood, gameState]);

  // Keyboard controls
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (gameStateRef.current === 'menu' && ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' '].includes(e.key)) {
        resetGame();
        return;
      }
      if (e.key === 'p' || e.key === 'P' || e.key === ' ') {
        if (gameStateRef.current === 'playing') {
          setGameState('paused');
          gameStateRef.current = 'paused';
        } else if (gameStateRef.current === 'paused') {
          setGameState('playing');
          gameStateRef.current = 'playing';
        }
        return;
      }
      if (gameStateRef.current !== 'playing') return;
      switch (e.key) {
        case 'ArrowUp': case 'w': case 'W':
          if (dirRef.current !== 'DOWN') setDirection('UP');
          break;
        case 'ArrowDown': case 's': case 'S':
          if (dirRef.current !== 'UP') setDirection('DOWN');
          break;
        case 'ArrowLeft': case 'a': case 'A':
          if (dirRef.current !== 'RIGHT') setDirection('LEFT');
          break;
        case 'ArrowRight': case 'd': case 'D':
          if (dirRef.current !== 'LEFT') setDirection('RIGHT');
          break;
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [resetGame]);

  const canvasSize = GRID_SIZE * CELL_SIZE;

  return (
    <div className="flex flex-col items-center h-full select-none" style={{ background: 'var(--bg-window)', padding: 8 }} tabIndex={0}>
      {/* Score panel */}
      <div className="flex items-center justify-between w-full mb-2" style={{ padding: '4px 8px', background: 'var(--bg-titlebar)', borderRadius: 8 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>Score: {score}</div>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Best: {getHighScore()}</div>
        <div className="flex gap-1">
          {[1, 2, 3, 4, 5].map(l => (
            <div key={l} style={{
              width: 8, height: 8, borderRadius: '50%',
              background: l <= Math.ceil((INITIAL_SPEED - speed) / 15) + 1 ? 'var(--accent-primary)' : 'var(--border-default)'
            }} />
          ))}
        </div>
      </div>

      {/* Game area */}
      <div style={{ position: 'relative', width: canvasSize, height: canvasSize, background: '#1A1A1A', border: '2px solid var(--border-default)', borderRadius: 4 }}>
        {gameState === 'menu' && (
          <div className="absolute inset-0 flex flex-col items-center justify-center" style={{ background: 'rgba(0,0,0,0.8)', zIndex: 10 }}>
            <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--accent-primary)', marginBottom: 8 }}>Snake</div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 16 }}>Arrow keys or WASD to move</div>
            <button onClick={resetGame} style={{ padding: '8px 24px', background: 'var(--accent-primary)', color: '#fff', borderRadius: 8, border: 'none', fontSize: 14, fontWeight: 600, cursor: 'pointer' }}>
              Start Game
            </button>
          </div>
        )}
        {gameState === 'paused' && (
          <div className="absolute inset-0 flex flex-col items-center justify-center" style={{ background: 'rgba(0,0,0,0.7)', zIndex: 10 }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 12 }}>Paused</div>
            <button onClick={() => { setGameState('playing'); gameStateRef.current = 'playing'; }} style={{ padding: '6px 20px', background: 'var(--accent-primary)', color: '#fff', borderRadius: 8, border: 'none', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
              Resume
            </button>
          </div>
        )}
        {gameState === 'over' && (
          <div className="absolute inset-0 flex flex-col items-center justify-center" style={{ background: 'rgba(0,0,0,0.8)', zIndex: 10 }}>
            <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--accent-error)', marginBottom: 4 }}>Game Over</div>
            <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>Score: {score}</div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 12 }}>Best: {getHighScore()}</div>
            <button onClick={resetGame} style={{ padding: '8px 24px', background: 'var(--accent-primary)', color: '#fff', borderRadius: 8, border: 'none', fontSize: 14, fontWeight: 600, cursor: 'pointer' }}>
              Play Again
            </button>
          </div>
        )}

        {/* Grid cells */}
        {Array.from({ length: GRID_SIZE }, (_, y) =>
          Array.from({ length: GRID_SIZE }, (_, x) => {
            const isSnake = snake.some((s, i) => s.x === x && s.y === y);
            const isHead = snake[0]?.x === x && snake[0]?.y === y;
            const isFood = food.x === x && food.y === y;
            const isSpecial = specialFood?.x === x && specialFood?.y === y;
            let bg = 'transparent';
            if (isHead) bg = '#388E3C';
            else if (isSnake) bg = '#4CAF50';
            else if (isFood) bg = '#F44336';
            else if (isSpecial) bg = '#FFD700';
            return (
              <div
                key={`${x}-${y}`}
                style={{
                  position: 'absolute',
                  left: x * CELL_SIZE,
                  top: y * CELL_SIZE,
                  width: CELL_SIZE - 1,
                  height: CELL_SIZE - 1,
                  background: bg,
                  borderRadius: isHead ? 5 : isSnake ? 3 : isFood || isSpecial ? '50%' : 0,
                  transition: isFood || isSpecial ? 'transform 0.3s' : 'none',
                  transform: isFood ? 'scale(1)' : undefined,
                }}
              />
            );
          })
        )}
      </div>

      <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>P: Pause | Arrow keys / WASD: Move</div>
    </div>
  );
}

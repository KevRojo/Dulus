import { useState, useEffect, useCallback } from 'react';
import { RotateCcw, Undo2 } from 'lucide-react';

const GRID_SIZE = 4;

const TILE_COLORS: Record<number, { bg: string; text: string }> = {
  2:    { bg: '#EDE0C8', text: '#776E65' },
  4:    { bg: '#EDE0C8', text: '#776E65' },
  8:    { bg: '#F2B179', text: '#fff' },
  16:   { bg: '#F59563', text: '#fff' },
  32:   { bg: '#F67C5F', text: '#fff' },
  64:   { bg: '#F65E3B', text: '#fff' },
  128:  { bg: '#EDCF72', text: '#fff' },
  256:  { bg: '#EDCC61', text: '#fff' },
  512:  { bg: '#EDC850', text: '#fff' },
  1024: { bg: '#EDC53F', text: '#fff' },
  2048: { bg: '#EDC22E', text: '#fff' },
};

function getDefaultTileColor(value: number) {
  return value > 2048 ? { bg: '#3C3A32', text: '#fff' } : (TILE_COLORS[value] || { bg: '#3C3A32', text: '#fff' });
}

function getHighScore(): number {
  const val = localStorage.getItem('2048_highscore');
  return val ? parseInt(val, 10) : 0;
}
function saveHighScore(score: number) {
  const current = getHighScore();
  if (score > current) localStorage.setItem('2048_highscore', String(score));
}

function addRandomTile(board: number[][]): number[][] {
  const empty: [number, number][] = [];
  for (let r = 0; r < GRID_SIZE; r++) {
    for (let c = 0; c < GRID_SIZE; c++) {
      if (board[r][c] === 0) empty.push([r, c]);
    }
  }
  if (empty.length === 0) return board;
  const [r, c] = empty[Math.floor(Math.random() * empty.length)];
  const newBoard = board.map(row => [...row]);
  newBoard[r][c] = Math.random() < 0.9 ? 2 : 4;
  return newBoard;
}

function createBoard(): number[][] {
  let board = Array.from({ length: GRID_SIZE }, () => Array(GRID_SIZE).fill(0));
  board = addRandomTile(board);
  board = addRandomTile(board);
  return board;
}

function slideRow(row: number[]): { row: number[]; score: number } {
  let filtered = row.filter(v => v !== 0);
  let score = 0;
  for (let i = 0; i < filtered.length - 1; i++) {
    if (filtered[i] === filtered[i + 1]) {
      filtered[i] *= 2;
      score += filtered[i];
      filtered[i + 1] = 0;
    }
  }
  filtered = filtered.filter(v => v !== 0);
  while (filtered.length < GRID_SIZE) filtered.push(0);
  return { row: filtered, score };
}

function moveLeft(board: number[][]): { board: number[][]; score: number; moved: boolean } {
  const newBoard: number[][] = [];
  let totalScore = 0;
  let moved = false;
  for (const row of board) {
    const result = slideRow([...row]);
    newBoard.push(result.row);
    totalScore += result.score;
    if (result.row.some((v, i) => v !== row[i])) moved = true;
  }
  return { board: newBoard, score: totalScore, moved };
}

function rotateBoard(board: number[][]): number[][] {
  const n = board.length;
  const result: number[][] = Array.from({ length: n }, () => Array(n).fill(0));
  for (let r = 0; r < n; r++) {
    for (let c = 0; c < n; c++) {
      result[c][n - 1 - r] = board[r][c];
    }
  }
  return result;
}

function moveBoard(board: number[][], direction: 'left' | 'right' | 'up' | 'down'): { board: number[][]; score: number; moved: boolean } {
  let working = board.map(r => [...r]);
  let rotations = 0;
  if (direction === 'up') rotations = 3;
  else if (direction === 'right') rotations = 2;
  else if (direction === 'down') rotations = 1;
  for (let i = 0; i < rotations; i++) working = rotateBoard(working);
  const result = moveLeft(working);
  working = result.board;
  for (let i = 0; i < (4 - rotations) % 4; i++) working = rotateBoard(working);
  return { board: working, score: result.score, moved: result.moved };
}

function hasMoves(board: number[][]): boolean {
  for (let r = 0; r < GRID_SIZE; r++) {
    for (let c = 0; c < GRID_SIZE; c++) {
      if (board[r][c] === 0) return true;
      if (c < GRID_SIZE - 1 && board[r][c] === board[r][c + 1]) return true;
      if (r < GRID_SIZE - 1 && board[r][c] === board[r + 1][c]) return true;
    }
  }
  return false;
}

export default function Game2048() {
  const [board, setBoard] = useState<number[][]>(createBoard);
  const [score, setScore] = useState(0);
  const [bestScore, setBestScore] = useState(getHighScore);
  const [previousBoard, setPreviousBoard] = useState<number[][] | null>(null);
  const [previousScore, setPreviousScore] = useState(0);
  const [gameOver, setGameOver] = useState(false);
  const [won, setWon] = useState(false);
  const [continuePlaying, setContinuePlaying] = useState(false);

  const handleMove = useCallback((direction: 'left' | 'right' | 'up' | 'down') => {
    if (gameOver) return;
    setPreviousBoard(board.map(r => [...r]));
    setPreviousScore(score);
    const result = moveBoard(board, direction);
    if (!result.moved) return;
    const newBoard = addRandomTile(result.board);
    const newScore = score + result.score;
    setBoard(newBoard);
    setScore(newScore);
    saveHighScore(newScore);
    setBestScore(getHighScore());
    if (!hasMoves(newBoard)) setGameOver(true);
    if (!continuePlaying && newBoard.some(row => row.includes(2048))) setWon(true);
  }, [board, score, gameOver, continuePlaying]);

  const undo = useCallback(() => {
    if (!previousBoard) return;
    setBoard(previousBoard);
    setScore(previousScore);
    setPreviousBoard(null);
    setGameOver(false);
  }, [previousBoard, previousScore]);

  const newGame = useCallback(() => {
    const b = createBoard();
    setBoard(b);
    setScore(0);
    setPreviousBoard(null);
    setGameOver(false);
    setWon(false);
    setContinuePlaying(false);
  }, []);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      switch (e.key) {
        case 'ArrowLeft': case 'a': case 'A': e.preventDefault(); handleMove('left'); break;
        case 'ArrowRight': case 'd': case 'D': e.preventDefault(); handleMove('right'); break;
        case 'ArrowUp': case 'w': case 'W': e.preventDefault(); handleMove('up'); break;
        case 'ArrowDown': case 's': case 'S': e.preventDefault(); handleMove('down'); break;
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [handleMove]);

  // Touch support
  const [touchStart, setTouchStart] = useState<{ x: number; y: number } | null>(null);
  const handleTouchStart = (e: React.TouchEvent) => {
    const t = e.touches[0];
    setTouchStart({ x: t.clientX, y: t.clientY });
  };
  const handleTouchEnd = (e: React.TouchEvent) => {
    if (!touchStart) return;
    const t = e.changedTouches[0];
    const dx = t.clientX - touchStart.x;
    const dy = t.clientY - touchStart.y;
    if (Math.abs(dx) < 20 && Math.abs(dy) < 20) return;
    if (Math.abs(dx) > Math.abs(dy)) {
      handleMove(dx > 0 ? 'right' : 'left');
    } else {
      handleMove(dy > 0 ? 'down' : 'up');
    }
    setTouchStart(null);
  };

  return (
    <div className="flex flex-col items-center h-full select-none" style={{ background: 'var(--bg-window)', padding: 16 }} tabIndex={0}
      onTouchStart={handleTouchStart} onTouchEnd={handleTouchEnd}>
      {/* Header */}
      <div className="flex items-center justify-between w-full mb-3" style={{ maxWidth: 360 }}>
        <div style={{ fontSize: 32, fontWeight: 800, color: 'var(--accent-primary)' }}>2048</div>
        <div className="flex gap-2">
          <div className="flex flex-col items-center" style={{ background: 'var(--bg-titlebar)', borderRadius: 4, padding: '4px 12px' }}>
            <span style={{ fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Score</span>
            <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>{score}</span>
          </div>
          <div className="flex flex-col items-center" style={{ background: 'var(--bg-titlebar)', borderRadius: 4, padding: '4px 12px' }}>
            <span style={{ fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Best</span>
            <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>{bestScore}</span>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="flex gap-2 mb-3">
        <button onClick={newGame} style={{ padding: '6px 16px', background: 'var(--accent-primary)', color: '#fff', borderRadius: 8, border: 'none', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
          <RotateCcw size={14} style={{ display: 'inline', marginRight: 4 }} />New Game
        </button>
        <button onClick={undo} disabled={!previousBoard} style={{ padding: '6px 16px', background: 'var(--bg-hover)', color: 'var(--text-primary)', borderRadius: 8, border: '1px solid var(--border-default)', fontSize: 13, cursor: previousBoard ? 'pointer' : 'not-allowed', opacity: previousBoard ? 1 : 0.4 }}>
          <Undo2 size={14} style={{ display: 'inline', marginRight: 4 }} />Undo
        </button>
      </div>

      {/* Board */}
      <div style={{
        display: 'grid', gridTemplateColumns: `repeat(${GRID_SIZE}, 78px)`,
        gap: 8, background: 'var(--bg-titlebar)', borderRadius: 8, padding: 8,
      }}>
        {board.map((row, r) =>
          row.map((value, c) => {
            const colors = value > 0 ? getDefaultTileColor(value) : { bg: 'rgba(255,255,255,0.05)', text: 'transparent' };
            return (
              <div key={`${r}-${c}`} className="flex items-center justify-center"
                style={{
                  width: 78, height: 78,
                  background: colors.bg,
                  borderRadius: 6,
                  fontSize: value >= 1000 ? 24 : 28,
                  fontWeight: 700,
                  color: colors.text,
                  transition: 'all 0.1s ease',
                }}>
                {value > 0 ? value : ''}
              </div>
            );
          })
        )}
      </div>

      {/* Game Over overlay */}
      {gameOver && (
        <div className="absolute inset-0 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.7)', zIndex: 20, borderRadius: 12 }}>
          <div className="flex flex-col items-center" style={{ background: 'var(--bg-window)', padding: 24, borderRadius: 16 }}>
            <span style={{ fontSize: 22, fontWeight: 700, color: 'var(--accent-error)' }}>Game Over!</span>
            <span style={{ fontSize: 16, color: 'var(--text-primary)', marginTop: 8 }}>Final Score: {score}</span>
            <button onClick={newGame} style={{ marginTop: 12, padding: '8px 24px', background: 'var(--accent-primary)', color: '#fff', borderRadius: 8, border: 'none', fontSize: 14, fontWeight: 600, cursor: 'pointer' }}>
              Try Again
            </button>
          </div>
        </div>
      )}

      {/* Win overlay */}
      {won && !continuePlaying && (
        <div className="absolute inset-0 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.7)', zIndex: 20, borderRadius: 12 }}>
          <div className="flex flex-col items-center" style={{ background: 'var(--bg-window)', padding: 24, borderRadius: 16 }}>
            <span style={{ fontSize: 22, fontWeight: 700, color: 'var(--accent-success)' }}>You Win!</span>
            <span style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>You reached 2048!</span>
            <div className="flex gap-2 mt-3">
              <button onClick={() => setContinuePlaying(true)} style={{ padding: '8px 20px', background: 'var(--accent-primary)', color: '#fff', borderRadius: 8, border: 'none', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
                Continue
              </button>
              <button onClick={newGame} style={{ padding: '8px 20px', background: 'var(--bg-hover)', color: 'var(--text-primary)', borderRadius: 8, border: '1px solid var(--border-default)', fontSize: 13, cursor: 'pointer' }}>
                New Game
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

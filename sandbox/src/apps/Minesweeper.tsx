import { useState, useEffect, useCallback, useRef } from 'react';
import { Bomb, Clock, Flag, RotateCcw } from 'lucide-react';

type CellState = 'hidden' | 'revealed' | 'flagged' | 'questioned';
interface Cell {
  isMine: boolean;
  neighborMines: number;
  state: CellState;
}

interface Difficulty {
  name: string;
  rows: number;
  cols: number;
  mines: number;
}

const DIFFICULTIES: Difficulty[] = [
  { name: 'Beginner', rows: 8, cols: 8, mines: 10 },
  { name: 'Intermediate', rows: 16, cols: 16, mines: 40 },
  { name: 'Expert', rows: 16, cols: 30, mines: 99 },
];

const NUMBER_COLORS: Record<number, string> = {
  1: '#2196F3', 2: '#4CAF50', 3: '#F44336', 4: '#7C4DFF',
  5: '#8B0000', 6: '#00BCD4', 7: '#212121', 8: '#757575',
};

function createBoard(rows: number, cols: number, mines: number, safeRow?: number, safeCol?: number): Cell[][] {
  const board: Cell[][] = Array.from({ length: rows }, () =>
    Array.from({ length: cols }, () => ({ isMine: false, neighborMines: 0, state: 'hidden' as CellState }))
  );
  let placed = 0;
  while (placed < mines) {
    const r = Math.floor(Math.random() * rows);
    const c = Math.floor(Math.random() * cols);
    if (board[r][c].isMine) continue;
    if (safeRow !== undefined && safeCol !== undefined && Math.abs(r - safeRow) <= 1 && Math.abs(c - safeCol) <= 1) continue;
    board[r][c].isMine = true;
    placed++;
  }
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      if (board[r][c].isMine) continue;
      let count = 0;
      for (let dr = -1; dr <= 1; dr++) {
        for (let dc = -1; dc <= 1; dc++) {
          const nr = r + dr, nc = c + dc;
          if (nr >= 0 && nr < rows && nc >= 0 && nc < cols && board[nr][nc].isMine) count++;
        }
      }
      board[r][c].neighborMines = count;
    }
  }
  return board;
}

function getBestTime(diff: number): number | null {
  const val = localStorage.getItem(`minesweeper_best_${diff}`);
  return val ? parseInt(val, 10) : null;
}
function setBestTime(diff: number, time: number) {
  const current = getBestTime(diff);
  if (current === null || time < current) {
    localStorage.setItem(`minesweeper_best_${diff}`, String(time));
  }
}

export default function Minesweeper() {
  const [difficulty, setDifficulty] = useState(0);
  const [board, setBoard] = useState<Cell[][]>([]);
  const [gameState, setGameState] = useState<'menu' | 'playing' | 'won' | 'lost'>('menu');
  const [timer, setTimer] = useState(0);
  const [flagCount, setFlagCount] = useState(0);
  const [firstClick, setFirstClick] = useState(true);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const diff = DIFFICULTIES[difficulty];

  useEffect(() => {
    if (gameState === 'playing') {
      timerRef.current = setInterval(() => setTimer(t => t + 1), 1000);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [gameState]);

  const newGame = useCallback((diffIndex?: number) => {
    const d = diffIndex !== undefined ? DIFFICULTIES[diffIndex] : diff;
    if (diffIndex !== undefined) setDifficulty(diffIndex);
    setBoard(createBoard(d.rows, d.cols, d.mines));
    setGameState('playing');
    setTimer(0);
    setFlagCount(0);
    setFirstClick(true);
  }, [diff]);

  const revealCell = useCallback((board: Cell[][], r: number, c: number): Cell[][] => {
    const rows = board.length;
    const cols = board[0].length;
    const newBoard = board.map(row => row.map(cell => ({ ...cell })));
    const queue: [number, number][] = [[r, c]];
    const visited = new Set<string>();
    visited.add(`${r},${c}`);
    while (queue.length) {
      const [cr, cc] = queue.shift()!;
      if (newBoard[cr][cc].state !== 'hidden' && newBoard[cr][cc].state !== 'questioned') continue;
      newBoard[cr][cc].state = 'revealed';
      if (newBoard[cr][cc].neighborMines === 0 && !newBoard[cr][cc].isMine) {
        for (let dr = -1; dr <= 1; dr++) {
          for (let dc = -1; dc <= 1; dc++) {
            const nr = cr + dr, nc = cc + dc;
            const key = `${nr},${nc}`;
            if (nr >= 0 && nr < rows && nc >= 0 && nc < cols && !visited.has(key)) {
              visited.add(key);
              queue.push([nr, nc]);
            }
          }
        }
      }
    }
    return newBoard;
  }, []);

  const checkWin = useCallback((board: Cell[][]) => {
    let revealedCount = 0;
    let totalCells = 0;
    for (const row of board) {
      for (const cell of row) {
        totalCells++;
        if (cell.state === 'revealed') revealedCount++;
      }
    }
    return revealedCount === totalCells - diff.mines;
  }, [diff]);

  const handleLeftClick = useCallback((r: number, c: number) => {
    if (gameState === 'menu') return;
    if (gameState === 'won' || gameState === 'lost') return;
    const cell = board[r][c];
    if (cell.state === 'flagged' || cell.state === 'questioned') return;
    if (cell.state === 'revealed') {
      // Chording
      const rows = board.length;
      const cols = board[0].length;
      let flagCount = 0;
      for (let dr = -1; dr <= 1; dr++) {
        for (let dc = -1; dc <= 1; dc++) {
          const nr = r + dr, nc = c + dc;
          if (nr >= 0 && nr < rows && nc >= 0 && nc < cols && board[nr][nc].state === 'flagged') flagCount++;
        }
      }
      if (flagCount === cell.neighborMines) {
        let newBoard = board.map(row => row.map(cell => ({ ...cell })));
        let hitMine = false;
        for (let dr = -1; dr <= 1; dr++) {
          for (let dc = -1; dc <= 1; dc++) {
            const nr = r + dr, nc = c + dc;
            if (nr >= 0 && nr < rows && nc >= 0 && nc < cols && board[nr][nc].state === 'hidden') {
              if (newBoard[nr][nc].isMine) {
                hitMine = true;
                newBoard[nr][nc].state = 'revealed';
              } else {
                newBoard = revealCell(newBoard, nr, nc);
              }
            }
          }
        }
        if (hitMine) {
          newBoard = revealAllMines(newBoard);
          setBoard(newBoard);
          setGameState('lost');
        } else {
          setBoard(newBoard);
          if (checkWin(newBoard)) {
            setGameState('won');
            setBestTime(difficulty, timer);
          }
        }
      }
      return;
    }
    let newBoard = board.map(row => row.map(cell => ({ ...cell })));
    if (firstClick) {
      setFirstClick(false);
      if (newBoard[r][c].isMine) {
        newBoard = createBoard(diff.rows, diff.cols, diff.mines, r, c);
      }
    }
    if (newBoard[r][c].isMine) {
      newBoard[r][c].state = 'revealed';
      newBoard = revealAllMines(newBoard);
      setBoard(newBoard);
      setGameState('lost');
      return;
    }
    newBoard = revealCell(newBoard, r, c);
    setBoard(newBoard);
    if (checkWin(newBoard)) {
      setGameState('won');
      setBestTime(difficulty, timer);
    }
  }, [board, gameState, firstClick, diff, difficulty, timer, checkWin, revealCell]);

  const handleRightClick = useCallback((e: React.MouseEvent, r: number, c: number) => {
    e.preventDefault();
    if (gameState === 'won' || gameState === 'lost') return;
    if (gameState === 'menu') return;
    const cell = board[r][c];
    if (cell.state === 'revealed') return;
    const newBoard = board.map(row => row.map(cell => ({ ...cell })));
    if (cell.state === 'hidden') {
      newBoard[r][c].state = 'flagged';
      setFlagCount(f => f + 1);
    } else if (cell.state === 'flagged') {
      newBoard[r][c].state = 'questioned';
      setFlagCount(f => f - 1);
    } else {
      newBoard[r][c].state = 'hidden';
    }
    setBoard(newBoard);
  }, [board, gameState]);

  const revealAllMines = (board: Cell[][]): Cell[][] => {
    return board.map(row => row.map(cell => {
      if (cell.isMine && cell.state !== 'flagged') return { ...cell, state: 'revealed' as CellState };
      if (!cell.isMine && cell.state === 'flagged') return { ...cell, state: 'flagged' as CellState };
      return { ...cell };
    }));
  };

  const cellSize = difficulty === 0 ? 28 : difficulty === 1 ? 22 : 20;
  const gridWidth = diff.cols * cellSize;

  return (
    <div className="flex flex-col items-center h-full select-none" style={{ background: 'var(--bg-window)', padding: 8 }}>
      {/* Info Bar */}
      <div className="flex items-center justify-between w-full mb-2 px-2" style={{ minHeight: 40, background: 'var(--bg-titlebar)', borderRadius: 8, padding: '6px 12px' }}>
        <div className="flex items-center gap-1" style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>
          <Flag size={16} style={{ color: 'var(--accent-error)' }} />
          <span>{diff.mines - flagCount}</span>
        </div>
        <button
          onClick={() => newGame()}
          className="flex items-center justify-center"
          style={{ width: 32, height: 32, borderRadius: '50%', border: '2px solid var(--border-default)', background: 'var(--bg-hover)', fontSize: 18, cursor: 'pointer' }}
          title="New Game"
        >
          {gameState === 'lost' ? '💀' : gameState === 'won' ? '😎' : '🙂'}
        </button>
        <div className="flex items-center gap-1" style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>
          <Clock size={16} style={{ color: 'var(--accent-info)' }} />
          <span>{timer}</span>
        </div>
      </div>

      {/* Difficulty selector */}
      <div className="flex gap-1 mb-2">
        {DIFFICULTIES.map((d, i) => (
          <button
            key={d.name}
            onClick={() => { setDifficulty(i); newGame(i); }}
            style={{
              padding: '3px 10px',
              borderRadius: 6,
              border: 'none',
              fontSize: 11,
              fontWeight: difficulty === i ? 600 : 400,
              cursor: 'pointer',
              background: difficulty === i ? 'var(--accent-primary)' : 'var(--bg-hover)',
              color: difficulty === i ? '#fff' : 'var(--text-secondary)',
            }}
          >
            {d.name}
          </button>
        ))}
      </div>

      {/* Best time */}
      {getBestTime(difficulty) !== null && (
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>
          Best: {getBestTime(difficulty)}s
        </div>
      )}

      {/* Grid */}
      <div
        className="grid"
        style={{
          gridTemplateColumns: `repeat(${diff.cols}, ${cellSize}px)`,
          gap: 1,
          background: 'var(--border-subtle)',
          border: '2px solid var(--border-default)',
        }}
      >
        {board.map((row, r) =>
          row.map((cell, c) => (
            <div
              key={`${r}-${c}`}
              onClick={() => handleLeftClick(r, c)}
              onContextMenu={(e) => handleRightClick(e, r, c)}
              className="flex items-center justify-center"
              style={{
                width: cellSize,
                height: cellSize,
                background: cell.state === 'revealed'
                  ? cell.isMine ? 'var(--accent-error)' : 'var(--bg-window)'
                  : 'var(--bg-hover)',
                border: cell.state === 'revealed' ? '1px solid var(--border-subtle)' : '2px outset var(--bg-window)',
                cursor: 'pointer',
                fontSize: cellSize * 0.55,
                fontWeight: 700,
                color: NUMBER_COLORS[cell.neighborMines] || 'var(--text-primary)',
                userSelect: 'none',
              }}
            >
              {cell.state === 'flagged' && <Flag size={cellSize * 0.5} style={{ color: 'var(--accent-error)' }} />}
              {cell.state === 'questioned' && '?'}
              {cell.state === 'revealed' && cell.isMine && <Bomb size={cellSize * 0.5} />}
              {cell.state === 'revealed' && !cell.isMine && cell.neighborMines > 0 && cell.neighborMines}
            </div>
          ))
        )}
      </div>

      {/* Game over overlay */}
      {gameState === 'won' && (
        <div className="flex flex-col items-center mt-2" style={{ padding: '6px 16px', background: 'rgba(76,175,80,0.15)', borderRadius: 8, border: '1px solid var(--accent-success)' }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--accent-success)' }}>You Win! Time: {timer}s</span>
        </div>
      )}
      {gameState === 'lost' && (
        <div className="flex flex-col items-center mt-2" style={{ padding: '6px 16px', background: 'rgba(244,67,54,0.15)', borderRadius: 8, border: '1px solid var(--accent-error)' }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--accent-error)' }}>Game Over!</span>
        </div>
      )}

      {gameState === 'menu' && (
        <button
          onClick={() => newGame()}
          style={{ marginTop: 16, padding: '8px 24px', background: 'var(--accent-primary)', color: '#fff', borderRadius: 8, border: 'none', fontSize: 14, fontWeight: 600, cursor: 'pointer' }}
        >
          New Game
        </button>
      )}
    </div>
  );
}

import { useState, useEffect, useCallback } from 'react';
import { Lightbulb, Eraser, Pencil, RotateCcw, Clock } from 'lucide-react';

type CellValue = number | null;
interface Cell {
  value: CellValue;
  given: boolean;
  notes: Set<number>;
}

interface SudokuState {
  board: Cell[][];
  solution: number[][];
  selectedCell: [number, number] | null;
  notesMode: boolean;
  hintsUsed: number;
  timer: number;
  gameState: 'menu' | 'playing' | 'won';
  difficulty: number;
  errors: Set<string>;
}

const DIFFICULTIES = [
  { name: 'Easy', cells: 45 },
  { name: 'Medium', cells: 35 },
  { name: 'Hard', cells: 28 },
  { name: 'Expert', cells: 22 },
];

function getBestTime(diff: number): number | null {
  const val = localStorage.getItem(`sudoku_best_${diff}`);
  return val ? parseInt(val, 10) : null;
}
function setBestTime(diff: number, time: number) {
  const current = getBestTime(diff);
  if (current === null || time < current) localStorage.setItem(`sudoku_best_${diff}`, String(time));
}

// Sudoku puzzle generation
function generateSolution(): number[][] {
  const board: number[][] = Array.from({ length: 9 }, () => Array(9).fill(0));
  const nums = [1, 2, 3, 4, 5, 6, 7, 8, 9];

  function shuffle(arr: number[]): number[] {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  function isValid(board: number[][], row: number, col: number, num: number): boolean {
    for (let i = 0; i < 9; i++) {
      if (board[row][i] === num || board[i][col] === num) return false;
    }
    const boxRow = Math.floor(row / 3) * 3;
    const boxCol = Math.floor(col / 3) * 3;
    for (let r = boxRow; r < boxRow + 3; r++) {
      for (let c = boxCol; c < boxCol + 3; c++) {
        if (board[r][c] === num) return false;
      }
    }
    return true;
  }

  function solve(board: number[][]): boolean {
    for (let row = 0; row < 9; row++) {
      for (let col = 0; col < 9; col++) {
        if (board[row][col] === 0) {
          for (const num of shuffle(nums)) {
            if (isValid(board, row, col, num)) {
              board[row][col] = num;
              if (solve(board)) return true;
              board[row][col] = 0;
            }
          }
          return false;
        }
      }
    }
    return true;
  }

  solve(board);
  return board;
}

function createPuzzle(difficulty: number): { puzzle: Cell[][]; solution: number[][] } {
  const solution = generateSolution();
  const puzzle: Cell[][] = solution.map(row =>
    row.map(val => ({ value: val as CellValue, given: true, notes: new Set<number>() }))
  );

  const cellsToRemove = 81 - DIFFICULTIES[difficulty].cells;
  const positions: [number, number][] = [];
  for (let r = 0; r < 9; r++) {
    for (let c = 0; c < 9; c++) {
      positions.push([r, c]);
    }
  }
  // Shuffle positions
  for (let i = positions.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [positions[i], positions[j]] = [positions[j], positions[i]];
  }

  for (let i = 0; i < cellsToRemove; i++) {
    const [r, c] = positions[i];
    puzzle[r][c] = { value: null, given: false, notes: new Set<number>() };
  }

  return { puzzle, solution };
}

function isValidPlacement(board: Cell[][], row: number, col: number, num: number): boolean {
  for (let i = 0; i < 9; i++) {
    if (i !== col && board[row][i].value === num) return false;
    if (i !== row && board[i][col].value === num) return false;
  }
  const boxRow = Math.floor(row / 3) * 3;
  const boxCol = Math.floor(col / 3) * 3;
  for (let r = boxRow; r < boxRow + 3; r++) {
    for (let c = boxCol; c < boxCol + 3; c++) {
      if ((r !== row || c !== col) && board[r][c].value === num) return false;
    }
  }
  return true;
}

export default function Sudoku() {
  const [state, setState] = useState<SudokuState>({
    board: [],
    solution: [],
    selectedCell: null,
    notesMode: false,
    hintsUsed: 0,
    timer: 0,
    gameState: 'menu',
    difficulty: 0,
    errors: new Set(),
  });

  // Timer
  useEffect(() => {
    if (state.gameState !== 'playing') return;
    const interval = setInterval(() => {
      setState(s => ({ ...s, timer: s.timer + 1 }));
    }, 1000);
    return () => clearInterval(interval);
  }, [state.gameState]);

  // Keyboard input
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (state.gameState !== 'playing' || !state.selectedCell) return;
      const [r, c] = state.selectedCell;
      if (e.key >= '1' && e.key <= '9') {
        handleNumberInput(parseInt(e.key, 10));
      } else if (e.key === 'Backspace' || e.key === 'Delete') {
        handleNumberInput(null);
      } else if (e.key === 'n' || e.key === 'N') {
        setState(s => ({ ...s, notesMode: !s.notesMode }));
      } else if (e.key === 'ArrowUp') {
        setState(s => ({ ...s, selectedCell: [Math.max(0, r - 1), c] }));
      } else if (e.key === 'ArrowDown') {
        setState(s => ({ ...s, selectedCell: [Math.min(8, r + 1), c] }));
      } else if (e.key === 'ArrowLeft') {
        setState(s => ({ ...s, selectedCell: [r, Math.max(0, c - 1)] }));
      } else if (e.key === 'ArrowRight') {
        setState(s => ({ ...s, selectedCell: [r, Math.min(8, c + 1)] }));
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [state.gameState, state.selectedCell, state.notesMode]);

  const startGame = useCallback((difficulty: number) => {
    const { puzzle, solution } = createPuzzle(difficulty);
    setState({
      board: puzzle,
      solution,
      selectedCell: null,
      notesMode: false,
      hintsUsed: 0,
      timer: 0,
      gameState: 'playing',
      difficulty,
      errors: new Set(),
    });
  }, []);

  const handleNumberInput = useCallback((num: number | null) => {
    if (!state.selectedCell) return;
    const [r, c] = state.selectedCell;
    const cell = state.board[r][c];
    if (cell.given) return;

    const newBoard = state.board.map(row => row.map(cell => ({ ...cell, notes: new Set(cell.notes) })));

    if (state.notesMode && num !== null) {
      if (newBoard[r][c].notes.has(num)) {
        newBoard[r][c].notes.delete(num);
      } else {
        newBoard[r][c].notes.add(num);
      }
      newBoard[r][c].value = null;
    } else {
      newBoard[r][c].value = num;
      newBoard[r][c].notes.clear();
    }

    // Check errors
    const newErrors = new Set<string>();
    for (let row = 0; row < 9; row++) {
      for (let col = 0; col < 9; col++) {
        const val = newBoard[row][col].value;
        if (val !== null && !isValidPlacement(newBoard, row, col, val)) {
          newErrors.add(`${row},${col}`);
        }
      }
    }

    // Check win
    const isComplete = newBoard.every(row => row.every(cell => cell.value !== null));
    const hasErrors = newErrors.size > 0;
    const won = isComplete && !hasErrors;

    if (won) {
      setBestTime(state.difficulty, state.timer);
    }

    setState(s => ({ ...s, board: newBoard, errors: newErrors, gameState: won ? 'won' : s.gameState }));
  }, [state.selectedCell, state.notesMode, state.board, state.difficulty, state.timer]);

  const handleHint = useCallback(() => {
    if (!state.selectedCell || state.hintsUsed >= 3) return;
    const [r, c] = state.selectedCell;
    const cell = state.board[r][c];
    if (cell.given || cell.value !== null) return;
    const correctValue = state.solution[r][c];
    const newBoard = state.board.map(row => row.map(cell => ({ ...cell, notes: new Set(cell.notes) })));
    newBoard[r][c].value = correctValue;
    newBoard[r][c].notes.clear();
    setState(s => ({ ...s, board: newBoard, hintsUsed: s.hintsUsed + 1 }));
  }, [state.selectedCell, state.hintsUsed, state.board, state.solution]);

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  if (state.gameState === 'menu') {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3" style={{ background: 'var(--bg-window)', padding: 16 }}>
        <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--accent-primary)' }}>Sudoku</div>
        <div style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 8 }}>Select difficulty</div>
        {DIFFICULTIES.map((d, i) => (
          <button key={d.name} onClick={() => startGame(i)}
            className="flex items-center justify-between"
            style={{ padding: '10px 20px', background: 'var(--bg-hover)', color: 'var(--text-primary)', borderRadius: 8, border: '1px solid var(--border-default)', fontSize: 14, fontWeight: 600, cursor: 'pointer', width: 200 }}>
            <span>{d.name}</span>
            <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{d.cells} clues</span>
          </button>
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center h-full select-none" style={{ background: 'var(--bg-window)', padding: 8 }} tabIndex={0}>
      {/* Info bar */}
      <div className="flex items-center justify-between w-full mb-2" style={{ padding: '4px 8px', background: 'var(--bg-titlebar)', borderRadius: 8 }}>
        <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600 }}>{DIFFICULTIES[state.difficulty].name}</span>
        <div className="flex items-center gap-1" style={{ fontSize: 13, color: 'var(--text-primary)' }}>
          <Clock size={14} /> {formatTime(state.timer)}
        </div>
        <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Hints: {3 - state.hintsUsed}</span>
      </div>

      {/* Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(9, 36px)', gap: 0, border: '2px solid var(--text-primary)' }}>
        {state.board.map((row, r) =>
          row.map((cell, c) => {
            const isSelected = state.selectedCell?.[0] === r && state.selectedCell?.[1] === c;
            const isSameNumber = state.selectedCell && cell.value !== null && state.board[state.selectedCell[0]][state.selectedCell[1]].value === cell.value;
            const isRelated = state.selectedCell && (state.selectedCell[0] === r || state.selectedCell[1] === c || (Math.floor(state.selectedCell[0] / 3) === Math.floor(r / 3) && Math.floor(state.selectedCell[1] / 3) === Math.floor(c / 3)));
            const hasError = state.errors.has(`${r},${c}`);
            const isThickRight = (c + 1) % 3 === 0 && c < 8;
            const isThickBottom = (r + 1) % 3 === 0 && r < 8;

            return (
              <div key={`${r}-${c}`}
                onClick={() => setState(s => ({ ...s, selectedCell: [r, c] }))}
                style={{
                  width: 36, height: 36,
                  background: isSelected ? 'rgba(124,77,255,0.25)' : isSameNumber ? 'rgba(124,77,255,0.12)' : isRelated ? 'rgba(255,255,255,0.04)' : 'transparent',
                  borderRight: isThickRight ? '2px solid var(--text-primary)' : '1px solid var(--border-default)',
                  borderBottom: isThickBottom ? '2px solid var(--text-primary)' : '1px solid var(--border-default)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  cursor: 'pointer',
                  position: 'relative',
                }}
              >
                {cell.value !== null ? (
                  <span style={{
                    fontSize: 18, fontWeight: cell.given ? 700 : 600,
                    color: hasError ? 'var(--accent-error)' : cell.given ? 'var(--text-primary)' : 'var(--accent-primary)',
                  }}>
                    {cell.value}
                  </span>
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 0, width: '100%', height: '100%', padding: 1 }}>
                    {[1, 2, 3, 4, 5, 6, 7, 8, 9].map(n => (
                      <div key={n} style={{ fontSize: 7, color: 'var(--text-secondary)', textAlign: 'center', lineHeight: '11px' }}>
                        {cell.notes.has(n) ? n : ''}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Controls */}
      <div className="flex items-center gap-2 mt-2">
        <button onClick={() => setState(s => ({ ...s, notesMode: !s.notesMode }))}
          style={{ padding: '6px 10px', background: state.notesMode ? 'var(--accent-primary)' : 'var(--bg-hover)', color: state.notesMode ? '#fff' : 'var(--text-primary)', borderRadius: 6, border: 'none', fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
          <Pencil size={14} /> Notes
        </button>
        <button onClick={handleHint} disabled={state.hintsUsed >= 3}
          style={{ padding: '6px 10px', background: 'var(--bg-hover)', color: state.hintsUsed >= 3 ? 'var(--text-disabled)' : 'var(--text-primary)', borderRadius: 6, border: 'none', fontSize: 12, cursor: state.hintsUsed >= 3 ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
          <Lightbulb size={14} /> Hint
        </button>
        <button onClick={() => handleNumberInput(null)}
          style={{ padding: '6px 10px', background: 'var(--bg-hover)', color: 'var(--text-primary)', borderRadius: 6, border: 'none', fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
          <Eraser size={14} /> Clear
        </button>
        <button onClick={() => setState(s => ({ ...s, gameState: 'menu' }))}
          style={{ padding: '6px 10px', background: 'var(--bg-hover)', color: 'var(--text-primary)', borderRadius: 6, border: 'none', fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
          <RotateCcw size={14} /> New
        </button>
      </div>

      {/* Numpad */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(9, 36px)', gap: 3, marginTop: 8 }}>
        {[1, 2, 3, 4, 5, 6, 7, 8, 9].map(n => {
          const count = state.board.flat().filter(c => c.value === n).length;
          return (
            <button key={n} onClick={() => handleNumberInput(n)}
              style={{
                width: 36, height: 36, borderRadius: 6,
                background: 'var(--bg-hover)',
                border: '1px solid var(--border-default)',
                fontSize: 16, fontWeight: 600,
                color: count === 9 ? 'var(--text-disabled)' : 'var(--text-primary)',
                cursor: count === 9 ? 'not-allowed' : 'pointer',
                opacity: count === 9 ? 0.4 : 1,
              }}>
              {n}
            </button>
          );
        })}
      </div>

      {/* Win overlay */}
      {state.gameState === 'won' && (
        <div className="absolute inset-0 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.7)', zIndex: 20, borderRadius: 12 }}>
          <div className="flex flex-col items-center" style={{ background: 'var(--bg-window)', padding: 24, borderRadius: 16 }}>
            <span style={{ fontSize: 22, fontWeight: 700, color: 'var(--accent-success)' }}>Solved!</span>
            <span style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>Time: {formatTime(state.timer)}</span>
            {getBestTime(state.difficulty) !== null && (
              <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Best: {formatTime(getBestTime(state.difficulty)!)}</span>
            )}
            <button onClick={() => setState(s => ({ ...s, gameState: 'menu' }))} style={{ marginTop: 12, padding: '8px 24px', background: 'var(--accent-primary)', color: '#fff', borderRadius: 8, border: 'none', fontSize: 14, fontWeight: 600, cursor: 'pointer' }}>
              New Puzzle
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

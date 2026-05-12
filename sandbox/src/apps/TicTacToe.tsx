import { useState, useCallback, useEffect } from 'react';
import { RotateCcw, User, Users } from 'lucide-react';

type Cell = 'X' | 'O' | null;
type GameMode = 'pvp' | 'ai';
type AIDifficulty = 'easy' | 'medium' | 'hard';

interface GameState {
  board: Cell[];
  currentPlayer: 'X' | 'O';
  winner: Cell;
  winningLine: number[] | null;
  isDraw: boolean;
  xWins: number;
  oWins: number;
  draws: number;
  gameCount: number;
}

const WIN_LINES = [
  [0, 1, 2], [3, 4, 5], [6, 7, 8],
  [0, 3, 6], [1, 4, 7], [2, 5, 8],
  [0, 4, 8], [2, 4, 6],
];

function checkWinner(board: Cell[]): { winner: Cell; line: number[] | null } {
  for (const line of WIN_LINES) {
    const [a, b, c] = line;
    if (board[a] && board[a] === board[b] && board[a] === board[c]) {
      return { winner: board[a], line };
    }
  }
  return { winner: null, line: null };
}

function minimax(board: Cell[], depth: number, isMax: boolean, alpha: number, beta: number): number {
  const { winner } = checkWinner(board);
  if (winner === 'X') return -10 + depth;
  if (winner === 'O') return 10 - depth;
  if (board.every(c => c !== null)) return 0;

  if (isMax) {
    let best = -Infinity;
    for (let i = 0; i < 9; i++) {
      if (board[i] === null) {
        board[i] = 'O';
        best = Math.max(best, minimax(board, depth + 1, false, alpha, beta));
        board[i] = null;
        alpha = Math.max(alpha, best);
        if (beta <= alpha) break;
      }
    }
    return best;
  } else {
    let best = Infinity;
    for (let i = 0; i < 9; i++) {
      if (board[i] === null) {
        board[i] = 'X';
        best = Math.min(best, minimax(board, depth + 1, true, alpha, beta));
        board[i] = null;
        beta = Math.min(beta, best);
        if (beta <= alpha) break;
      }
    }
    return best;
  }
}

function getAIMove(board: Cell[], difficulty: AIDifficulty): number {
  const emptyCells = board.map((c, i) => c === null ? i : null).filter((i): i is number => i !== null);
  if (emptyCells.length === 0) return -1;

  if (difficulty === 'easy') {
    return emptyCells[Math.floor(Math.random() * emptyCells.length)];
  }

  if (difficulty === 'medium') {
    // 50% random, 50% smart
    if (Math.random() < 0.5) {
      return emptyCells[Math.floor(Math.random() * emptyCells.length)];
    }
  }

  // Hard: minimax
  let bestScore = -Infinity;
  let bestMove = emptyCells[0];
  for (const i of emptyCells) {
    board[i] = 'O';
    const score = minimax(board, 0, false, -Infinity, Infinity);
    board[i] = null;
    if (score > bestScore) {
      bestScore = score;
      bestMove = i;
    }
  }
  return bestMove;
}

export default function TicTacToe() {
  const [mode, setMode] = useState<GameMode | null>(null);
  const [aiDifficulty, setAiDifficulty] = useState<AIDifficulty>('medium');
  const [state, setState] = useState<GameState>({
    board: Array(9).fill(null),
    currentPlayer: 'X',
    winner: null,
    winningLine: null,
    isDraw: false,
    xWins: 0,
    oWins: 0,
    draws: 0,
    gameCount: 0,
  });

  const resetScores = useCallback(() => {
    setState(s => ({
      ...s, xWins: 0, oWins: 0, draws: 0, gameCount: 0,
      board: Array(9).fill(null), currentPlayer: 'X', winner: null, winningLine: null, isDraw: false,
    }));
  }, []);

  const newGame = useCallback(() => {
    setState(s => ({
      ...s,
      board: Array(9).fill(null),
      currentPlayer: s.gameCount % 2 === 0 ? 'X' : 'O',
      winner: null,
      winningLine: null,
      isDraw: false,
    }));
  }, []);

  const handleCellClick = useCallback((index: number) => {
    if (state.winner || state.isDraw || state.board[index] !== null) return;
    const newBoard = [...state.board];
    newBoard[index] = state.currentPlayer;
    const { winner, line } = checkWinner(newBoard);
    const isDraw = !winner && newBoard.every(c => c !== null);

    if (winner) {
      setState(s => ({
        ...s, board: newBoard, winner, winningLine: line,
        xWins: winner === 'X' ? s.xWins + 1 : s.xWins,
        oWins: winner === 'O' ? s.oWins + 1 : s.oWins,
        gameCount: s.gameCount + 1,
      }));
    } else if (isDraw) {
      setState(s => ({
        ...s, board: newBoard, isDraw: true, draws: s.draws + 1, gameCount: s.gameCount + 1,
      }));
    } else {
      setState(s => ({ ...s, board: newBoard, currentPlayer: s.currentPlayer === 'X' ? 'O' : 'X' }));
    }
  }, [state]);

  // AI turn
  useEffect(() => {
    if (mode !== 'ai' || state.currentPlayer !== 'O' || state.winner || state.isDraw) return;
    const timeout = setTimeout(() => {
      const move = getAIMove([...state.board], aiDifficulty);
      if (move !== -1) handleCellClick(move);
    }, 400);
    return () => clearTimeout(timeout);
  }, [mode, state.currentPlayer, state.board, state.winner, state.isDraw, aiDifficulty, handleCellClick]);

  if (mode === null) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4" style={{ background: 'var(--bg-window)', padding: 16 }}>
        <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--accent-primary)' }}>Tic-Tac-Toe</div>
        <div style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 8 }}>Choose game mode</div>
        <button onClick={() => setMode('pvp')} className="flex items-center gap-2" style={{ padding: '12px 32px', background: 'var(--accent-primary)', color: '#fff', borderRadius: 10, border: 'none', fontSize: 15, fontWeight: 600, cursor: 'pointer', width: 200 }}>
          <Users size={18} /> 2 Players
        </button>
        <button onClick={() => setMode('ai')} className="flex items-center gap-2" style={{ padding: '12px 32px', background: 'var(--bg-hover)', color: 'var(--text-primary)', borderRadius: 10, border: '1px solid var(--border-default)', fontSize: 15, fontWeight: 600, cursor: 'pointer', width: 200 }}>
          <User size={18} /> vs Computer
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center h-full" style={{ background: 'var(--bg-window)', padding: 12 }}>
      {/* Mode selector */}
      {mode === 'ai' && (
        <div className="flex gap-1 mb-2">
          {(['easy', 'medium', 'hard'] as AIDifficulty[]).map(d => (
            <button key={d} onClick={() => { setAiDifficulty(d); newGame(); }}
              style={{ padding: '3px 10px', borderRadius: 6, border: 'none', fontSize: 11, cursor: 'pointer', background: aiDifficulty === d ? 'var(--accent-primary)' : 'var(--bg-hover)', color: aiDifficulty === d ? '#fff' : 'var(--text-secondary)', fontWeight: aiDifficulty === d ? 600 : 400 }}>
              {d.charAt(0).toUpperCase() + d.slice(1)}
            </button>
          ))}
        </div>
      )}

      {/* Turn indicator */}
      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>
        {state.winner ? `${state.winner} Wins!` : state.isDraw ? "It's a Draw!" : `${state.currentPlayer}'s Turn`}
      </div>

      {/* Board */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 90px)', gap: 6 }}>
        {state.board.map((cell, i) => {
          const isWinning = state.winningLine?.includes(i);
          return (
            <button key={i} onClick={() => handleCellClick(i)}
              style={{
                width: 90, height: 90,
                background: isWinning ? 'rgba(76,175,80,0.2)' : 'var(--bg-hover)',
                borderRadius: 12,
                border: isWinning ? '2px solid var(--accent-success)' : '2px solid transparent',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 36, fontWeight: 700,
                color: cell === 'X' ? 'var(--accent-primary)' : cell === 'O' ? 'var(--accent-secondary)' : 'var(--text-primary)',
                cursor: cell || state.winner || state.isDraw ? 'default' : 'pointer',
                transition: 'all 0.15s',
              }}
              disabled={!!cell || !!state.winner || state.isDraw || (mode === 'ai' && state.currentPlayer === 'O')}
            >
              {cell}
            </button>
          );
        })}
      </div>

      {/* Score board */}
      <div className="flex items-center gap-4 mt-3" style={{ padding: '8px 16px', background: 'var(--bg-titlebar)', borderRadius: 8 }}>
        <div className="flex flex-col items-center">
          <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>X Wins</span>
          <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--accent-primary)' }}>{state.xWins}</span>
        </div>
        <div className="flex flex-col items-center">
          <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Draws</span>
          <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-secondary)' }}>{state.draws}</span>
        </div>
        <div className="flex flex-col items-center">
          <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>O Wins</span>
          <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--accent-secondary)' }}>{state.oWins}</span>
        </div>
      </div>

      {/* Buttons */}
      <div className="flex gap-2 mt-3">
        <button onClick={newGame} style={{ padding: '6px 16px', background: 'var(--accent-primary)', color: '#fff', borderRadius: 8, border: 'none', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
          New Game
        </button>
        <button onClick={resetScores} style={{ padding: '6px 16px', background: 'var(--bg-hover)', color: 'var(--text-primary)', borderRadius: 8, border: '1px solid var(--border-default)', fontSize: 13, cursor: 'pointer' }}>
          <RotateCcw size={14} style={{ display: 'inline', marginRight: 4 }} />Reset
        </button>
        <button onClick={() => { setMode(null); resetScores(); }} style={{ padding: '6px 16px', background: 'var(--bg-hover)', color: 'var(--text-primary)', borderRadius: 8, border: '1px solid var(--border-default)', fontSize: 13, cursor: 'pointer' }}>
          Menu
        </button>
      </div>
    </div>
  );
}

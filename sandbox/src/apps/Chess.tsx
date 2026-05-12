import { useState, useCallback } from 'react';
import { RotateCcw, ChevronLeft, Crown } from 'lucide-react';

type PieceType = 'p' | 'n' | 'b' | 'r' | 'q' | 'k';
type PieceColor = 'w' | 'b';
interface ChessPiece {
  type: PieceType;
  color: PieceColor;
}

interface Move {
  from: [number, number];
  to: [number, number];
  piece: ChessPiece;
  captured?: ChessPiece;
  notation: string;
}

interface GameState {
  board: (ChessPiece | null)[][];
  currentPlayer: PieceColor;
  selectedSquare: [number, number] | null;
  validMoves: [number, number][];
  moveHistory: Move[];
  capturedWhite: ChessPiece[];
  capturedBlack: ChessPiece[];
  gameStatus: 'playing' | 'check' | 'checkmate' | 'stalemate';
  winner: PieceColor | null;
  enPassantTarget: [number, number] | null;
  castlingRights: { wk: boolean; wq: boolean; bk: boolean; bq: boolean };
  halfmoveClock: number;
}

const PIECE_SYMBOLS: Record<PieceColor, Record<PieceType, string>> = {
  w: { p: '♙', n: '♘', b: '♗', r: '♖', q: '♕', k: '♔' },
  b: { p: '♟', n: '♞', b: '♝', r: '♜', q: '♛', k: '♚' },
};

const PIECE_VALUES: Record<PieceType, number> = { p: 1, n: 3, b: 3, r: 5, q: 9, k: 0 };

function createInitialBoard(): (ChessPiece | null)[][] {
  const board: (ChessPiece | null)[][] = Array.from({ length: 8 }, () => Array(8).fill(null));
  const backRank: PieceType[] = ['r', 'n', 'b', 'q', 'k', 'b', 'n', 'r'];
  for (let c = 0; c < 8; c++) {
    board[0][c] = { type: backRank[c], color: 'b' };
    board[1][c] = { type: 'p', color: 'b' };
    board[6][c] = { type: 'p', color: 'w' };
    board[7][c] = { type: backRank[c], color: 'w' };
  }
  return board;
}

function inBounds(r: number, c: number): boolean {
  return r >= 0 && r < 8 && c >= 0 && c < 8;
}

function getValidMoves(board: (ChessPiece | null)[][], row: number, col: number, enPassant: [number, number] | null, castling: GameState['castlingRights']): [number, number][] {
  const piece = board[row][col];
  if (!piece) return [];
  const moves: [number, number][] = [];
  const { type, color } = piece;
  const dir = color === 'w' ? -1 : 1;

  switch (type) {
    case 'p': {
      const startRow = color === 'w' ? 6 : 1;
      // Forward
      if (inBounds(row + dir, col) && !board[row + dir][col]) {
        moves.push([row + dir, col]);
        if (row === startRow && !board[row + 2 * dir][col]) {
          moves.push([row + 2 * dir, col]);
        }
      }
      // Capture
      for (const dc of [-1, 1]) {
        const nr = row + dir, nc = col + dc;
        if (inBounds(nr, nc) && board[nr][nc] && board[nr][nc]!.color !== color) {
          moves.push([nr, nc]);
        }
        // En passant
        if (enPassant && enPassant[0] === nr && enPassant[1] === nc) {
          moves.push([nr, nc]);
        }
      }
      break;
    }
    case 'n': {
      const offsets = [[-2,-1],[-2,1],[-1,-2],[-1,2],[1,-2],[1,2],[2,-1],[2,1]];
      for (const [dr, dc] of offsets) {
        const nr = row + dr, nc = col + dc;
        if (inBounds(nr, nc) && (!board[nr][nc] || board[nr][nc]!.color !== color)) {
          moves.push([nr, nc]);
        }
      }
      break;
    }
    case 'b':
    case 'r':
    case 'q': {
      const directions: [number, number][] = type === 'b' ? [[-1,-1],[-1,1],[1,-1],[1,1]]
        : type === 'r' ? [[-1,0],[1,0],[0,-1],[0,1]]
        : [[-1,-1],[-1,0],[-1,1],[0,-1],[0,1],[1,-1],[1,0],[1,1]];
      for (const [dr, dc] of directions) {
        for (let i = 1; i < 8; i++) {
          const nr = row + dr * i, nc = col + dc * i;
          if (!inBounds(nr, nc)) break;
          if (!board[nr][nc]) { moves.push([nr, nc]); }
          else if (board[nr][nc]!.color !== color) { moves.push([nr, nc]); break; }
          else break;
        }
      }
      break;
    }
    case 'k': {
      const offsets = [[-1,-1],[-1,0],[-1,1],[0,-1],[0,1],[1,-1],[1,0],[1,1]];
      for (const [dr, dc] of offsets) {
        const nr = row + dr, nc = col + dc;
        if (inBounds(nr, nc) && (!board[nr][nc] || board[nr][nc]!.color !== color)) {
          moves.push([nr, nc]);
        }
      }
      // Castling
      if (color === 'w') {
        if (castling.wk && !board[7][5] && !board[7][6] && board[7][7]?.type === 'r' && board[7][7]?.color === 'w') moves.push([7, 6]);
        if (castling.wq && !board[7][3] && !board[7][2] && !board[7][1] && board[7][0]?.type === 'r' && board[7][0]?.color === 'w') moves.push([7, 2]);
      } else {
        if (castling.bk && !board[0][5] && !board[0][6] && board[0][7]?.type === 'r' && board[0][7]?.color === 'b') moves.push([0, 6]);
        if (castling.bq && !board[0][3] && !board[0][2] && !board[0][1] && board[0][0]?.type === 'r' && board[0][0]?.color === 'b') moves.push([0, 2]);
      }
      break;
    }
  }

  // Filter out moves that leave king in check
  return moves.filter(([nr, nc]) => {
    const newBoard = board.map(r => [...r]);
    newBoard[nr][nc] = newBoard[row][col];
    newBoard[row][col] = null;
    // En passant capture
    if (type === 'p' && enPassant && enPassant[0] === nr && enPassant[1] === nc) {
      newBoard[nr - dir][nc] = null;
    }
    return !isKingInCheck(newBoard, color);
  });
}

function isKingInCheck(board: (ChessPiece | null)[][], color: PieceColor): boolean {
  let kingRow = -1, kingCol = -1;
  for (let r = 0; r < 8; r++) {
    for (let c = 0; c < 8; c++) {
      if (board[r][c]?.type === 'k' && board[r][c]?.color === color) {
        kingRow = r; kingCol = c; break;
      }
    }
    if (kingRow !== -1) break;
  }
  // Check if any opponent piece can attack the king
  for (let r = 0; r < 8; r++) {
    for (let c = 0; c < 8; c++) {
      const piece = board[r][c];
      if (!piece || piece.color === color) continue;
      const moves = getRawMoves(board, r, c);
      if (moves.some(([mr, mc]) => mr === kingRow && mc === kingCol)) return true;
    }
  }
  return false;
}

function getRawMoves(board: (ChessPiece | null)[][], row: number, col: number): [number, number][] {
  const piece = board[row][col];
  if (!piece) return [];
  const moves: [number, number][] = [];
  const { type, color } = piece;
  const dir = color === 'w' ? -1 : 1;

  switch (type) {
    case 'p': {
      if (inBounds(row + dir, col) && !board[row + dir][col]) moves.push([row + dir, col]);
      for (const dc of [-1, 1]) {
        const nr = row + dir, nc = col + dc;
        if (inBounds(nr, nc) && board[nr][nc] && board[nr][nc]!.color !== color) moves.push([nr, nc]);
      }
      break;
    }
    case 'n': {
      const offsets = [[-2,-1],[-2,1],[-1,-2],[-1,2],[1,-2],[1,2],[2,-1],[2,1]];
      for (const [dr, dc] of offsets) {
        const nr = row + dr, nc = col + dc;
        if (inBounds(nr, nc) && (!board[nr][nc] || board[nr][nc]!.color !== color)) moves.push([nr, nc]);
      }
      break;
    }
    case 'b':
    case 'r':
    case 'q': {
      const directions: [number, number][] = type === 'b' ? [[-1,-1],[-1,1],[1,-1],[1,1]]
        : type === 'r' ? [[-1,0],[1,0],[0,-1],[0,1]]
        : [[-1,-1],[-1,0],[-1,1],[0,-1],[0,1],[1,-1],[1,0],[1,1]];
      for (const [dr, dc] of directions) {
        for (let i = 1; i < 8; i++) {
          const nr = row + dr * i, nc = col + dc * i;
          if (!inBounds(nr, nc)) break;
          if (!board[nr][nc]) { moves.push([nr, nc]); }
          else if (board[nr][nc]!.color !== color) { moves.push([nr, nc]); break; }
          else break;
        }
      }
      break;
    }
    case 'k': {
      const offsets = [[-1,-1],[-1,0],[-1,1],[0,-1],[0,1],[1,-1],[1,0],[1,1]];
      for (const [dr, dc] of offsets) {
        const nr = row + dr, nc = col + dc;
        if (inBounds(nr, nc) && (!board[nr][nc] || board[nr][nc]!.color !== color)) moves.push([nr, nc]);
      }
      break;
    }
  }
  return moves;
}

function hasAnyValidMoves(board: (ChessPiece | null)[][], color: PieceColor, enPassant: [number, number] | null, castling: GameState['castlingRights']): boolean {
  for (let r = 0; r < 8; r++) {
    for (let c = 0; c < 8; c++) {
      if (board[r][c]?.color === color) {
        if (getValidMoves(board, r, c, enPassant, castling).length > 0) return true;
      }
    }
  }
  return false;
}

function moveToAlgebraic(piece: ChessPiece, from: [number, number], to: [number, number], captured: boolean, check: boolean, checkmate: boolean): string {
  const files = 'abcdefgh';
  const ranks = '87654321';
  let notation = '';
  if (piece.type === 'p') {
    if (captured) notation += files[from[1]];
  } else {
    notation += piece.type.toUpperCase();
  }
  if (captured) notation += 'x';
  notation += files[to[1]] + ranks[to[0]];
  if (checkmate) notation += '#';
  else if (check) notation += '+';
  return notation;
}

export default function Chess() {
  const [state, setState] = useState<GameState>({
    board: createInitialBoard(),
    currentPlayer: 'w',
    selectedSquare: null,
    validMoves: [],
    moveHistory: [],
    capturedWhite: [],
    capturedBlack: [],
    gameStatus: 'playing',
    winner: null,
    enPassantTarget: null,
    castlingRights: { wk: true, wq: true, bk: true, bq: true },
    halfmoveClock: 0,
  });

  const [mode, setMode] = useState<'pvp' | 'ai'>('pvp');
  const [aiDepth, setAiDepth] = useState(2);

  const handleSquareClick = useCallback((row: number, col: number) => {
    if (state.gameStatus === 'checkmate' || state.gameStatus === 'stalemate') return;
    if (mode === 'ai' && state.currentPlayer === 'b') return;

    const clickedPiece = state.board[row][col];

    // If a piece is already selected
    if (state.selectedSquare) {
      const [sr, sc] = state.selectedSquare;
      const move = state.validMoves.find(([r, c]) => r === row && c === col);

      if (move) {
        // Execute move
        const newBoard = state.board.map(r => [...r]);
        const movingPiece = newBoard[sr][sc]!;
        const capturedPiece = newBoard[row][col];
        let newEnPassant: [number, number] | null = null;
        let newCastling = { ...state.castlingRights };
        let notation = '';

        // Handle special moves
        if (movingPiece.type === 'p' && Math.abs(row - sr) === 2) {
          newEnPassant = [(sr + row) / 2, col];
        }
        // En passant capture
        if (movingPiece.type === 'p' && state.enPassantTarget && state.enPassantTarget[0] === row && state.enPassantTarget[1] === col) {
          const capturedPawnRow = movingPiece.color === 'w' ? row + 1 : row - 1;
          newBoard[capturedPawnRow][col] = null;
        }
        // Castling
        if (movingPiece.type === 'k' && Math.abs(col - sc) === 2) {
          const rookFromCol = col > sc ? 7 : 0;
          const rookToCol = col > sc ? col - 1 : col + 1;
          newBoard[row][rookToCol] = newBoard[row][rookFromCol];
          newBoard[row][rookFromCol] = null;
        }
        // Update castling rights
        if (movingPiece.type === 'k') {
          if (movingPiece.color === 'w') { newCastling.wk = false; newCastling.wq = false; }
          else { newCastling.bk = false; newCastling.bq = false; }
        }
        if (movingPiece.type === 'r') {
          if (sr === 7 && sc === 0) newCastling.wq = false;
          if (sr === 7 && sc === 7) newCastling.wk = false;
          if (sr === 0 && sc === 0) newCastling.bq = false;
          if (sr === 0 && sc === 7) newCastling.bk = false;
        }

        newBoard[row][col] = newBoard[sr][sc];
        newBoard[sr][sc] = null;

        // Pawn promotion
        if (movingPiece.type === 'p' && (row === 0 || row === 7)) {
          newBoard[row][col] = { type: 'q', color: movingPiece.color };
        }

        // Check/checkmate detection
        const nextColor = state.currentPlayer === 'w' ? 'b' : 'w';
        const inCheck = isKingInCheck(newBoard, nextColor);
        const hasMoves = hasAnyValidMoves(newBoard, nextColor, newEnPassant, newCastling);
        let gameStatus: GameState['gameStatus'] = 'playing';
        let winner: PieceColor | null = null;
        if (inCheck && !hasMoves) { gameStatus = 'checkmate'; winner = state.currentPlayer; }
        else if (!inCheck && !hasMoves) gameStatus = 'stalemate';
        else if (inCheck) gameStatus = 'check';

        notation = moveToAlgebraic(movingPiece, [sr, sc], [row, col], !!capturedPiece || (movingPiece.type === 'p' && state.enPassantTarget?.[0] === row && state.enPassantTarget?.[1] === col), inCheck, gameStatus === 'checkmate');

        const moveRecord: Move = {
          from: [sr, sc],
          to: [row, col],
          piece: movingPiece,
          captured: capturedPiece || undefined,
          notation,
        };

        const newCapturedWhite = [...state.capturedWhite];
        const newCapturedBlack = [...state.capturedBlack];
        if (capturedPiece) {
          if (capturedPiece.color === 'w') newCapturedBlack.push(capturedPiece);
          else newCapturedWhite.push(capturedPiece);
        }

        setState(s => ({
          ...s,
          board: newBoard,
          currentPlayer: nextColor,
          selectedSquare: null,
          validMoves: [],
          moveHistory: [...s.moveHistory, moveRecord],
          capturedWhite: newCapturedWhite,
          capturedBlack: newCapturedBlack,
          gameStatus,
          winner,
          enPassantTarget: newEnPassant,
          castlingRights: newCastling,
        }));
        return;
      }

      // If clicking own piece, select it
      if (clickedPiece && clickedPiece.color === state.currentPlayer) {
        const moves = getValidMoves(state.board, row, col, state.enPassantTarget, state.castlingRights);
        setState(s => ({ ...s, selectedSquare: [row, col], validMoves: moves }));
        return;
      }

      // Deselect
      setState(s => ({ ...s, selectedSquare: null, validMoves: [] }));
      return;
    }

    // Select piece
    if (clickedPiece && clickedPiece.color === state.currentPlayer) {
      const moves = getValidMoves(state.board, row, col, state.enPassantTarget, state.castlingRights);
      setState(s => ({ ...s, selectedSquare: [row, col], validMoves: moves }));
    }
  }, [state, mode]);

  // AI move
  useState(() => {
    if (mode === 'ai' && state.currentPlayer === 'b' && state.gameStatus === 'playing') {
      const timeout = setTimeout(() => {
        // Simple minimax for AI
        let bestMove: { from: [number, number]; to: [number, number] } | null = null;
        let bestScore = -Infinity;
        
        for (let r = 0; r < 8; r++) {
          for (let c = 0; c < 8; c++) {
            const piece = state.board[r][c];
            if (!piece || piece.color !== 'b') continue;
            const moves = getValidMoves(state.board, r, c, state.enPassantTarget, state.castlingRights);
            for (const [mr, mc] of moves) {
              const newBoard = state.board.map(row => [...row]);
              const captured = newBoard[mr][mc];
              newBoard[mr][mc] = newBoard[r][c];
              newBoard[r][c] = null;
              let score = evaluateBoard(newBoard);
              if (captured) score += PIECE_VALUES[captured.type] * 10;
              // Random factor for variety
              score += Math.random() * 20;
              if (score > bestScore) {
                bestScore = score;
                bestMove = { from: [r, c], to: [mr, mc] };
              }
            }
          }
        }
        
        if (bestMove) {
          handleSquareClick(bestMove.from[0], bestMove.from[1]);
          setTimeout(() => handleSquareClick(bestMove!.to[0], bestMove!.to[1]), 50);
        }
      }, 500);
      return () => clearTimeout(timeout);
    }
  });

  const evaluateBoard = (board: (ChessPiece | null)[][]): number => {
    let score = 0;
    for (let r = 0; r < 8; r++) {
      for (let c = 0; c < 8; c++) {
        const piece = board[r][c];
        if (!piece) continue;
        const value = PIECE_VALUES[piece.type];
        if (piece.color === 'b') score += value;
        else score -= value;
      }
    }
    return score;
  };

  const undoMove = useCallback(() => {
    if (state.moveHistory.length === 0) return;
    const lastMove = state.moveHistory[state.moveHistory.length - 1];
    const newBoard = state.board.map(r => [...r]);
    newBoard[lastMove.from[0]][lastMove.from[1]] = lastMove.piece;
    newBoard[lastMove.to[0]][lastMove.to[1]] = lastMove.captured || null;
    
    setState(s => ({
      ...s,
      board: newBoard,
      currentPlayer: s.currentPlayer === 'w' ? 'b' : 'w',
      moveHistory: s.moveHistory.slice(0, -1),
      gameStatus: 'playing',
      winner: null,
      selectedSquare: null,
      validMoves: [],
    }));
  }, [state.moveHistory, state.board]);

  const newGame = useCallback(() => {
    setState({
      board: createInitialBoard(),
      currentPlayer: 'w',
      selectedSquare: null,
      validMoves: [],
      moveHistory: [],
      capturedWhite: [],
      capturedBlack: [],
      gameStatus: 'playing',
      winner: null,
      enPassantTarget: null,
      castlingRights: { wk: true, wq: true, bk: true, bq: true },
      halfmoveClock: 0,
    });
  }, []);

  const isLightSquare = (r: number, c: number) => (r + c) % 2 === 0;

  return (
    <div className="flex h-full select-none" style={{ background: 'var(--bg-window)', padding: 8 }}>
      <div className="flex flex-col items-center">
        {/* Captured pieces (top - black's captures) */}
        <div className="flex items-center" style={{ height: 24, marginBottom: 4 }}>
          {state.capturedBlack.map((p, i) => (
            <span key={i} style={{ fontSize: 16, marginRight: -4 }}>{PIECE_SYMBOLS[p.color][p.type]}</span>
          ))}
        </div>

        {/* Board */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(8, 48px)', border: '3px solid #555', borderRadius: 2 }}>
          {state.board.map((row, r) =>
            row.map((cell, c) => {
              const isSelected = state.selectedSquare?.[0] === r && state.selectedSquare?.[1] === c;
              const isValidMove = state.validMoves.some(([mr, mc]) => mr === r && mc === c);
              const light = isLightSquare(r, c);
              return (
                <div key={`${r}-${c}`}
                  onClick={() => handleSquareClick(r, c)}
                  style={{
                    width: 48, height: 48,
                    background: isSelected ? '#646FA0' : light ? '#F0D9B5' : '#B58863',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    cursor: 'pointer',
                    position: 'relative',
                    fontSize: 32,
                    color: cell?.color === 'w' ? '#FFFFFF' : '#212121',
                    textShadow: cell?.color === 'w' ? '0 1px 2px rgba(0,0,0,0.5)' : '0 1px 2px rgba(255,255,255,0.3)',
                  }}
                >
                  {cell && PIECE_SYMBOLS[cell.color][cell.type]}
                  {isValidMove && !cell && (
                    <div style={{ position: 'absolute', width: 12, height: 12, borderRadius: '50%', background: 'rgba(0,0,0,0.3)' }} />
                  )}
                  {isValidMove && cell && (
                    <div style={{ position: 'absolute', inset: 2, border: '3px solid rgba(0,0,0,0.3)', borderRadius: '50%' }} />
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Captured pieces (bottom - white's captures) */}
        <div className="flex items-center" style={{ height: 24, marginTop: 4 }}>
          {state.capturedWhite.map((p, i) => (
            <span key={i} style={{ fontSize: 16, marginRight: -4 }}>{PIECE_SYMBOLS[p.color][p.type]}</span>
          ))}
        </div>
      </div>

      {/* Side panel */}
      <div className="flex flex-col ml-3 gap-2" style={{ width: 140 }}>
        {/* Mode & status */}
        <div style={{ background: 'var(--bg-titlebar)', borderRadius: 8, padding: 8 }}>
          <div className="flex gap-1 mb-2">
            <button onClick={() => { setMode('pvp'); newGame(); }} style={{ flex: 1, padding: '3px 6px', background: mode === 'pvp' ? 'var(--accent-primary)' : 'var(--bg-hover)', color: mode === 'pvp' ? '#fff' : 'var(--text-secondary)', borderRadius: 4, border: 'none', fontSize: 10, cursor: 'pointer' }}>PvP</button>
            <button onClick={() => { setMode('ai'); newGame(); }} style={{ flex: 1, padding: '3px 6px', background: mode === 'ai' ? 'var(--accent-primary)' : 'var(--bg-hover)', color: mode === 'ai' ? '#fff' : 'var(--text-secondary)', borderRadius: 4, border: 'none', fontSize: 10, cursor: 'pointer' }}>vs AI</button>
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-primary)', fontWeight: 600, textAlign: 'center' }}>
            {state.gameStatus === 'checkmate' ? `Checkmate! ${state.winner === 'w' ? 'White' : 'Black'} wins` :
             state.gameStatus === 'stalemate' ? 'Stalemate!' :
             state.gameStatus === 'check' ? 'Check!' :
             `${state.currentPlayer === 'w' ? "White" : "Black"}'s turn`}
          </div>
        </div>

        {/* Move history */}
        <div style={{ background: 'var(--bg-titlebar)', borderRadius: 8, padding: 8, flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontWeight: 600, marginBottom: 4 }}>Moves</span>
          <div className="custom-scrollbar" style={{ overflow: 'auto', flex: 1, fontSize: 11, fontFamily: 'monospace' }}>
            {state.moveHistory.map((m, i) => (
              <div key={i} style={{ color: i % 2 === 0 ? 'var(--text-primary)' : 'var(--text-secondary)', padding: '1px 0' }}>
                {Math.floor(i / 2) + 1}.{i % 2 === 0 ? '' : '..'} {m.notation}
              </div>
            ))}
          </div>
        </div>

        {/* Buttons */}
        <div className="flex gap-1">
          <button onClick={undoMove} style={{ flex: 1, padding: '6px 0', background: 'var(--bg-hover)', color: 'var(--text-primary)', borderRadius: 6, border: '1px solid var(--border-default)', fontSize: 11, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 2 }}>
            <ChevronLeft size={12} /> Undo
          </button>
          <button onClick={newGame} style={{ flex: 1, padding: '6px 0', background: 'var(--accent-primary)', color: '#fff', borderRadius: 6, border: 'none', fontSize: 11, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 2 }}>
            <RotateCcw size={12} /> New
          </button>
        </div>
      </div>
    </div>
  );
}

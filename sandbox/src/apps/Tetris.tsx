import { useState, useEffect, useCallback, useRef } from 'react';

const COLS = 10;
const ROWS = 20;
const CELL = 20;

const TETROMINOES: Record<string, { shape: number[][]; color: string }> = {
  I: { shape: [[1,1,1,1]], color: '#00BCD4' },
  O: { shape: [[1,1],[1,1]], color: '#FFEB3B' },
  T: { shape: [[0,1,0],[1,1,1]], color: '#7C4DFF' },
  S: { shape: [[0,1,1],[1,1,0]], color: '#4CAF50' },
  Z: { shape: [[1,1,0],[0,1,1]], color: '#F44336' },
  J: { shape: [[1,0,0],[1,1,1]], color: '#2196F3' },
  L: { shape: [[0,0,1],[1,1,1]], color: '#FF9800' },
};

const PIECE_NAMES = Object.keys(TETROMINOES);

function randomPiece(): string {
  return PIECE_NAMES[Math.floor(Math.random() * PIECE_NAMES.length)];
}

function rotatePiece(shape: number[][]): number[][] {
  const rows = shape.length;
  const cols = shape[0].length;
  const result: number[][] = [];
  for (let c = 0; c < cols; c++) {
    result[c] = [];
    for (let r = rows - 1; r >= 0; r--) {
      result[c].push(shape[r][c]);
    }
  }
  return result;
}

function getHighScore(): number {
  const val = localStorage.getItem('tetris_highscore');
  return val ? parseInt(val, 10) : 0;
}
function setHighScore(score: number) {
  const current = getHighScore();
  if (score > current) localStorage.setItem('tetris_highscore', String(score));
}

interface Piece {
  name: string;
  shape: number[][];
  color: string;
  x: number;
  y: number;
}

export default function Tetris() {
  const [board, setBoard] = useState<(string | null)[][]>(() =>
    Array.from({ length: ROWS }, () => Array(COLS).fill(null))
  );
  const [currentPiece, setCurrentPiece] = useState<Piece | null>(null);
  const [nextPiece, setNextPiece] = useState<string>('');
  const [holdPiece, setHoldPiece] = useState<string | null>(null);
  const [canHold, setCanHold] = useState(true);
  const [score, setScore] = useState(0);
  const [lines, setLines] = useState(0);
  const [level, setLevel] = useState(1);
  const [gameState, setGameState] = useState<'menu' | 'playing' | 'paused' | 'over'>('menu');
  const [clearingRows, setClearingRows] = useState<number[]>([]);

  const boardRef = useRef(board);
  const pieceRef = useRef(currentPiece);
  const gameRef = useRef(gameState);
  const scoreRef = useRef(score);
  const linesRef = useRef(lines);
  const levelRef = useRef(level);
  const nextRef = useRef(nextPiece);

  useEffect(() => { boardRef.current = board; }, [board]);
  useEffect(() => { pieceRef.current = currentPiece; }, [currentPiece]);
  useEffect(() => { gameRef.current = gameState; }, [gameState]);
  useEffect(() => { scoreRef.current = score; }, [score]);
  useEffect(() => { linesRef.current = lines; }, [lines]);
  useEffect(() => { levelRef.current = level; }, [level]);
  useEffect(() => { nextRef.current = nextPiece; }, [nextPiece]);

  const spawnPiece = useCallback((name?: string) => {
    const pieceName = name || nextRef.current || randomPiece();
    const t = TETROMINOES[pieceName];
    const p: Piece = { name: pieceName, shape: t.shape.map(r => [...r]), color: t.color, x: 3, y: 0 };
    setCurrentPiece(p);
    pieceRef.current = p;
    const next = randomPiece();
    setNextPiece(next);
    nextRef.current = next;
    setCanHold(true);
    // Check if new piece collides -> game over
    if (checkCollision(boardRef.current, p.shape, p.x, p.y)) {
      setGameState('over');
      gameRef.current = 'over';
      setHighScore(scoreRef.current);
    }
  }, []);

  const startGame = useCallback(() => {
    const empty = Array.from({ length: ROWS }, () => Array(COLS).fill(null));
    setBoard(empty);
    boardRef.current = empty;
    setScore(0);
    scoreRef.current = 0;
    setLines(0);
    linesRef.current = 0;
    setLevel(1);
    levelRef.current = 1;
    setHoldPiece(null);
    setCanHold(true);
    setClearingRows([]);
    const first = randomPiece();
    const next = randomPiece();
    setNextPiece(next);
    nextRef.current = next;
    const t = TETROMINOES[first];
    const p: Piece = { name: first, shape: t.shape.map(r => [...r]), color: t.color, x: 3, y: 0 };
    setCurrentPiece(p);
    pieceRef.current = p;
    setGameState('playing');
    gameRef.current = 'playing';
  }, []);

  const checkCollision = (brd: (string | null)[][], shape: number[][], px: number, py: number): boolean => {
    for (let r = 0; r < shape.length; r++) {
      for (let c = 0; c < shape[r].length; c++) {
        if (shape[r][c]) {
          const nx = px + c;
          const ny = py + r;
          if (nx < 0 || nx >= COLS || ny >= ROWS) return true;
          if (ny >= 0 && brd[ny][nx] !== null) return true;
        }
      }
    }
    return false;
  };

  const lockPiece = useCallback(() => {
    const p = pieceRef.current;
    const brd = boardRef.current;
    if (!p) return;
    const newBoard = brd.map(r => [...r]);
    for (let r = 0; r < p.shape.length; r++) {
      for (let c = 0; c < p.shape[r].length; c++) {
        if (p.shape[r][c]) {
          const ny = p.y + r;
          const nx = p.x + c;
          if (ny >= 0 && ny < ROWS && nx >= 0 && nx < COLS) {
            newBoard[ny][nx] = p.color;
          }
        }
      }
    }
    // Check lines
    const fullRows: number[] = [];
    for (let r = 0; r < ROWS; r++) {
      if (newBoard[r].every(c => c !== null)) fullRows.push(r);
    }
    if (fullRows.length > 0) {
      setClearingRows(fullRows);
      const points = [0, 100, 300, 500, 800];
      const newScore = scoreRef.current + points[fullRows.length] * levelRef.current;
      const newLines = linesRef.current + fullRows.length;
      const newLevel = Math.floor(newLines / 10) + 1;
      scoreRef.current = newScore;
      linesRef.current = newLines;
      levelRef.current = newLevel;
      setScore(newScore);
      setLines(newLines);
      setLevel(newLevel);
      setTimeout(() => {
        const cleared = newBoard.filter((_, i) => !fullRows.includes(i));
        const emptyRows = Array.from({ length: fullRows.length }, () => Array(COLS).fill(null));
        const finalBoard = [...emptyRows, ...cleared];
        setBoard(finalBoard);
        boardRef.current = finalBoard;
        setClearingRows([]);
        spawnPiece();
      }, 300);
    } else {
      setBoard(newBoard);
      boardRef.current = newBoard;
      spawnPiece();
    }
  }, [spawnPiece]);

  const movePiece = useCallback((dx: number, dy: number) => {
    const p = pieceRef.current;
    if (!p || gameRef.current !== 'playing' || clearingRows.length > 0) return;
    if (!checkCollision(boardRef.current, p.shape, p.x + dx, p.y + dy)) {
      const np = { ...p, x: p.x + dx, y: p.y + dy };
      setCurrentPiece(np);
      pieceRef.current = np;
      return true;
    }
    if (dy > 0) lockPiece();
    return false;
  }, [lockPiece, clearingRows]);

  const rotatePieceFn = useCallback(() => {
    const p = pieceRef.current;
    if (!p || gameRef.current !== 'playing') return;
    const rotated = rotatePiece(p.shape);
    let offset = 0;
    if (checkCollision(boardRef.current, rotated, p.x, p.y)) {
      offset = 1;
      if (checkCollision(boardRef.current, rotated, p.x + 1, p.y)) {
        offset = -1;
        if (checkCollision(boardRef.current, rotated, p.x - 1, p.y)) return;
      }
    }
    const np = { ...p, shape: rotated, x: p.x + offset };
    setCurrentPiece(np);
    pieceRef.current = np;
  }, []);

  const hardDrop = useCallback(() => {
    const p = pieceRef.current;
    if (!p || gameRef.current !== 'playing') return;
    let dropY = p.y;
    while (!checkCollision(boardRef.current, p.shape, p.x, dropY + 1)) dropY++;
    const np = { ...p, y: dropY };
    setCurrentPiece(np);
    pieceRef.current = np;
    lockPiece();
  }, [lockPiece]);

  const hold = useCallback(() => {
    if (!canHold || gameRef.current !== 'playing') return;
    const p = pieceRef.current;
    if (!p) return;
    const current = holdPiece;
    setHoldPiece(p.name);
    setCanHold(false);
    if (current) {
      const t = TETROMINOES[current];
      const np: Piece = { name: current, shape: t.shape.map(r => [...r]), color: t.color, x: 3, y: 0 };
      setCurrentPiece(np);
      pieceRef.current = np;
    } else {
      spawnPiece();
    }
  }, [canHold, holdPiece, spawnPiece]);

  // Game loop
  useEffect(() => {
    if (gameState !== 'playing') return;
    const speed = Math.max(100, 800 - (level - 1) * 60);
    const interval = setInterval(() => {
      movePiece(0, 1);
    }, speed);
    return () => clearInterval(interval);
  }, [gameState, level, movePiece]);

  // Keyboard
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'p' || e.key === 'P') {
        if (gameRef.current === 'playing') { setGameState('paused'); gameRef.current = 'paused'; }
        else if (gameRef.current === 'paused') { setGameState('playing'); gameRef.current = 'playing'; }
        return;
      }
      if (gameRef.current !== 'playing') return;
      switch (e.key) {
        case 'ArrowLeft': movePiece(-1, 0); break;
        case 'ArrowRight': movePiece(1, 0); break;
        case 'ArrowDown': movePiece(0, 1); break;
        case 'ArrowUp': rotatePieceFn(); break;
        case ' ': e.preventDefault(); hardDrop(); break;
        case 'c': case 'C': hold(); break;
        case 'z': case 'Z': {
          const p = pieceRef.current;
          if (p) {
            const rotated = rotatePiece(rotatePiece(rotatePiece(p.shape)));
            let offset = 0;
            if (checkCollision(boardRef.current, rotated, p.x, p.y)) {
              offset = 1;
              if (checkCollision(boardRef.current, rotated, p.x + 1, p.y)) {
                offset = -1;
                if (checkCollision(boardRef.current, rotated, p.x - 1, p.y)) return;
              }
            }
            const np = { ...p, shape: rotated, x: p.x + offset };
            setCurrentPiece(np);
            pieceRef.current = np;
          }
          break;
        }
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [movePiece, rotatePieceFn, hardDrop, hold]);

  // Ghost piece
  const getGhostY = useCallback(() => {
    const p = pieceRef.current;
    if (!p) return 0;
    let gy = p.y;
    while (!checkCollision(boardRef.current, p.shape, p.x, gy + 1)) gy++;
    return gy;
  }, []);

  const ghostY = currentPiece ? getGhostY() : 0;

  // Render board with current piece
  const renderBoard = () => {
    const display = board.map(r => [...r]);
    if (currentPiece) {
      // Ghost
      for (let r = 0; r < currentPiece.shape.length; r++) {
        for (let c = 0; c < currentPiece.shape[r].length; c++) {
          if (currentPiece.shape[r][c]) {
            const ny = ghostY + r;
            const nx = currentPiece.x + c;
            if (ny >= 0 && ny < ROWS && nx >= 0 && nx < COLS && display[ny][nx] === null) {
              display[ny][nx] = currentPiece.color + '40';
            }
          }
        }
      }
      // Current
      for (let r = 0; r < currentPiece.shape.length; r++) {
        for (let c = 0; c < currentPiece.shape[r].length; c++) {
          if (currentPiece.shape[r][c]) {
            const ny = currentPiece.y + r;
            const nx = currentPiece.x + c;
            if (ny >= 0 && ny < ROWS && nx >= 0 && nx < COLS) {
              display[ny][nx] = currentPiece.color;
            }
          }
        }
      }
    }
    return display;
  };

  const displayBoard = renderBoard();

  const renderMiniPiece = (name: string | null) => {
    if (!name) return <div style={{ width: 60, height: 60 }} />;
    const t = TETROMINOES[name];
    return (
      <div className="flex flex-col items-center justify-center" style={{ width: 60, height: 60 }}>
        {t.shape.map((row, ri) => (
          <div key={ri} className="flex">
            {row.map((cell, ci) => (
              <div key={ci} style={{ width: 12, height: 12, background: cell ? t.color : 'transparent' }} />
            ))}
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="flex h-full select-none" style={{ background: 'var(--bg-window)', padding: 8 }} tabIndex={0}>
      {/* Game area */}
      <div className="flex flex-col items-center">
        {/* Board */}
        <div style={{ display: 'grid', gridTemplateColumns: `repeat(${COLS}, ${CELL}px)`, gap: 1, background: 'var(--border-subtle)', border: '2px solid var(--border-default)' }}>
          {displayBoard.map((row, r) =>
            row.map((cell, c) => (
              <div
                key={`${r}-${c}`}
                style={{
                  width: CELL,
                  height: CELL,
                  background: cell === null ? '#1A1A1A' : cell.length > 7 ? cell.slice(0, 7) + '40' : cell,
                  border: clearingRows.includes(r) ? '2px solid #fff' : 'none',
                  opacity: clearingRows.includes(r) ? 0.3 : 1,
                  transition: clearingRows.includes(r) ? 'opacity 0.2s' : 'none',
                }}
              />
            ))
          )}
        </div>
      </div>

      {/* Side panel */}
      <div className="flex flex-col ml-3 gap-2" style={{ width: 100 }}>
        {/* Next */}
        <div className="flex flex-col items-center" style={{ background: 'var(--bg-titlebar)', borderRadius: 8, padding: 8 }}>
          <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontWeight: 600 }}>NEXT</span>
          {renderMiniPiece(nextPiece)}
        </div>
        {/* Hold */}
        <div className="flex flex-col items-center" style={{ background: 'var(--bg-titlebar)', borderRadius: 8, padding: 8 }}>
          <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontWeight: 600 }}>HOLD</span>
          {renderMiniPiece(holdPiece)}
        </div>
        {/* Score */}
        <div className="flex flex-col items-center" style={{ background: 'var(--bg-titlebar)', borderRadius: 8, padding: 8 }}>
          <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)' }}>{score}</span>
          <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Lines: {lines}</span>
          <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Lv: {level}</span>
          <span style={{ fontSize: 10, color: 'var(--text-disabled)', marginTop: 4 }}>Best: {getHighScore()}</span>
        </div>
        {/* Controls */}
        <div className="flex flex-col gap-1">
          {gameState === 'menu' && (
            <button onClick={startGame} style={{ padding: '8px 0', background: 'var(--accent-primary)', color: '#fff', borderRadius: 8, border: 'none', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
              Start
            </button>
          )}
          {gameState === 'playing' && (
            <button onClick={() => { setGameState('paused'); gameRef.current = 'paused'; }} style={{ padding: '6px 0', background: 'var(--bg-hover)', color: 'var(--text-primary)', borderRadius: 8, border: '1px solid var(--border-default)', fontSize: 12, cursor: 'pointer' }}>
              Pause
            </button>
          )}
          {gameState === 'paused' && (
            <button onClick={() => { setGameState('playing'); gameRef.current = 'playing'; }} style={{ padding: '6px 0', background: 'var(--accent-primary)', color: '#fff', borderRadius: 8, border: 'none', fontSize: 12, cursor: 'pointer' }}>
              Resume
            </button>
          )}
          {gameState === 'over' && (
            <button onClick={startGame} style={{ padding: '8px 0', background: 'var(--accent-primary)', color: '#fff', borderRadius: 8, border: 'none', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
              Restart
            </button>
          )}
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-disabled)', lineHeight: 1.6 }}>
          ←→: Move<br/>↑: Rotate<br/>↓: Soft drop<br/>Space: Hard<br/>C: Hold<br/>P: Pause
        </div>
      </div>

      {/* Game over overlay */}
      {gameState === 'over' && (
        <div className="absolute inset-0 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.7)', zIndex: 20 }}>
          <div className="flex flex-col items-center" style={{ background: 'var(--bg-window)', padding: 24, borderRadius: 16, boxShadow: 'var(--shadow-xl)' }}>
            <span style={{ fontSize: 22, fontWeight: 700, color: 'var(--accent-error)' }}>Game Over</span>
            <span style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', marginTop: 8 }}>Score: {score}</span>
            <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Best: {getHighScore()}</span>
          </div>
        </div>
      )}
    </div>
  );
}

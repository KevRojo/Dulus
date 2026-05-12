import { useState, useEffect, useCallback } from 'react';
import { Brain, RotateCcw, Star, Clock, MousePointer } from 'lucide-react';

type Theme = 'colors' | 'numbers' | 'animals' | 'letters';
type Difficulty = 'easy' | 'medium' | 'hard' | 'expert';

interface Card {
  id: number;
  value: string;
  isFlipped: boolean;
  isMatched: boolean;
  color?: string;
}

const THEMES: Record<Theme, { values: string[]; colors?: string[] }> = {
  colors: {
    values: ['Red', 'Blue', 'Green', 'Yellow', 'Purple', 'Orange', 'Pink', 'Cyan', 'Lime', 'Brown', 'Magenta', 'Teal', 'Coral', 'Indigo', 'Gold', 'Silver', 'Crimson', 'Aqua'],
    colors: ['#F44336', '#2196F3', '#4CAF50', '#FFEB3B', '#9C27B0', '#FF9800', '#E91E63', '#00BCD4', '#8BC34A', '#795548', '#E91E8C', '#009688', '#FF7043', '#3F51B5', '#FFD700', '#9E9E9E', '#DC143C', '#00FFFF'],
  },
  numbers: { values: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18'] },
  animals: { values: ['🐶', '🐱', '🐭', '🐹', '🐰', '🦊', '🐻', '🐼', '🐨', '🐯', '🦁', '🐮', '🐷', '🐸', '🐵', '🐔', '🐧', '🐦'] },
  letters: { values: ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R'] },
};

const DIFFICULTIES: Record<Difficulty, { rows: number; cols: number; name: string }> = {
  easy: { rows: 3, cols: 4, name: 'Easy' },
  medium: { rows: 4, cols: 4, name: 'Medium' },
  hard: { rows: 4, cols: 6, name: 'Hard' },
  expert: { rows: 6, cols: 6, name: 'Expert' },
};

function getHighScore(diff: Difficulty): { moves: number; time: number } | null {
  const val = localStorage.getItem(`memory_best_${diff}`);
  return val ? JSON.parse(val) : null;
}
function setHighScore(diff: Difficulty, moves: number, time: number) {
  const current = getHighScore(diff);
  if (!current || moves < current.moves || (moves === current.moves && time < current.time)) {
    localStorage.setItem(`memory_best_${diff}`, JSON.stringify({ moves, time }));
  }
}

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function createCards(theme: Theme, difficulty: Difficulty): Card[] {
  const diff = DIFFICULTIES[difficulty];
  const pairCount = (diff.rows * diff.cols) / 2;
  const themeData = THEMES[theme];
  const selectedValues = themeData.values.slice(0, pairCount);
  const selectedColors = themeData.colors?.slice(0, pairCount);
  
  const cards: Card[] = [];
  selectedValues.forEach((val, i) => {
    cards.push({ id: i * 2, value: val, isFlipped: false, isMatched: false, color: selectedColors?.[i] });
    cards.push({ id: i * 2 + 1, value: val, isFlipped: false, isMatched: false, color: selectedColors?.[i] });
  });
  return shuffle(cards);
}

export default function Memory() {
  const [theme, setTheme] = useState<Theme>('animals');
  const [difficulty, setDifficulty] = useState<Difficulty>('easy');
  const [cards, setCards] = useState<Card[]>([]);
  const [flippedCards, setFlippedCards] = useState<number[]>([]);
  const [moves, setMoves] = useState(0);
  const [matches, setMatches] = useState(0);
  const [timer, setTimer] = useState(0);
  const [gameState, setGameState] = useState<'menu' | 'playing' | 'won'>('menu');
  const [isLocked, setIsLocked] = useState(false);

  // Timer
  useEffect(() => {
    if (gameState !== 'playing') return;
    const interval = setInterval(() => setTimer(t => t + 1), 1000);
    return () => clearInterval(interval);
  }, [gameState]);

  const startGame = useCallback(() => {
    setCards(createCards(theme, difficulty));
    setFlippedCards([]);
    setMoves(0);
    setMatches(0);
    setTimer(0);
    setGameState('playing');
    setIsLocked(false);
  }, [theme, difficulty]);

  const handleCardClick = useCallback((index: number) => {
    if (isLocked || gameState !== 'playing') return;
    const card = cards[index];
    if (card.isFlipped || card.isMatched || flippedCards.includes(index)) return;

    const newFlipped = [...flippedCards, index];
    const newCards = cards.map((c, i) => i === index ? { ...c, isFlipped: true } : { ...c });
    setCards(newCards);
    setFlippedCards(newFlipped);

    if (newFlipped.length === 2) {
      setMoves(m => m + 1);
      const [first, second] = newFlipped;
      if (newCards[first].value === newCards[second].value) {
        // Match
        setTimeout(() => {
          setCards(prev => prev.map((c, i) => 
            i === first || i === second ? { ...c, isMatched: true } : c
          ));
          setFlippedCards([]);
          setMatches(m => {
            const newMatches = m + 1;
            const totalPairs = cards.length / 2;
            if (newMatches === totalPairs) {
              setGameState('won');
              setHighScore(difficulty, moves + 1, timer);
            }
            return newMatches;
          });
        }, 500);
      } else {
        // No match
        setIsLocked(true);
        setTimeout(() => {
          setCards(prev => prev.map((c, i) => 
            i === first || i === second ? { ...c, isFlipped: false } : c
          ));
          setFlippedCards([]);
          setIsLocked(false);
        }, 1000);
      }
    }
  }, [cards, flippedCards, isLocked, gameState, difficulty, moves, timer]);

  const getStarRating = () => {
    const totalPairs = cards.length / 2;
    const ratio = moves / totalPairs;
    if (ratio <= 1.3) return 3;
    if (ratio <= 1.8) return 2;
    return 1;
  };

  const diff = DIFFICULTIES[difficulty];
  const highScore = getHighScore(difficulty);

  if (gameState === 'menu') {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3" style={{ background: 'var(--bg-window)', padding: 16 }}>
        <Brain size={36} style={{ color: 'var(--accent-primary)' }} />
        <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--accent-primary)' }}>Memory Game</div>
        
        {/* Theme selector */}
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>Theme</div>
        <div className="flex gap-1">
          {(['animals', 'colors', 'numbers', 'letters'] as Theme[]).map(t => (
            <button key={t} onClick={() => setTheme(t)}
              style={{ padding: '4px 12px', background: theme === t ? 'var(--accent-primary)' : 'var(--bg-hover)', color: theme === t ? '#fff' : 'var(--text-secondary)', borderRadius: 6, border: 'none', fontSize: 12, cursor: 'pointer', textTransform: 'capitalize' }}>
              {t}
            </button>
          ))}
        </div>

        {/* Difficulty selector */}
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>Difficulty</div>
        <div className="flex gap-1">
          {(Object.keys(DIFFICULTIES) as Difficulty[]).map(d => (
            <button key={d} onClick={() => setDifficulty(d)}
              style={{ padding: '4px 12px', background: difficulty === d ? 'var(--accent-primary)' : 'var(--bg-hover)', color: difficulty === d ? '#fff' : 'var(--text-secondary)', borderRadius: 6, border: 'none', fontSize: 12, cursor: 'pointer' }}>
              {DIFFICULTIES[d].name}
            </button>
          ))}
        </div>

        {highScore && (
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
            Best: {highScore.moves} moves in {highScore.time}s
          </div>
        )}

        <button onClick={startGame} style={{ marginTop: 8, padding: '10px 32px', background: 'var(--accent-primary)', color: '#fff', borderRadius: 10, border: 'none', fontSize: 15, fontWeight: 600, cursor: 'pointer' }}>
          Start Game
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center h-full" style={{ background: 'var(--bg-window)', padding: 12 }}>
      {/* HUD */}
      <div className="flex items-center justify-between w-full mb-2" style={{ padding: '4px 8px', background: 'var(--bg-titlebar)', borderRadius: 8 }}>
        <div className="flex items-center gap-1" style={{ fontSize: 12, color: 'var(--text-primary)' }}>
          <MousePointer size={14} /> {moves}
        </div>
        <div className="flex items-center gap-1" style={{ fontSize: 12, color: 'var(--text-primary)' }}>
          <Clock size={14} /> {timer}s
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-primary)' }}>
          {matches}/{cards.length / 2}
        </div>
      </div>

      {/* Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${diff.cols}, 72px)`,
        gap: 8,
        justifyContent: 'center',
      }}>
        {cards.map((card, index) => (
          <div
            key={card.id}
            onClick={() => handleCardClick(index)}
            style={{
              width: 72, height: 72,
              borderRadius: 12,
              cursor: card.isMatched ? 'default' : 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: card.isFlipped || card.isMatched ? (theme === 'animals' ? 32 : 24) : 20,
              fontWeight: 700,
              transition: 'all 0.3s ease',
              transform: card.isFlipped || card.isMatched ? 'rotateY(0deg)' : 'rotateY(180deg)',
              background: card.isMatched
                ? 'rgba(76,175,80,0.2)'
                : card.isFlipped
                  ? (theme === 'colors' ? card.color : 'var(--bg-window)')
                  : 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))',
              border: card.isMatched ? '2px solid var(--accent-success)' : card.isFlipped ? '2px solid var(--accent-primary)' : '2px solid transparent',
              boxShadow: card.isMatched ? '0 0 12px rgba(76,175,80,0.3)' : 'var(--shadow-sm)',
              color: theme === 'colors' && card.isFlipped ? '#fff' : 'var(--text-primary)',
            }}
          >
            {card.isFlipped || card.isMatched ? (
              <span>{card.value}</span>
            ) : (
              <Brain size={24} style={{ color: '#fff' }} />
            )}
          </div>
        ))}
      </div>

      {/* Win overlay */}
      {gameState === 'won' && (
        <div className="absolute inset-0 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.7)', zIndex: 20, borderRadius: 12 }}>
          <div className="flex flex-col items-center" style={{ background: 'var(--bg-window)', padding: 24, borderRadius: 16 }}>
            <div className="flex gap-1 mb-2">
              {[1, 2, 3].map(i => (
                <Star key={i} size={28} style={{ color: i <= getStarRating() ? 'var(--accent-secondary)' : 'var(--border-default)', fill: i <= getStarRating() ? 'var(--accent-secondary)' : 'transparent' }} />
              ))}
            </div>
            <span style={{ fontSize: 22, fontWeight: 700, color: 'var(--accent-success)' }}>You Win!</span>
            <span style={{ fontSize: 14, color: 'var(--text-primary)', marginTop: 4 }}>{moves} moves in {timer}s</span>
            <div className="flex gap-2 mt-3">
              <button onClick={startGame} style={{ padding: '8px 20px', background: 'var(--accent-primary)', color: '#fff', borderRadius: 8, border: 'none', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
                Play Again
              </button>
              <button onClick={() => setGameState('menu')} style={{ padding: '8px 20px', background: 'var(--bg-hover)', color: 'var(--text-primary)', borderRadius: 8, border: '1px solid var(--border-default)', fontSize: 13, cursor: 'pointer' }}>
                Menu
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

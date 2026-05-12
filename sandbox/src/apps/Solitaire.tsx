import { useState, useCallback, useEffect } from 'react';
import { Layers, RotateCcw, Undo2, Settings } from 'lucide-react';

type Suit = 'hearts' | 'diamonds' | 'clubs' | 'spades';
type Rank = 'A' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9' | '10' | 'J' | 'Q' | 'K';

interface Card {
  suit: Suit;
  rank: Rank;
  faceUp: boolean;
  id: string;
}

interface GameState {
  tableau: Card[][];
  foundation: Card[][];
  stock: Card[];
  waste: Card[];
  score: number;
  moves: number;
  timer: number;
  drawThree: boolean;
  history: GameSnapshot[];
  selectedCard: { pile: string; index: number; card: Card } | null;
  gameWon: boolean;
}

interface GameSnapshot {
  tableau: Card[][];
  foundation: Card[][];
  stock: Card[];
  waste: Card[];
  score: number;
}

const SUITS: Suit[] = ['hearts', 'diamonds', 'clubs', 'spades'];
const RANKS: Rank[] = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K'];
const SUIT_SYMBOLS: Record<Suit, string> = { hearts: '♥', diamonds: '♦', clubs: '♣', spades: '♠' };
const SUIT_COLORS: Record<Suit, string> = { hearts: '#D32F2F', diamonds: '#D32F2F', clubs: '#212121', spades: '#212121' };
const RANK_VALUES: Record<Rank, number> = { A: 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10, J: 11, Q: 12, K: 13 };

function createDeck(): Card[] {
  const deck: Card[] = [];
  for (const suit of SUITS) {
    for (const rank of RANKS) {
      deck.push({ suit, rank, faceUp: false, id: `${suit}-${rank}` });
    }
  }
  // Shuffle
  for (let i = deck.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [deck[i], deck[j]] = [deck[j], deck[i]];
  }
  return deck;
}

function dealCards(): { tableau: Card[][]; stock: Card[] } {
  const deck = createDeck();
  const tableau: Card[][] = [];
  let deckIdx = 0;
  for (let col = 0; col < 7; col++) {
    tableau[col] = [];
    for (let row = 0; row <= col; row++) {
      const card = { ...deck[deckIdx++], faceUp: row === col };
      tableau[col].push(card);
    }
  }
  const stock = deck.slice(deckIdx).map(c => ({ ...c, faceUp: false }));
  return { tableau, stock };
}

function isRed(suit: Suit): boolean {
  return suit === 'hearts' || suit === 'diamonds';
}

function canPlaceOnTableau(topCard: Card | null, card: Card): boolean {
  if (!topCard) return card.rank === 'K';
  if (isRed(topCard.suit) === isRed(card.suit)) return false;
  return RANK_VALUES[card.rank] === RANK_VALUES[topCard.rank] - 1;
}

function canPlaceOnFoundation(topCard: Card | null, card: Card): boolean {
  if (!topCard) return card.rank === 'A';
  if (topCard.suit !== card.suit) return false;
  return RANK_VALUES[card.rank] === RANK_VALUES[topCard.rank] + 1;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export default function Solitaire() {
  const [state, setState] = useState<GameState>(() => {
    const { tableau, stock } = dealCards();
    return {
      tableau,
      foundation: [[], [], [], []],
      stock,
      waste: [],
      score: 0,
      moves: 0,
      timer: 0,
      drawThree: true,
      history: [],
      selectedCard: null,
      gameWon: false,
    };
  });

  // Timer
  useEffect(() => {
    if (state.gameWon) return;
    const interval = setInterval(() => setState(s => ({ ...s, timer: s.timer + 1 })), 1000);
    return () => clearInterval(interval);
  }, [state.gameWon]);

  const saveSnapshot = useCallback((s: GameState): GameSnapshot => ({
    tableau: s.tableau.map(col => col.map(c => ({ ...c }))),
    foundation: s.foundation.map(col => col.map(c => ({ ...c }))),
    stock: s.stock.map(c => ({ ...c })),
    waste: s.waste.map(c => ({ ...c })),
    score: s.score,
  }), []);

  const restoreSnapshot = useCallback((s: GameState, snap: GameSnapshot): GameState => ({
    ...s,
    tableau: snap.tableau,
    foundation: snap.foundation,
    stock: snap.stock,
    waste: snap.waste,
    score: snap.score,
  }), []);

  const handleStockClick = useCallback(() => {
    setState(s => {
      if (s.stock.length === 0) {
        if (s.waste.length === 0) return s;
        // Recycle waste to stock
        return {
          ...s,
          stock: s.waste.reverse().map(c => ({ ...c, faceUp: false })),
          waste: [],
          score: Math.max(0, s.score - 100),
          moves: s.moves + 1,
          history: [...s.history, saveSnapshot(s)],
        };
      }
      const drawCount = s.drawThree ? 3 : 1;
      const drawn = s.stock.slice(0, drawCount).map(c => ({ ...c, faceUp: true }));
      const remaining = s.stock.slice(drawCount);
      return {
        ...s,
        stock: remaining,
        waste: [...drawn, ...s.waste],
        moves: s.moves + 1,
        history: [...s.history, saveSnapshot(s)],
      };
    });
  }, [saveSnapshot]);

  const handleCardClick = useCallback((pile: string, index: number, card: Card) => {
    setState(s => {
      if (s.selectedCard) {
        const sel = s.selectedCard;
        // Don't allow moving to same pile at same index
        if (sel.pile === pile && sel.index === index) {
          return { ...s, selectedCard: null };
        }

        let newState: GameState = { ...s, selectedCard: null };
        const snap = saveSnapshot(s);

        // Try to move selected card to target
        if (pile.startsWith('foundation')) {
          const fIdx = parseInt(pile.split('-')[1]);
          const topCard = s.foundation[fIdx].length > 0 ? s.foundation[fIdx][s.foundation[fIdx].length - 1] : null;
          // Only move single cards to foundation
          if (canPlaceOnFoundation(topCard, sel.card)) {
            // Remove from source
            const sourceUpdates = removeCardFromSource(s, sel);
            newState = { ...newState, ...sourceUpdates };
            newState.foundation = newState.foundation.map((col, i) =>
              i === fIdx ? [...col, sel.card] : col
            );
            newState.score += 10;
            newState.moves += 1;
            newState.history = [...newState.history, snap];
            return checkWin(newState);
          }
        } else if (pile.startsWith('tableau')) {
          const tIdx = parseInt(pile.split('-')[1]);
          const topCard = s.tableau[tIdx].length > 0 ? s.tableau[tIdx][s.tableau[tIdx].length - 1] : null;
          // Get cards to move (if from tableau, move sequence)
          const cardsToMove = sel.pile.startsWith('tableau')
            ? s.tableau[parseInt(sel.pile.split('-')[1])].slice(sel.index)
            : [sel.card];
          if (canPlaceOnTableau(topCard, cardsToMove[0])) {
            const sourceUpdates = removeCardFromSource(s, sel);
            newState = { ...newState, ...sourceUpdates };
            newState.tableau = newState.tableau.map((col, i) =>
              i === tIdx ? [...col, ...cardsToMove] : col
            );
            if (sel.pile.startsWith('waste')) newState.score += 5;
            newState.moves += 1;
            newState.history = [...newState.history, snap];
            return checkWin(newState);
          }
        }

        // If can't place, select the new card instead
        return { ...s, selectedCard: { pile, index, card } };
      }

      // Select the card
      return { ...s, selectedCard: { pile, index, card } };
    });
  }, [saveSnapshot]);

  const removeCardFromSource = (s: GameState, sel: { pile: string; index: number }): Partial<GameState> => {
    if (sel.pile.startsWith('tableau')) {
      const tIdx = parseInt(sel.pile.split('-')[1]);
      const newTableau = s.tableau.map((col, i) => {
        if (i !== tIdx) return col;
        const newCol = col.slice(0, sel.index);
        // Flip top card if face down
        if (newCol.length > 0 && !newCol[newCol.length - 1].faceUp) {
          newCol[newCol.length - 1] = { ...newCol[newCol.length - 1], faceUp: true };
        }
        return newCol;
      });
      return { tableau: newTableau };
    } else if (sel.pile.startsWith('foundation')) {
      const fIdx = parseInt(sel.pile.split('-')[1]);
      return { foundation: s.foundation.map((col, i) => i === fIdx ? col.slice(0, -1) : col) };
    } else if (sel.pile === 'waste') {
      return { waste: s.waste.slice(1) };
    }
    return {};
  };

  const checkWin = (s: GameState): GameState => {
    const allInFoundation = s.foundation.every(col => col.length === 13);
    if (allInFoundation) {
      return { ...s, gameWon: true, score: s.score + 10000 };
    }
    return s;
  };

  const undo = useCallback(() => {
    setState(s => {
      if (s.history.length === 0) return s;
      const lastSnap = s.history[s.history.length - 1];
      return { ...restoreSnapshot(s, lastSnap), history: s.history.slice(0, -1), moves: s.moves + 1, selectedCard: null };
    });
  }, [restoreSnapshot]);

  const newGame = useCallback(() => {
    const { tableau, stock } = dealCards();
    setState({
      tableau,
      foundation: [[], [], [], []],
      stock,
      waste: [],
      score: 0,
      moves: 0,
      timer: 0,
      drawThree: true,
      history: [],
      selectedCard: null,
      gameWon: false,
    });
  }, []);

  const autoMoveToFoundation = useCallback(() => {
    setState(s => {
      let newState = { ...s };
      let moved = false;
      // Check waste top
      if (s.waste.length > 0) {
        const card = s.waste[0];
        for (let i = 0; i < 4; i++) {
          const top = s.foundation[i].length > 0 ? s.foundation[i][s.foundation[i].length - 1] : null;
          if (canPlaceOnFoundation(top, card)) {
            const snap = saveSnapshot(s);
            newState = { ...newState, waste: newState.waste.slice(1), score: newState.score + 10, moves: newState.moves + 1, history: [...newState.history, snap] };
            newState.foundation = newState.foundation.map((col, fi) => fi === i ? [...col, card] : col);
            moved = true;
            break;
          }
        }
      }
      if (!moved) {
        // Check tableau tops
        for (let t = 0; t < 7; t++) {
          if (s.tableau[t].length === 0) continue;
          const card = s.tableau[t][s.tableau[t].length - 1];
          for (let i = 0; i < 4; i++) {
            const top = s.foundation[i].length > 0 ? s.foundation[i][s.foundation[i].length - 1] : null;
            if (canPlaceOnFoundation(top, card)) {
              const snap = saveSnapshot(s);
              newState = {
                ...newState,
                tableau: newState.tableau.map((col, ti) => {
                  if (ti !== t) return col;
                  const newCol = col.slice(0, -1);
                  if (newCol.length > 0 && !newCol[newCol.length - 1].faceUp) {
                    newCol[newCol.length - 1] = { ...newCol[newCol.length - 1], faceUp: true };
                  }
                  return newCol;
                }),
                score: newState.score + 10,
                moves: newState.moves + 1,
                history: [...newState.history, snap],
              };
              newState.foundation = newState.foundation.map((col, fi) => fi === i ? [...col, card] : col);
              moved = true;
              break;
            }
          }
          if (moved) break;
        }
      }
      return checkWin(newState);
    });
  }, [saveSnapshot]);

  // Card rendering
  const renderCard = (card: Card, pile: string, index: number, isTop: boolean, overlap = false) => {
    const isSelected = state.selectedCard?.pile === pile && state.selectedCard?.index === index;
    if (!card.faceUp) {
      return (
        <div key={card.id} style={{
          width: 60, height: 84, borderRadius: 6,
          background: 'repeating-linear-gradient(45deg, #1565C0, #1565C0 4px, #0D47A1 4px, #0D47A1 8px)',
          border: '1px solid #0D47A1',
          marginTop: overlap ? -60 : 0,
        }} />
      );
    }

    return (
      <div key={card.id}
        onClick={() => handleCardClick(pile, index, card)}
        style={{
          width: 60, height: 84, borderRadius: 6,
          background: isSelected ? '#FFF9C4' : '#fff',
          border: isSelected ? '2px solid var(--accent-primary)' : '1px solid #DDD',
          marginTop: overlap ? -60 : 0,
          cursor: 'pointer',
          display: 'flex', flexDirection: 'column', justifyContent: 'space-between', padding: '3px 4px',
          position: 'relative',
          zIndex: isSelected ? 10 : index,
          boxShadow: isSelected ? '0 2px 8px rgba(0,0,0,0.3)' : 'none',
        }}
      >
        <div style={{ fontSize: 10, fontWeight: 700, color: SUIT_COLORS[card.suit], lineHeight: 1 }}>{card.rank}</div>
        <div style={{ fontSize: 22, color: SUIT_COLORS[card.suit], alignSelf: 'center', lineHeight: 1 }}>{SUIT_SYMBOLS[card.suit]}</div>
        <div style={{ fontSize: 10, fontWeight: 700, color: SUIT_COLORS[card.suit], alignSelf: 'flex-end', lineHeight: 1, transform: 'rotate(180deg)' }}>{card.rank}</div>
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full select-none" style={{ background: 'linear-gradient(135deg, #1B5E20, #2E7D32)', padding: 8 }}>
      {/* Top bar */}
      <div className="flex items-center justify-between mb-2" style={{ padding: '4px 8px', background: 'rgba(0,0,0,0.2)', borderRadius: 8 }}>
        <div className="flex items-center gap-3">
          <span style={{ fontSize: 12, color: '#fff', fontWeight: 600 }}>Score: {state.score}</span>
          <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.7)' }}>Moves: {state.moves}</span>
          <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.7)' }}>{formatTime(state.timer)}</span>
        </div>
        <div className="flex gap-1">
          <button onClick={autoMoveToFoundation} style={{ padding: '4px 10px', background: 'rgba(255,255,255,0.15)', color: '#fff', borderRadius: 6, border: 'none', fontSize: 11, cursor: 'pointer' }}>
            Auto
          </button>
          <button onClick={undo} style={{ padding: '4px 8px', background: 'rgba(255,255,255,0.15)', color: '#fff', borderRadius: 6, border: 'none', fontSize: 11, cursor: 'pointer' }}>
            <Undo2 size={14} />
          </button>
          <button onClick={newGame} style={{ padding: '4px 8px', background: 'rgba(255,255,255,0.15)', color: '#fff', borderRadius: 6, border: 'none', fontSize: 11, cursor: 'pointer' }}>
            <RotateCcw size={14} />
          </button>
        </div>
      </div>

      {/* Top row: Stock, Waste, Foundation */}
      <div className="flex justify-between mb-3">
        <div className="flex gap-2">
          {/* Stock */}
          <div onClick={handleStockClick} style={{ width: 60, height: 84, borderRadius: 6, background: state.stock.length > 0 ? 'repeating-linear-gradient(45deg, #1565C0, #1565C0 4px, #0D47A1 4px, #0D47A1 8px)' : 'rgba(255,255,255,0.1)', border: '1px dashed rgba(255,255,255,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
            {state.stock.length === 0 && <RotateCcw size={20} style={{ color: 'rgba(255,255,255,0.5)' }} />}
          </div>
          {/* Waste */}
          <div style={{ width: 60, height: 84 }}>
            {state.waste.length > 0 && renderCard(state.waste[0], 'waste', 0, true)}
          </div>
        </div>
        {/* Foundation */}
        <div className="flex gap-2">
          {state.foundation.map((pile, i) => (
            <div key={i} style={{ width: 60, height: 84, borderRadius: 6, border: '1px dashed rgba(255,255,255,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(255,255,255,0.05)' }}>
              {pile.length === 0 ? (
                <span style={{ fontSize: 24, color: 'rgba(255,255,255,0.3)' }}>{SUIT_SYMBOLS[SUITS[i]]}</span>
              ) : (
                renderCard(pile[pile.length - 1], `foundation-${i}`, pile.length - 1, true)
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Tableau */}
      <div className="flex gap-2" style={{ flex: 1 }}>
        {state.tableau.map((pile, colIdx) => (
          <div key={colIdx} className="flex flex-col items-center" style={{ width: 62 }}>
            {/* Empty column placeholder */}
            {pile.length === 0 && (
              <div onClick={() => {
                if (state.selectedCard) {
                  handleCardClick(`tableau-${colIdx}`, 0, { suit: 'hearts', rank: 'A', faceUp: true, id: 'empty' });
                }
              }}
                style={{ width: 60, height: 84, borderRadius: 6, border: '1px dashed rgba(255,255,255,0.2)', background: 'rgba(255,255,255,0.03)', cursor: 'pointer' }} />
            )}
            {pile.map((card, cardIdx) => renderCard(card, `tableau-${colIdx}`, cardIdx, cardIdx === pile.length - 1, cardIdx > 0))}
          </div>
        ))}
      </div>

      {/* Win overlay */}
      {state.gameWon && (
        <div className="absolute inset-0 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.7)', zIndex: 20, borderRadius: 12 }}>
          <div className="flex flex-col items-center" style={{ background: '#fff', padding: 32, borderRadius: 16 }}>
            <span style={{ fontSize: 28, fontWeight: 800, color: '#1B5E20' }}>You Win!</span>
            <span style={{ fontSize: 14, color: '#666', marginTop: 8 }}>Score: {state.score} | Moves: {state.moves} | Time: {formatTime(state.timer)}</span>
            <button onClick={newGame} style={{ marginTop: 16, padding: '10px 28px', background: '#1B5E20', color: '#fff', borderRadius: 8, border: 'none', fontSize: 15, fontWeight: 600, cursor: 'pointer' }}>
              Play Again
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

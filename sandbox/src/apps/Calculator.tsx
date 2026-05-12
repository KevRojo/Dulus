// ============================================================
// Calculator v2 — Polished native Dulus app
// ============================================================

import { useState, useEffect, useCallback, useRef } from 'react';
import { Delete, History, ChevronLeft } from 'lucide-react';
import AppContainer from '@/components/AppContainer';

type CalcMode = 'standard' | 'scientific';

interface HistoryEntry {
  expr: string;
  result: string;
}

const Calculator: React.FC = () => {
  const [mode, setMode] = useState<CalcMode>('standard');
  const [display, setDisplay] = useState('0');
  const [prevExpr, setPrevExpr] = useState('');
  const [history, setHistory] = useState<HistoryEntry[]>(() => {
    try { const s = localStorage.getItem('calc_history'); return s ? JSON.parse(s) : []; } catch { return []; }
  });
  const [showHistory, setShowHistory] = useState(false);
  const [memory, setMemory] = useState<number>(() => {
    try { return Number(localStorage.getItem('calc_memory') || '0'); } catch { return 0; }
  });
  const [waitingForOperand, setWaitingForOperand] = useState(false);
  const [operator, setOperator] = useState<string | null>(null);
  const [operand, setOperand] = useState<number | null>(null);
  const historyEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    localStorage.setItem('calc_history', JSON.stringify(history));
  }, [history]);

  useEffect(() => {
    localStorage.setItem('calc_memory', String(memory));
  }, [memory]);

  const formatNumber = (n: number): string => {
    if (!isFinite(n)) return 'Error';
    if (isNaN(n)) return 'Error';
    const s = String(n);
    if (s.length > 14) return n.toExponential(9);
    return s;
  };

  const evaluate = (a: number, op: string, b: number): number => {
    switch (op) {
      case '+': return a + b;
      case '-': return a - b;
      case '*': return a * b;
      case '/': return b === 0 ? NaN : a / b;
      case '%': return b === 0 ? NaN : a % b;
      case '^': return Math.pow(a, b);
      default: return b;
    }
  };

  const calculate = useCallback(() => {
    if (operator === null || operand === null) return;
    const current = parseFloat(display);
    const result = evaluate(operand, operator, current);
    const resultStr = formatNumber(result);
    setHistory(prev => [{ expr: `${operand} ${operator} ${current}`, result: resultStr }, ...prev].slice(0, 50));
    setPrevExpr(`${operand} ${operator} ${current} =`);
    setDisplay(resultStr);
    setOperator(null);
    setOperand(null);
    setWaitingForOperand(true);
  }, [display, operator, operand]);

  const inputDigit = (digit: string) => {
    if (waitingForOperand) {
      setDisplay(digit);
      setWaitingForOperand(false);
    } else {
      setDisplay(display === '0' ? digit : display + digit);
    }
  };

  const inputDecimal = () => {
    if (waitingForOperand) {
      setDisplay('0.');
      setWaitingForOperand(false);
      return;
    }
    if (!display.includes('.')) setDisplay(display + '.');
  };

  const performOp = (op: string) => {
    const current = parseFloat(display);
    if (operator && !waitingForOperand) {
      const result = evaluate(operand || 0, operator, current);
      setDisplay(formatNumber(result));
      setOperand(result);
    } else {
      setOperand(current);
    }
    setOperator(op);
    setWaitingForOperand(true);
    setPrevExpr(`${current} ${op}`);
  };

  const clear = () => {
    setDisplay('0');
    setPrevExpr('');
    setOperator(null);
    setOperand(null);
    setWaitingForOperand(false);
  };

  const backspace = () => {
    if (waitingForOperand) return;
    if (display.length === 1 || (display.length === 2 && display[0] === '-')) {
      setDisplay('0');
    } else {
      setDisplay(display.slice(0, -1));
    }
  };

  const percentage = () => {
    const v = parseFloat(display);
    setDisplay(formatNumber(v / 100));
  };

  const sciFunc = (fn: string) => {
    const v = parseFloat(display);
    let result = 0;
    switch (fn) {
      case 'sin': result = Math.sin(v); break;
      case 'cos': result = Math.cos(v); break;
      case 'tan': result = Math.tan(v); break;
      case 'log': result = Math.log10(v); break;
      case 'ln': result = Math.log(v); break;
      case 'sqrt': result = Math.sqrt(v); break;
      case 'square': result = v * v; break;
      case 'cube': result = v * v * v; break;
      case '1/x': result = 1 / v; break;
      case 'factorial': result = v < 0 || !Number.isInteger(v) ? NaN : Array.from({ length: Math.floor(v) }, (_, i) => i + 1).reduce((a, b) => a * b, 1); break;
      case 'abs': result = Math.abs(v); break;
      case 'pi': setDisplay(String(Math.PI)); setWaitingForOperand(true); return;
      case 'e': setDisplay(String(Math.E)); setWaitingForOperand(true); return;
      default: return;
    }
    const resultStr = formatNumber(result);
    setHistory(prev => [{ expr: `${fn}(${v})`, result: resultStr }, ...prev].slice(0, 50));
    setPrevExpr(`${fn}(${v}) =`);
    setDisplay(resultStr);
    setWaitingForOperand(true);
  };

  const memoryAdd = () => setMemory(m => m + parseFloat(display));
  const memorySubtract = () => setMemory(m => m - parseFloat(display));
  const memoryClear = () => setMemory(0);
  const memoryRecall = () => { setDisplay(formatNumber(memory)); setWaitingForOperand(true); };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key >= '0' && e.key <= '9') inputDigit(e.key);
      else if (e.key === '.') inputDecimal();
      else if (e.key === '+') performOp('+');
      else if (e.key === '-') performOp('-');
      else if (e.key === '*') performOp('*');
      else if (e.key === '/') { e.preventDefault(); performOp('/'); }
      else if (e.key === 'Enter' || e.key === '=') calculate();
      else if (e.key === 'Escape') clear();
      else if (e.key === 'Backspace') backspace();
      else if (e.key === '%') percentage();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [display, waitingForOperand, operator, operand]);

  const Btn: React.FC<{
    label: React.ReactNode;
    onClick?: () => void;
    variant?: 'num' | 'op' | 'action' | 'eq' | 'sci';
    className?: string;
    colSpan?: number;
  }> = ({ label, onClick, variant = 'num', className = '', colSpan }) => {
    const base = 'h-12 rounded-xl text-sm font-semibold transition-all duration-100 active:scale-95 flex items-center justify-center shadow-sm';
    const styles: Record<string, string> = {
      num: 'bg-[var(--bg-panel)] hover:bg-[var(--bg-hover)] text-[var(--text-primary)] border border-[var(--border-subtle)]',
      op: 'bg-[var(--bg-titlebar)] hover:bg-[var(--bg-hover)] text-[var(--accent-primary)] border border-[var(--border-default)]',
      action: 'bg-[var(--bg-titlebar)] hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] border border-[var(--border-default)]',
      eq: 'bg-[var(--accent-primary)] hover:bg-[var(--accent-primary-hover)] text-white shadow-md shadow-[var(--accent-primary)]/20',
      sci: 'bg-[var(--bg-titlebar)] hover:bg-[var(--bg-hover)] text-[var(--text-primary)] text-xs border border-[var(--border-subtle)]',
    };
    return (
      <button
        onClick={onClick}
        className={`${base} ${styles[variant]} ${className}`}
        style={colSpan ? { gridColumn: `span ${colSpan}` } : undefined}
      >
        {label}
      </button>
    );
  };

  return (
    <AppContainer noPadding className="select-none">
      {/* Mode toggle */}
      <div
        className="flex items-center justify-between px-3 h-10 border-b shrink-0"
        style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-titlebar)' }}
      >
        <div className="flex gap-1">
          <button
            onClick={() => setMode('standard')}
            className={`text-xs px-3 py-1 rounded-lg transition-colors ${mode === 'standard' ? 'text-[var(--accent-primary)] font-semibold bg-[var(--bg-selected)]' : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'}`}
          >
            Standard
          </button>
          <button
            onClick={() => setMode('scientific')}
            className={`text-xs px-3 py-1 rounded-lg transition-colors ${mode === 'scientific' ? 'text-[var(--accent-primary)] font-semibold bg-[var(--bg-selected)]' : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'}`}
          >
            Scientific
          </button>
        </div>
        <button
          onClick={() => setShowHistory(!showHistory)}
          className={`p-1.5 rounded-lg transition-colors ${showHistory ? 'text-[var(--accent-primary)] bg-[var(--bg-selected)]' : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]'}`}
        >
          <History size={16} />
        </button>
      </div>

      {/* Display */}
      <div className="flex flex-col items-end justify-center px-5 py-4 shrink-0" style={{ minHeight: 88 }}>
        <div className="text-xs text-[var(--text-secondary)] truncate w-full text-right font-medium tracking-wide" style={{ minHeight: 18 }}>
          {prevExpr}
        </div>
        <div
          className="font-light text-right w-full truncate tracking-tight"
          style={{
            fontSize: display.length > 12 ? 26 : 38,
            color: display === 'Error' ? 'var(--accent-error)' : 'var(--text-primary)',
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {display}
        </div>
        {memory !== 0 && <div className="text-[10px] text-[var(--accent-primary)] font-semibold uppercase tracking-wider">M</div>}
      </div>

      {/* History panel */}
      {showHistory && (
        <div
          className="shrink-0 overflow-auto custom-scrollbar px-3 py-2 border-t"
          style={{ borderColor: 'var(--border-subtle)', maxHeight: 140, background: 'var(--bg-panel)' }}
        >
          {history.length === 0 ? (
            <div className="text-xs text-[var(--text-disabled)] text-center py-3">No history yet</div>
          ) : (
            <>
              {history.map((h, i) => (
                <button
                  key={i}
                  onClick={() => { setDisplay(h.result); setWaitingForOperand(true); }}
                  className="w-full text-right py-1.5 px-3 rounded-lg hover:bg-[var(--bg-hover)] transition-colors"
                >
                  <div className="text-[10px] text-[var(--text-secondary)] font-medium">{h.expr}</div>
                  <div className="text-sm text-[var(--text-primary)] font-semibold" style={{ fontVariantNumeric: 'tabular-nums' }}>{h.result}</div>
                </button>
              ))}
              <div ref={historyEndRef} />
              <button
                onClick={() => setHistory([])}
                className="w-full text-center text-xs text-[var(--accent-error)] py-2 hover:underline font-medium"
              >
                Clear History
              </button>
            </>
          )}
        </div>
      )}

      {/* Buttons */}
      <div className="flex-1 p-2 min-h-0">
        {mode === 'standard' ? (
          <div className="grid grid-cols-4 gap-2 h-full">
            <Btn label="AC" onClick={clear} variant="action" />
            <Btn label={<ChevronLeft size={16} />} onClick={backspace} variant="action" />
            <Btn label="%" onClick={percentage} variant="action" />
            <Btn label="÷" onClick={() => performOp('/')} variant="op" />
            <Btn label="7" onClick={() => inputDigit('7')} />
            <Btn label="8" onClick={() => inputDigit('8')} />
            <Btn label="9" onClick={() => inputDigit('9')} />
            <Btn label="×" onClick={() => performOp('*')} variant="op" />
            <Btn label="4" onClick={() => inputDigit('4')} />
            <Btn label="5" onClick={() => inputDigit('5')} />
            <Btn label="6" onClick={() => inputDigit('6')} />
            <Btn label="−" onClick={() => performOp('-')} variant="op" />
            <Btn label="1" onClick={() => inputDigit('1')} />
            <Btn label="2" onClick={() => inputDigit('2')} />
            <Btn label="3" onClick={() => inputDigit('3')} />
            <Btn label="+" onClick={() => performOp('+')} variant="op" />
            <Btn label="0" onClick={() => inputDigit('0')} colSpan={2} />
            <Btn label="." onClick={inputDecimal} />
            <Btn label="=" onClick={calculate} variant="eq" />
          </div>
        ) : (
          <div className="grid grid-cols-5 gap-1.5 h-full">
            <Btn label="MC" onClick={memoryClear} variant="sci" />
            <Btn label="MR" onClick={memoryRecall} variant="sci" />
            <Btn label="M+" onClick={memoryAdd} variant="sci" />
            <Btn label="M−" onClick={memorySubtract} variant="sci" />
            <Btn label={<Delete size={14} />} onClick={backspace} variant="action" />

            <Btn label="sin" onClick={() => sciFunc('sin')} variant="sci" />
            <Btn label="cos" onClick={() => sciFunc('cos')} variant="sci" />
            <Btn label="tan" onClick={() => sciFunc('tan')} variant="sci" />
            <Btn label="(" onClick={() => inputDigit('(')} variant="sci" />
            <Btn label=")" onClick={() => inputDigit(')')} variant="sci" />

            <Btn label="x²" onClick={() => sciFunc('square')} variant="sci" />
            <Btn label="x³" onClick={() => sciFunc('cube')} variant="sci" />
            <Btn label="xʸ" onClick={() => performOp('^')} variant="sci" />
            <Btn label="AC" onClick={clear} variant="action" />
            <Btn label="÷" onClick={() => performOp('/')} variant="op" />

            <Btn label="√" onClick={() => sciFunc('sqrt')} variant="sci" />
            <Btn label="log" onClick={() => sciFunc('log')} variant="sci" />
            <Btn label="ln" onClick={() => sciFunc('ln')} variant="sci" />
            <Btn label="%" onClick={percentage} variant="sci" />
            <Btn label="×" onClick={() => performOp('*')} variant="op" />

            <Btn label="7" onClick={() => inputDigit('7')} />
            <Btn label="8" onClick={() => inputDigit('8')} />
            <Btn label="9" onClick={() => inputDigit('9')} />
            <Btn label="1/x" onClick={() => sciFunc('1/x')} variant="sci" />
            <Btn label="−" onClick={() => performOp('-')} variant="op" />

            <Btn label="4" onClick={() => inputDigit('4')} />
            <Btn label="5" onClick={() => inputDigit('5')} />
            <Btn label="6" onClick={() => inputDigit('6')} />
            <Btn label="n!" onClick={() => sciFunc('factorial')} variant="sci" />
            <Btn label="+" onClick={() => performOp('+')} variant="op" />

            <Btn label="1" onClick={() => inputDigit('1')} />
            <Btn label="2" onClick={() => inputDigit('2')} />
            <Btn label="3" onClick={() => inputDigit('3')} />
            <Btn label="π" onClick={() => sciFunc('pi')} variant="sci" />
            <Btn label="=" onClick={calculate} variant="eq" colSpan={1} className="row-span-2 h-full" />

            <Btn label="0" onClick={() => inputDigit('0')} colSpan={2} />
            <Btn label="." onClick={inputDecimal} />
            <Btn label="e" onClick={() => sciFunc('e')} variant="sci" />
          </div>
        )}
      </div>
    </AppContainer>
  );
};

export default Calculator;

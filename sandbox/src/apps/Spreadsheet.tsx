// ============================================================
// Spreadsheet — Grid with formulas, formatting, CSV export
// ============================================================

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Bold, Italic, Paintbrush, Download, Plus,
  Trash2, FileSpreadsheet,
} from 'lucide-react';

const COLS = Array.from({ length: 20 }, (_, i) => {
  let s = '';
  let n = i;
  while (n >= 0) { s = String.fromCharCode(65 + (n % 26)) + s; n = Math.floor(n / 26) - 1; }
  return s;
});
const ROWS = 50;

interface CellStyle {
  bold?: boolean;
  italic?: boolean;
  fontSize?: number;
  bgColor?: string;
  textColor?: string;
}

interface CellData {
  value: string;
  style?: CellStyle;
}

interface Sheet {
  id: string;
  name: string;
  cells: Record<string, CellData>;
}

const generateId = () => Math.random().toString(36).slice(2) + Date.now().toString(36);

const loadSheets = (): Sheet[] => {
  try {
    const saved = localStorage.getItem('dulus_spreadsheet');
    if (saved) return JSON.parse(saved);
  } catch { /* ignore */ }
  const sampleCells: Record<string, CellData> = {
    'A1': { value: 'Item' },
    'B1': { value: 'Q1' },
    'C1': { value: 'Q2' },
    'D1': { value: 'Q3' },
    'E1': { value: 'Total' },
    'A2': { value: 'Product A' },
    'B2': { value: '100' },
    'C2': { value: '150' },
    'D2': { value: '120' },
    'E2': { value: '=SUM(B2:D2)' },
    'A3': { value: 'Product B' },
    'B3': { value: '80' },
    'C3': { value: '90' },
    'D3': { value: '110' },
    'E3': { value: '=SUM(B3:D3)' },
    'A4': { value: 'Product C' },
    'B4': { value: '200' },
    'C4': { value: '180' },
    'D4': { value: '220' },
    'E4': { value: '=SUM(B4:D4)' },
    'E5': { value: '=SUM(E2:E4)' },
  };
  return [{ id: 'sheet1', name: 'Sheet1', cells: sampleCells }];
};

const Spreadsheet: React.FC = () => {
  const [sheets, setSheets] = useState<Sheet[]>(loadSheets);
  const [activeSheet, setActiveSheet] = useState(0);
  const [selectedCell, setSelectedCell] = useState<string | null>(null);
  const [editingCell, setEditingCell] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [selectedRange, setSelectedRange] = useState<string[]>([]);
  const cellRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const sheet = sheets[activeSheet];

  useEffect(() => {
    localStorage.setItem('dulus_spreadsheet', JSON.stringify(sheets));
  }, [sheets]);

  // Formula evaluation
  const evaluateCell = useCallback((cellId: string, visited = new Set<string>()): string => {
    if (visited.has(cellId)) return '#REF!';
    visited.add(cellId);

    const cell = sheet.cells[cellId];
    if (!cell) return '';
    const val = cell.value;
    if (!val.startsWith('=')) return val;

    const formula = val.slice(1).toUpperCase();

    // SUM, AVERAGE, MAX, MIN, COUNT
    const funcMatch = formula.match(/^(SUM|AVERAGE|AVG|MAX|MIN|COUNT)\(([A-Z]+\d+):([A-Z]+\d+)\)$/);
    if (funcMatch) {
      const [, func, start, end] = funcMatch;
      const values = getRangeValues(start, end);
      const nums = values.map(v => parseFloat(v)).filter(v => !isNaN(v));
      if (func === 'SUM') return String(nums.reduce((a, b) => a + b, 0));
      if (func === 'AVERAGE' || func === 'AVG') return nums.length ? String(nums.reduce((a, b) => a + b, 0) / nums.length) : '0';
      if (func === 'MAX') return nums.length ? String(Math.max(...nums)) : '0';
      if (func === 'MIN') return nums.length ? String(Math.min(...nums)) : '0';
      if (func === 'COUNT') return String(nums.length);
    }

    // Cell reference or simple expression
    try {
      // Replace cell references with their values
      let expr = formula;
      expr = expr.replace(/([A-Z]+\d+)/g, (match) => {
        if (match === cellId) return '0';
        const val = evaluateCell(match, new Set(visited));
        const num = parseFloat(val);
        return isNaN(num) ? '0' : String(num);
      });
      // eslint-disable-next-line no-eval
      const result = eval(expr);
      return String(Number(result.toFixed(4)));
    } catch {
      return '#VALUE!';
    }
  }, [sheet]);

  const getRangeValues = (start: string, end: string): string[] => {
    const startCol = start.match(/[A-Z]+/)?.[0] || 'A';
    const startRow = parseInt(start.match(/\d+/)?.[0] || '1');
    const endCol = end.match(/[A-Z]+/)?.[0] || 'A';
    const endRow = parseInt(end.match(/\d+/)?.[0] || '1');

    const startColIdx = COLS.indexOf(startCol);
    const endColIdx = COLS.indexOf(endCol);
    const values: string[] = [];

    for (let r = Math.min(startRow, endRow); r <= Math.max(startRow, endRow); r++) {
      for (let c = Math.min(startColIdx, endColIdx); c <= Math.max(startColIdx, endColIdx); c++) {
        const cellId = `${COLS[c]}${r}`;
        const cell = sheet.cells[cellId];
        if (cell) values.push(evaluateCell(cellId));
      }
    }
    return values;
  };

  const getCellId = (col: string, row: number) => `${col}${row}`;

  const setCellValue = (cellId: string, value: string) => {
    setSheets(prev => prev.map((s, i) => {
      if (i !== activeSheet) return s;
      return {
        ...s,
        cells: {
          ...s.cells,
          [cellId]: { ...s.cells[cellId], value },
        },
      };
    }));
  };

  const setCellStyle = (cellId: string, styleUpdate: Partial<CellStyle>) => {
    setSheets(prev => prev.map((s, i) => {
      if (i !== activeSheet) return s;
      const cell = s.cells[cellId] || { value: '' };
      return {
        ...s,
        cells: {
          ...s.cells,
          [cellId]: { ...cell, style: { ...cell.style, ...styleUpdate } },
        },
      };
    }));
  };

  const handleCellClick = (cellId: string, e: React.MouseEvent) => {
    if (e.shiftKey && selectedCell) {
      const range = getCellRange(selectedCell, cellId);
      setSelectedRange(range);
    } else {
      setSelectedCell(cellId);
      setSelectedRange([]);
    }
  };

  const handleCellDoubleClick = (cellId: string) => {
    const cell = sheet.cells[cellId];
    setEditValue(cell?.value || '');
    setEditingCell(cellId);
  };

  const handleEditSubmit = () => {
    if (editingCell) {
      setCellValue(editingCell, editValue);
      setEditingCell(null);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!selectedCell) return;
    const match = selectedCell.match(/([A-Z]+)(\d+)/);
    if (!match) return;

    if (editingCell) {
      if (e.key === 'Enter') { handleEditSubmit(); moveSelection(0, 1); }
      if (e.key === 'Escape') setEditingCell(null);
      return;
    }

    // Start editing
    if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
      setEditValue(e.key);
      setEditingCell(selectedCell);
      return;
    }

    if (e.key === 'Enter') { handleCellDoubleClick(selectedCell); return; }

    switch (e.key) {
      case 'ArrowUp': moveSelection(0, -1); break;
      case 'ArrowDown': moveSelection(0, 1); break;
      case 'ArrowLeft': moveSelection(-1, 0); break;
      case 'ArrowRight': moveSelection(1, 0); break;
      case 'Delete': setCellValue(selectedCell, ''); break;
    }
  };

  const moveSelection = (dc: number, dr: number) => {
    if (!selectedCell) return;
    const match = selectedCell.match(/([A-Z]+)(\d+)/);
    if (!match) return;
    const [, col, rowStr] = match;
    const row = parseInt(rowStr);
    const colIdx = COLS.indexOf(col);
    const newCol = COLS[Math.max(0, Math.min(COLS.length - 1, colIdx + dc))];
    const newRow = Math.max(1, Math.min(ROWS, row + dr));
    const newId = getCellId(newCol, newRow);
    setSelectedCell(newId);
    cellRefs.current[newId]?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  };

  const getCellRange = (start: string, end: string): string[] => {
    const sMatch = start.match(/([A-Z]+)(\d+)/);
    const eMatch = end.match(/([A-Z]+)(\d+)/);
    if (!sMatch || !eMatch) return [start, end];
    const [, sCol, sRow] = sMatch;
    const [, eCol, eRow] = eMatch;
    const sColIdx = COLS.indexOf(sCol);
    const eColIdx = COLS.indexOf(eCol);
    const cells: string[] = [];
    for (let r = Math.min(parseInt(sRow), parseInt(eRow)); r <= Math.max(parseInt(sRow), parseInt(eRow)); r++) {
      for (let c = Math.min(sColIdx, eColIdx); c <= Math.max(sColIdx, eColIdx); c++) {
        cells.push(`${COLS[c]}${r}`);
      }
    }
    return cells;
  };

  const exportCSV = () => {
    let csv = '';
    for (let r = 1; r <= ROWS; r++) {
      const row: string[] = [];
      for (let c = 0; c < COLS.length; c++) {
        const cellId = `${COLS[c]}${r}`;
        const val = evaluateCell(cellId);
        row.push(val.includes(',') ? `"${val}"` : val);
      }
      if (row.some(v => v)) csv += row.join(',') + '\n';
    }
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${sheet.name}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const addSheet = () => {
    const newSheet: Sheet = { id: generateId(), name: `Sheet${sheets.length + 1}`, cells: {} };
    setSheets(prev => [...prev, newSheet]);
    setActiveSheet(sheets.length);
  };

  const deleteSheet = (index: number) => {
    if (sheets.length <= 1) return;
    setSheets(prev => prev.filter((_, i) => i !== index));
    if (activeSheet >= index && activeSheet > 0) setActiveSheet(activeSheet - 1);
  };

  const getDisplayValue = (cellId: string) => {
    const cell = sheet.cells[cellId];
    if (!cell) return '';
    if (cell.value.startsWith('=')) return evaluateCell(cellId);
    return cell.value;
  };

  const currentCell = selectedCell ? sheet.cells[selectedCell] : null;
  const formulaBarValue = editingCell !== null ? editValue : (selectedCell ? (sheet.cells[selectedCell]?.value || '') : '');

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-window)' }} tabIndex={0} onKeyDown={handleKeyDown}>
      {/* Toolbar */}
      <div className="flex items-center gap-1 px-2 py-1.5 border-b shrink-0" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-titlebar)' }}>
        <button onClick={() => selectedCell && setCellStyle(selectedCell, { bold: !(currentCell?.style?.bold) })} className={`p-1.5 rounded hover:bg-[var(--bg-hover)] ${currentCell?.style?.bold ? 'text-[var(--accent-primary)]' : 'text-[var(--text-secondary)]'}`} title="Bold">
          <Bold size={13} />
        </button>
        <button onClick={() => selectedCell && setCellStyle(selectedCell, { italic: !(currentCell?.style?.italic) })} className={`p-1.5 rounded hover:bg-[var(--bg-hover)] ${currentCell?.style?.italic ? 'text-[var(--accent-primary)]' : 'text-[var(--text-secondary)]'}`} title="Italic">
          <Italic size={13} />
        </button>
        <div className="w-px h-4 mx-1" style={{ background: 'var(--border-subtle)' }} />
        <button onClick={() => selectedCell && setCellStyle(selectedCell, { bgColor: currentCell?.style?.bgColor ? undefined : 'rgba(124,77,255,0.2)' })} className="p-1.5 rounded hover:bg-[var(--bg-hover)] text-[var(--text-secondary)]" title="Background Color">
          <Paintbrush size={13} />
        </button>
        <div className="w-px h-4 mx-1" style={{ background: 'var(--border-subtle)' }} />
        <button onClick={exportCSV} className="flex items-center gap-1 px-2 py-1 rounded hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] text-xs">
          <Download size={12} /> CSV
        </button>
      </div>

      {/* Formula bar */}
      <div className="flex items-center gap-2 px-2 py-1.5 border-b shrink-0" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-titlebar)' }}>
        <div className="text-[10px] text-[var(--text-secondary)] px-2 py-0.5 rounded border shrink-0" style={{ borderColor: 'var(--border-default)', minWidth: 48, textAlign: 'center' }}>
          {selectedCell || ''}
        </div>
        <div className="flex-1 text-xs text-[var(--text-primary)] truncate px-2">
          {formulaBarValue}
        </div>
      </div>

      {/* Grid */}
      <div className="flex-1 overflow-auto custom-scrollbar relative">
        <div className="inline-block min-w-full">
          {/* Column headers */}
          <div className="flex sticky top-0 z-10" style={{ background: 'var(--bg-titlebar)' }}>
            <div className="w-10 h-7 shrink-0 border-r border-b" style={{ borderColor: 'var(--border-subtle)' }} />
            {COLS.map(col => (
              <div key={col} className="w-20 h-7 shrink-0 border-r border-b flex items-center justify-center text-[10px] text-[var(--text-secondary)] font-medium" style={{ borderColor: 'var(--border-subtle)' }}>
                {col}
              </div>
            ))}
          </div>

          {/* Rows */}
          {Array.from({ length: ROWS }, (_, ri) => {
            const row = ri + 1;
            return (
              <div key={row} className="flex">
                {/* Row header */}
                <div className="w-10 h-6 shrink-0 border-r border-b flex items-center justify-center text-[10px] text-[var(--text-secondary)] sticky left-0" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-titlebar)' }}>
                  {row}
                </div>
                {COLS.map(col => {
                  const cellId = `${col}${row}`;
                  const cell = sheet.cells[cellId];
                  const displayValue = getDisplayValue(cellId);
                  const isSelected = selectedCell === cellId || selectedRange.includes(cellId);
                  const isEditing = editingCell === cellId;

                  return (
                    <div
                      key={cellId}
                      ref={el => { cellRefs.current[cellId] = el; }}
                      onClick={e => handleCellClick(cellId, e)}
                      onDoubleClick={() => handleCellDoubleClick(cellId)}
                      className="w-20 h-6 shrink-0 border-r border-b relative"
                      style={{
                        borderColor: 'var(--border-subtle)',
                        background: isSelected ? 'var(--bg-selected)' : cell?.style?.bgColor || 'transparent',
                      }}
                    >
                      {isEditing ? (
                        <input
                          autoFocus
                          value={editValue}
                          onChange={e => setEditValue(e.target.value)}
                          onBlur={handleEditSubmit}
                          onKeyDown={e => {
                            if (e.key === 'Enter') { handleEditSubmit(); moveSelection(0, 1); }
                            if (e.key === 'Escape') setEditingCell(null);
                            if (e.key === 'Tab') { e.preventDefault(); handleEditSubmit(); moveSelection(1, 0); }
                          }}
                          className="absolute inset-0 w-full h-full px-1 text-xs outline-none text-[var(--text-primary)]"
                          style={{ background: 'var(--bg-window)', border: '2px solid var(--accent-primary)' }}
                        />
                      ) : (
                        <div
                          className="w-full h-full px-1 text-xs truncate flex items-center"
                          style={{
                            color: isSelected ? 'var(--accent-primary)' : (cell?.style?.textColor || 'var(--text-primary)'),
                            fontWeight: cell?.style?.bold ? 'bold' : 'normal',
                            fontStyle: cell?.style?.italic ? 'italic' : 'normal',
                            fontSize: cell?.style?.fontSize ? `${cell.style.fontSize}px` : '11px',
                            border: isSelected ? '2px solid var(--accent-primary)' : 'none',
                          }}
                        >
                          {displayValue}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>

      {/* Sheet tabs */}
      <div className="flex items-center gap-1 px-2 py-1 border-t shrink-0" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-titlebar)' }}>
        {sheets.map((s, i) => (
          <button
            key={s.id}
            onClick={() => setActiveSheet(i)}
            className="flex items-center gap-1 px-3 py-1 rounded-t text-xs transition-colors"
            style={{
              background: activeSheet === i ? 'var(--bg-window)' : 'transparent',
              color: activeSheet === i ? 'var(--accent-primary)' : 'var(--text-secondary)',
              borderBottom: activeSheet === i ? '2px solid var(--accent-primary)' : '2px solid transparent',
            }}
          >
            <FileSpreadsheet size={12} />
            {s.name}
            {sheets.length > 1 && (
              <button onClick={e => { e.stopPropagation(); deleteSheet(i); }} className="ml-1 text-[var(--text-disabled)] hover:text-[var(--accent-error)]">
                <Trash2 size={10} />
              </button>
            )}
          </button>
        ))}
        <button onClick={addSheet} className="p-1 rounded hover:bg-[var(--bg-hover)] text-[var(--text-secondary)]">
          <Plus size={14} />
        </button>
      </div>
    </div>
  );
};

export default Spreadsheet;

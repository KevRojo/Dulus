// ============================================================
// Regex Tester — Test, debug, and explain regular expressions
// ============================================================

import { useState, useCallback, useMemo } from 'react';
import {
  Copy, BookOpen,
  Replace, Flag, X,
} from 'lucide-react';

const FLAG_OPTIONS = [
  { key: 'g', label: 'g', desc: 'Global' },
  { key: 'i', label: 'i', desc: 'Ignore case' },
  { key: 'm', label: 'm', desc: 'Multiline' },
  { key: 's', label: 's', desc: 'DotAll' },
  { key: 'u', label: 'u', desc: 'Unicode' },
  { key: 'y', label: 'y', desc: 'Sticky' },
];

const MATCH_COLORS = [
  'rgba(255,235,59,0.35)',
  'rgba(76,175,80,0.35)',
  'rgba(33,150,243,0.35)',
  'rgba(156,39,176,0.35)',
  'rgba(255,152,0,0.35)',
  'rgba(0,150,136,0.35)',
  'rgba(233,30,99,0.35)',
  'rgba(63,81,181,0.35)',
];

const COMMON_PATTERNS = [
  { name: 'Email', pattern: '^[\\w.-]+@[\\w.-]+\\.\\w{2,}$', flags: '' },
  { name: 'URL', pattern: 'https?://(www\\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\\.[a-zA-Z0-9()]{1,6}\\b([-a-zA-Z0-9()@:%_+.~#?&/=]*)', flags: 'i' },
  { name: 'Phone (US)', pattern: '\\(?\\d{3}\\)?[-.\\s]?\\d{3}[-.\\s]?\\d{4}', flags: '' },
  { name: 'IPv4', pattern: '^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$', flags: '' },
  { name: 'Date (YYYY-MM-DD)', pattern: '^\\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\\d|3[01])$', flags: '' },
  { name: 'Credit Card', pattern: '^\\d{4}[\\s-]?\\d{4}[\\s-]?\\d{4}[\\s-]?\\d{4}$', flags: '' },
  { name: 'Hex Color', pattern: '^#(?:[0-9a-fA-F]{3}){1,2}$', flags: '' },
  { name: 'Username', pattern: '^[a-zA-Z0-9_]{3,16}$', flags: '' },
];

const QUICK_REFERENCE = [
  { char: '.', desc: 'Any character except newline' },
  { char: '\\d', desc: 'Digit (0-9)' },
  { char: '\\w', desc: 'Word character' },
  { char: '\\s', desc: 'Whitespace' },
  { char: '^', desc: 'Start of string' },
  { char: '$', desc: 'End of string' },
  { char: '*', desc: '0 or more' },
  { char: '+', desc: '1 or more' },
  { char: '?', desc: '0 or 1' },
  { char: '{n,m}', desc: 'Between n and m' },
  { char: '[abc]', desc: 'Character class' },
  { char: '(...)', desc: 'Capturing group' },
  { char: '|', desc: 'Alternation (OR)' },
  { char: '\\b', desc: 'Word boundary' },
];

function explainPattern(pattern: string): { part: string; meaning: string }[] {
  const explanations: { part: string; meaning: string }[] = [];
  const parts = pattern.split(/(\[.*?\]|\\.|\.|\*|\+|\?|\^|\$|\(\?[:=!]|\(|\)|\{|\}|\||\d+)/g).filter(Boolean);
  const meaningMap: Record<string, string> = {
    '.': 'Any character',
    '^': 'Start of string',
    '$': 'End of string',
    '\\d': 'Digit [0-9]',
    '\\w': 'Word character [a-zA-Z0-9_]',
    '\\s': 'Whitespace',
    '\\b': 'Word boundary',
    '*': 'Zero or more (greedy)',
    '+': 'One or more (greedy)',
    '?': 'Zero or one (optional)',
    '|': 'OR - alternation',
    '(': 'Start capturing group',
    ')': 'End capturing group',
    '{': 'Start quantifier',
    '}': 'End quantifier',
    '[': 'Start character class',
    ']': 'End character class',
  };

  for (const part of parts) {
    if (!part) continue;
    if (part.startsWith('[') && part.endsWith(']')) {
      explanations.push({ part, meaning: `Character class: ${part.slice(1, -1)}` });
    } else if (meaningMap[part]) {
      explanations.push({ part, meaning: meaningMap[part] });
    } else if (/^\\.$/.test(part)) {
      explanations.push({ part, meaning: `Escaped: ${part[1]}` });
    } else {
      explanations.push({ part, meaning: `Literal "${part}"` });
    }
  }
  return explanations;
}

interface MatchResult {
  text: string;
  index: number;
  length: number;
  groups: string[];
}

export default function RegexTester() {
  const [pattern, setPattern] = useState('');
  const [flags, setFlags] = useState<Set<string>>(new Set(['g']));
  const [testString, setTestString] = useState('');
  const [replaceText, setReplaceText] = useState('');
  const [showReplace, setShowReplace] = useState(false);
  const [showRef, setShowRef] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');

  const flagString = useMemo(() => Array.from(flags).join(''), [flags]);

  const toggleFlag = useCallback((key: string) => {
    setFlags((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const matches = useMemo((): MatchResult[] => {
    if (!pattern || !testString) return [];
    try {
      setError('');
      const regex = new RegExp(pattern, flagString);
      const results: MatchResult[] = [];

      if (flags.has('g')) {
        let m: RegExpExecArray | null;
        const localRegex = new RegExp(pattern, flagString);
        while ((m = localRegex.exec(testString)) !== null) {
          if (m.index === localRegex.lastIndex) localRegex.lastIndex++;
          results.push({
            text: m[0],
            index: m.index,
            length: m[0].length,
            groups: m.slice(1),
          });
        }
      } else {
        const m = regex.exec(testString);
        if (m) {
          results.push({
            text: m[0],
            index: m.index,
            length: m[0].length,
            groups: m.slice(1),
          });
        }
      }
      return results;
    } catch (e) {
      setError((e as Error).message);
      return [];
    }
  }, [pattern, testString, flags, flagString]);

  const highlightedText = useMemo(() => {
    if (!pattern || !testString || error) return testString;
    if (matches.length === 0) return testString;

    const parts: { text: string; color?: string }[] = [];
    let lastIndex = 0;

    for (let i = 0; i < matches.length; i++) {
      const m = matches[i];
      if (m.index > lastIndex) {
        parts.push({ text: testString.slice(lastIndex, m.index) });
      }
      parts.push({ text: m.text, color: MATCH_COLORS[i % MATCH_COLORS.length] });
      lastIndex = m.index + m.length;
    }

    if (lastIndex < testString.length) {
      parts.push({ text: testString.slice(lastIndex) });
    }

    return parts.map((p, i) =>
      p.color
        ? `<mark key=${i} style="background:${p.color};border-radius:2px;padding:0 1px">${p.text}</mark>`
        : p.text
    ).join('');
  }, [pattern, testString, matches, error]);

  const replacementResult = useMemo(() => {
    if (!pattern || !testString || !showReplace) return '';
    try {
      const regex = new RegExp(pattern, flagString);
      return testString.replace(regex, replaceText);
    } catch {
      return '';
    }
  }, [pattern, testString, replaceText, showReplace, flagString]);

  const explanations = useMemo(() => {
    if (!pattern) return [];
    return explainPattern(pattern);
  }, [pattern]);

  const applyPattern = useCallback((p: string, f: string) => {
    setPattern(p);
    setFlags(new Set(f.split('').filter(Boolean)));
  }, []);

  const copyMatches = useCallback(async () => {
    const text = matches.map((m, i) => `Match ${i + 1}: "${m.text}" at position ${m.index}`).join('\n');
    if (text) {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  }, [matches]);

  return (
    <div className="h-full flex flex-col overflow-hidden" style={{ background: 'var(--bg-window)' }}>
      {/* Pattern Area */}
      <div className="shrink-0 px-4 pt-3 pb-2" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>Regular Expression</span>
          <button onClick={() => setShowRef((v) => !v)} className="flex items-center gap-1 text-xs px-2 py-0.5 rounded hover:bg-[var(--bg-hover)] transition-colors" style={{ color: 'var(--text-secondary)' }}>
            <BookOpen size={12} /> Quick Ref
          </button>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-lg font-mono" style={{ color: 'var(--text-secondary)' }}>/</span>
          <input
            value={pattern}
            onChange={(e) => setPattern(e.target.value)}
            placeholder="Enter regex pattern..."
            className="flex-1 px-3 py-1.5 rounded outline-none text-sm"
            style={{
              background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)',
              fontFamily: "'JetBrains Mono', monospace",
            }}
            spellCheck={false}
          />
          <span className="text-lg font-mono" style={{ color: 'var(--text-secondary)' }}>/{flagString}</span>
        </div>
        {/* Flags */}
        <div className="flex items-center gap-2 mt-2">
          {FLAG_OPTIONS.map((f) => (
            <button
              key={f.key}
              onClick={() => toggleFlag(f.key)}
              className="flex items-center gap-1 px-2 py-0.5 rounded-full text-xs transition-all"
              style={{
                background: flags.has(f.key) ? 'var(--accent-primary)' : 'var(--bg-hover)',
                color: flags.has(f.key) ? 'white' : 'var(--text-secondary)',
                border: `1px solid ${flags.has(f.key) ? 'var(--accent-primary)' : 'var(--border-default)'}`,
              }}
              title={f.desc}
            >
              <Flag size={10} /> {f.label}
            </button>
          ))}
        </div>
        {error && (
          <div className="flex items-center gap-2 mt-2 px-2 py-1 rounded" style={{ background: 'rgba(244,67,54,0.1)' }}>
            <X size={14} className="text-red-500" />
            <span className="text-xs text-red-400">{error}</span>
          </div>
        )}
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Main area */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Test String */}
          <div className="flex-1 flex flex-col px-4 pt-3 pb-2" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
            <span className="text-xs font-semibold mb-1.5" style={{ color: 'var(--text-secondary)' }}>Test String</span>
            <div className="flex-1 relative">
              <div
                className="absolute inset-0 p-3 rounded text-sm whitespace-pre-wrap break-all overflow-auto custom-scrollbar"
                style={{
                  background: 'var(--bg-input)', color: 'var(--text-primary)',
                  border: '1px solid var(--border-default)', fontFamily: "'JetBrains Mono', monospace", fontSize: 13,
                }}
                dangerouslySetInnerHTML={{ __html: highlightedText || '<span style="color:var(--text-disabled)">Enter text to test against...</span>' }}
              />
              <textarea
                value={testString}
                onChange={(e) => setTestString(e.target.value)}
                className="absolute inset-0 w-full h-full p-3 rounded text-sm resize-none outline-none bg-transparent whitespace-pre-wrap break-all overflow-auto"
                style={{
                  color: 'transparent', caretColor: 'var(--text-primary)',
                  fontFamily: "'JetBrains Mono', monospace", fontSize: 13,
                }}
                spellCheck={false}
              />
            </div>
          </div>

          {/* Match count + Results */}
          <div className="shrink-0 px-4 py-2" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
                {matches.length} {matches.length === 1 ? 'match' : 'matches'} found
              </span>
              {matches.length > 0 && (
                <button onClick={copyMatches} className="flex items-center gap-1 text-xs px-2 py-0.5 rounded hover:bg-[var(--bg-hover)]">
                  <Copy size={12} /> {copied ? 'Copied!' : 'Copy matches'}
                </button>
              )}
              <button onClick={() => setShowReplace((v) => !v)} className="flex items-center gap-1 text-xs px-2 py-0.5 rounded hover:bg-[var(--bg-hover)]">
                <Replace size={12} /> Replace
              </button>
            </div>
          </div>

          {/* Replace section */}
          {showReplace && (
            <div className="shrink-0 px-4 py-2" style={{ borderBottom: '1px solid var(--border-subtle)', background: 'var(--bg-titlebar)' }}>
              <span className="text-xs font-semibold mb-1 block" style={{ color: 'var(--text-secondary)' }}>Replacement</span>
              <div className="flex gap-2">
                <input
                  value={replaceText}
                  onChange={(e) => setReplaceText(e.target.value)}
                  placeholder="Replacement text..."
                  className="flex-1 px-2 py-1 rounded text-xs outline-none"
                  style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }}
                />
              </div>
              {replacementResult && (
                <div className="mt-2 p-2 rounded text-xs break-all" style={{ background: 'var(--bg-input)', fontFamily: "'JetBrains Mono', monospace" }}>
                  {replacementResult}
                </div>
              )}
            </div>
          )}

          {/* Match details */}
          {matches.length > 0 && (
            <div className="flex-1 overflow-auto px-4 py-2 custom-scrollbar">
              {matches.map((m, i) => (
                <div
                  key={i}
                  className="flex flex-col p-2 rounded mb-1"
                  style={{ background: 'var(--bg-hover)' }}
                >
                  <div className="flex items-center gap-2">
                    <span
                      className="text-xs font-semibold px-1.5 py-0.5 rounded"
                      style={{ background: MATCH_COLORS[i % MATCH_COLORS.length] }}
                    >
                      Match {i + 1}
                    </span>
                    <span className="text-xs" style={{ color: 'var(--text-primary)', fontFamily: "'JetBrains Mono', monospace" }}>
                      &quot;{m.text}&quot;
                    </span>
                  </div>
                  <span className="text-xs mt-0.5" style={{ color: 'var(--text-disabled)' }}>
                    Position: {m.index}–{m.index + m.length}
                  </span>
                  {m.groups.length > 0 && m.groups.some(Boolean) && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {m.groups.map((g, gi) => g && (
                        <span key={gi} className="text-xs px-1 py-0.5 rounded" style={{ background: 'var(--bg-active)' }}>
                          Group {gi + 1}: &quot;{g}&quot;
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right sidebar */}
        {showRef && (
          <div className="shrink-0 overflow-y-auto custom-scrollbar p-3" style={{ width: 220, borderLeft: '1px solid var(--border-subtle)', background: 'var(--bg-window)' }}>
            {/* Common patterns */}
            <div className="mb-4">
              <span className="text-xs font-semibold block mb-2" style={{ color: 'var(--text-secondary)' }}>Common Patterns</span>
              <div className="flex flex-col gap-1">
                {COMMON_PATTERNS.map((p) => (
                  <button
                    key={p.name}
                    onClick={() => applyPattern(p.pattern, p.flags)}
                    className="text-left px-2 py-1 rounded text-xs hover:bg-[var(--bg-hover)] transition-colors"
                    style={{ color: 'var(--text-primary)' }}
                  >
                    <div className="font-medium">{p.name}</div>
                    <div className="truncate" style={{ color: 'var(--text-disabled)', fontFamily: "'JetBrains Mono', monospace", fontSize: 10 }}>
                      {p.pattern}
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Quick reference */}
            <div className="mb-4">
              <span className="text-xs font-semibold block mb-2" style={{ color: 'var(--text-secondary)' }}>Quick Reference</span>
              <div className="flex flex-col gap-0.5">
                {QUICK_REFERENCE.map((r) => (
                  <div
                    key={r.char}
                    className="flex items-center justify-between px-2 py-1 rounded hover:bg-[var(--bg-hover)] cursor-pointer"
                    onClick={() => setPattern((prev) => prev + r.char)}
                  >
                    <code className="text-xs font-mono" style={{ color: 'var(--accent-primary)' }}>{r.char}</code>
                    <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{r.desc}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Pattern explanation */}
            {explanations.length > 0 && (
              <div>
                <span className="text-xs font-semibold block mb-2" style={{ color: 'var(--text-secondary)' }}>Explanation</span>
                <div className="flex flex-col gap-0.5">
                  {explanations.map((exp, i) => (
                    <div key={i} className="flex items-start gap-1 px-2 py-1 rounded hover:bg-[var(--bg-hover)]">
                      <code className="text-xs font-mono shrink-0" style={{ color: 'var(--accent-primary)' }}>{exp.part}</code>
                      <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{exp.meaning}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

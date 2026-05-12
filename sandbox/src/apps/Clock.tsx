// ============================================================
// Clock — World Clock, Alarm, Timer, Stopwatch
// ============================================================

import { useState, useEffect, useRef } from 'react';
import {
  Clock, Globe, Bell, Timer, Play, Pause, RotateCcw,
  Plus, X, Trash2, Sun, Moon,
} from 'lucide-react';

type ClockTab = 'world' | 'alarm' | 'timer' | 'stopwatch';

interface WorldCity {
  id: string;
  name: string;
  country: string;
  timezone: string;
}

interface Alarm {
  id: string;
  hour: number;
  minute: number;
  label: string;
  repeat: boolean[]; // Sun-Sat
  enabled: boolean;
}

const MAJOR_CITIES: WorldCity[] = [
  { id: 'local', name: 'Local Time', country: '', timezone: Intl.DateTimeFormat().resolvedOptions().timeZone },
  { id: 'nyc', name: 'New York', country: 'USA', timezone: 'America/New_York' },
  { id: 'lon', name: 'London', country: 'UK', timezone: 'Europe/London' },
  { id: 'tok', name: 'Tokyo', country: 'Japan', timezone: 'Asia/Tokyo' },
  { id: 'par', name: 'Paris', country: 'France', timezone: 'Europe/Paris' },
  { id: 'syd', name: 'Sydney', country: 'Australia', timezone: 'Australia/Sydney' },
  { id: 'dub', name: 'Dubai', country: 'UAE', timezone: 'Asia/Dubai' },
  { id: 'sin', name: 'Singapore', country: 'Singapore', timezone: 'Asia/Singapore' },
  { id: 'lax', name: 'Los Angeles', country: 'USA', timezone: 'America/Los_Angeles' },
  { id: 'ber', name: 'Berlin', country: 'Germany', timezone: 'Europe/Berlin' },
];

const DAY_NAMES = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];

const generateId = () => Math.random().toString(36).slice(2) + Date.now().toString(36);

const loadCities = (): string[] => {
  try { return JSON.parse(localStorage.getItem('clock_cities') || '["local","nyc","lon","tok"]'); } catch { return ['local', 'nyc', 'lon', 'tok']; }
};

const loadAlarms = (): Alarm[] => {
  try { return JSON.parse(localStorage.getItem('clock_alarms') || '[]'); } catch { return []; }
};

const ClockApp: React.FC = () => {
  const [tab, setTab] = useState<ClockTab>('world');
  const [now, setNow] = useState(new Date());
  const [selectedCities, setSelectedCities] = useState<string[]>(loadCities);
  const [showAddCity, setShowAddCity] = useState(false);
  const [alarms, setAlarms] = useState<Alarm[]>(loadAlarms);
  const [showAddAlarm, setShowAddAlarm] = useState(false);

  // Timer state
  const [timerHours, setTimerHours] = useState(0);
  const [timerMinutes, setTimerMinutes] = useState(5);
  const [timerSeconds, setTimerSeconds] = useState(0);
  const [timerRunning, setTimerRunning] = useState(false);
  const [timerLeft, setTimerLeft] = useState(300);

  // Stopwatch state
  const [swRunning, setSwRunning] = useState(false);
  const [swElapsed, setSwElapsed] = useState(0);
  const [swLaps, setSwLaps] = useState<number[]>([]);

  // Alarm form
  const [alarmHour, setAlarmHour] = useState(8);
  const [alarmMinute, setAlarmMinute] = useState(0);
  const [alarmLabel, setAlarmLabel] = useState('');
  const [alarmRepeat, setAlarmRepeat] = useState<boolean[]>([false, false, false, false, false, false, false]);

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const swRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const swStartRef = useRef<number>(0);
  const swOffsetRef = useRef<number>(0);

  useEffect(() => {
    const interval = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    localStorage.setItem('clock_cities', JSON.stringify(selectedCities));
  }, [selectedCities]);

  useEffect(() => {
    localStorage.setItem('clock_alarms', JSON.stringify(alarms));
  }, [alarms]);

  // Timer logic
  useEffect(() => {
    if (timerRunning && timerLeft > 0) {
      timerRef.current = setInterval(() => {
        setTimerLeft(prev => {
          if (prev <= 1) {
            setTimerRunning(false);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [timerRunning, timerLeft]);

  // Stopwatch logic
  useEffect(() => {
    if (swRunning) {
      swStartRef.current = Date.now() - swOffsetRef.current;
      swRef.current = setInterval(() => {
        setSwElapsed(Date.now() - swStartRef.current);
      }, 10);
    }
    return () => { if (swRef.current) clearInterval(swRef.current); };
  }, [swRunning]);

  const formatTimeForZone = (date: Date, tz: string) => {
    return new Intl.DateTimeFormat('en-US', {
      hour: 'numeric', minute: '2-digit', second: '2-digit', hour12: true, timeZone: tz,
    }).format(date);
  };

  const formatDateForZone = (date: Date, tz: string) => {
    return new Intl.DateTimeFormat('en-US', {
      weekday: 'long', month: 'long', day: 'numeric', timeZone: tz,
    }).format(date);
  };

  const getHourForZone = (date: Date, tz: string): number => {
    return parseInt(new Intl.DateTimeFormat('en-US', { hour: 'numeric', hour12: false, timeZone: tz }).format(date));
  };

  const addCity = (cityId: string) => {
    if (!selectedCities.includes(cityId)) {
      setSelectedCities(prev => [...prev, cityId]);
    }
    setShowAddCity(false);
  };

  const removeCity = (cityId: string) => {
    setSelectedCities(prev => prev.filter(c => c !== cityId));
  };

  const addAlarm = () => {
    const alarm: Alarm = {
      id: generateId(),
      hour: alarmHour,
      minute: alarmMinute,
      label: alarmLabel || 'Alarm',
      repeat: [...alarmRepeat],
      enabled: true,
    };
    setAlarms(prev => [...prev, alarm]);
    setShowAddAlarm(false);
    setAlarmLabel('');
    setAlarmRepeat([false, false, false, false, false, false, false]);
  };

  const toggleAlarm = (id: string) => {
    setAlarms(prev => prev.map(a => a.id === id ? { ...a, enabled: !a.enabled } : a));
  };

  const deleteAlarm = (id: string) => {
    setAlarms(prev => prev.filter(a => a.id !== id));
  };

  const startTimer = () => {
    if (!timerRunning) {
      if (timerLeft === 0) setTimerLeft(timerHours * 3600 + timerMinutes * 60 + timerSeconds);
      setTimerRunning(true);
    }
  };

  const pauseTimer = () => setTimerRunning(false);

  const resetTimer = () => {
    setTimerRunning(false);
    setTimerLeft(timerHours * 3600 + timerMinutes * 60 + timerSeconds);
  };

  const startStopwatch = () => {
    if (!swRunning) {
      swOffsetRef.current = swElapsed;
      setSwRunning(true);
    }
  };

  const pauseStopwatch = () => {
    setSwRunning(false);
    swOffsetRef.current = swElapsed;
  };

  const resetStopwatch = () => {
    setSwRunning(false);
    setSwElapsed(0);
    swOffsetRef.current = 0;
    setSwLaps([]);
  };

  const lapStopwatch = () => {
    setSwLaps(prev => [...prev, swElapsed]);
  };

  const formatDuration = (ms: number) => {
    const totalSec = Math.floor(ms / 1000);
    const m = Math.floor(totalSec / 60);
    const s = totalSec % 60;
    const msVal = Math.floor((ms % 1000) / 10);
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(msVal).padStart(2, '0')}`;
  };

  const formatTimer = (seconds: number) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  };

  const timerTotal = timerHours * 3600 + timerMinutes * 60 + timerSeconds;
  const timerProgress = timerTotal > 0 ? ((timerTotal - timerLeft) / timerTotal) * 100 : 0;

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-window)' }}>
      {/* Tab bar */}
      <div className="flex items-center border-b shrink-0" style={{ borderColor: 'var(--border-subtle)' }}>
        {([
          { id: 'world' as ClockTab, label: 'World Clock', icon: <Globe size={14} /> },
          { id: 'alarm' as ClockTab, label: 'Alarm', icon: <Bell size={14} /> },
          { id: 'timer' as ClockTab, label: 'Timer', icon: <Timer size={14} /> },
          { id: 'stopwatch' as ClockTab, label: 'Stopwatch', icon: <Clock size={14} /> },
        ]).map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className="flex items-center gap-1.5 px-4 py-2.5 text-sm relative transition-colors"
            style={{ color: tab === t.id ? 'var(--accent-primary)' : 'var(--text-secondary)' }}
          >
            {t.icon}
            {t.label}
            {tab === t.id && (
              <div className="absolute bottom-0 left-4 right-4 h-0.5 rounded-full" style={{ background: 'var(--accent-primary)' }} />
            )}
          </button>
        ))}
      </div>

      {/* World Clock */}
      {tab === 'world' && (
        <div className="flex-1 overflow-y-auto custom-scrollbar p-4">
          {/* Local digital clock */}
          <div className="text-center mb-6">
            <div className="text-4xl font-light text-[var(--text-primary)]" style={{ fontVariantNumeric: 'tabular-nums' }}>
              {formatTimeForZone(now, Intl.DateTimeFormat().resolvedOptions().timeZone)}
            </div>
            <div className="text-sm text-[var(--text-secondary)] mt-1">
              {formatDateForZone(now, Intl.DateTimeFormat().resolvedOptions().timeZone)}
            </div>
          </div>

          {/* City list */}
          <div className="space-y-2">
            {selectedCities.map(cityId => {
              const city = MAJOR_CITIES.find(c => c.id === cityId);
              if (!city) return null;
              const hour = getHourForZone(now, city.timezone);
              const isNight = hour < 6 || hour >= 18;
              const cityTime = formatTimeForZone(now, city.timezone);
              return (
                <div key={cityId} className="flex items-center justify-between px-4 py-3 rounded-lg" style={{ background: 'var(--bg-titlebar)' }}>
                  <div className="flex items-center gap-3">
                    {isNight ? <Moon size={16} className="text-[var(--accent-primary)]" /> : <Sun size={16} className="text-[var(--accent-secondary)]" />}
                    <div>
                      <div className="text-sm font-medium text-[var(--text-primary)]">{city.name}</div>
                      <div className="text-[10px] text-[var(--text-secondary)]">{city.country}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-lg font-light text-[var(--text-primary)]">{cityTime}</span>
                    {cityId !== 'local' && (
                      <button onClick={() => removeCity(cityId)} className="text-[var(--text-secondary)] hover:text-[var(--accent-error)]">
                        <X size={14} />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Add city */}
          {!showAddCity ? (
            <button
              onClick={() => setShowAddCity(true)}
              className="flex items-center gap-2 mt-3 text-xs text-[var(--accent-primary)] hover:underline"
            >
              <Plus size={14} /> Add City
            </button>
          ) : (
            <div className="mt-3 space-y-1">
              {MAJOR_CITIES.filter(c => !selectedCities.includes(c.id)).map(city => (
                <button
                  key={city.id}
                  onClick={() => addCity(city.id)}
                  className="flex items-center justify-between w-full px-3 py-2 rounded-lg text-xs text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
                >
                  <span>{city.name}, {city.country}</span>
                  <Plus size={12} className="text-[var(--accent-primary)]" />
                </button>
              ))}
              <button onClick={() => setShowAddCity(false)} className="text-xs text-[var(--text-secondary)] mt-1">Cancel</button>
            </div>
          )}
        </div>
      )}

      {/* Alarm */}
      {tab === 'alarm' && (
        <div className="flex-1 overflow-y-auto custom-scrollbar p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">Alarms</h3>
            <button
              onClick={() => setShowAddAlarm(!showAddAlarm)}
              className="p-1.5 rounded-lg hover:bg-[var(--bg-hover)] text-[var(--accent-primary)]"
            >
              <Plus size={16} />
            </button>
          </div>

          {showAddAlarm && (
            <div className="rounded-lg p-4 mb-4" style={{ background: 'var(--bg-titlebar)' }}>
              <div className="flex items-center gap-2 mb-3">
                <input
                  type="number"
                  value={alarmHour}
                  onChange={e => setAlarmHour(Math.max(0, Math.min(23, Number(e.target.value))))}
                  className="w-16 h-10 text-center rounded text-lg text-[var(--text-primary)] outline-none"
                  style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)' }}
                />
                <span className="text-xl text-[var(--text-primary)]">:</span>
                <input
                  type="number"
                  value={String(alarmMinute).padStart(2, '0')}
                  onChange={e => setAlarmMinute(Math.max(0, Math.min(59, Number(e.target.value))))}
                  className="w-16 h-10 text-center rounded text-lg text-[var(--text-primary)] outline-none"
                  style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)' }}
                />
              </div>
              <input
                value={alarmLabel}
                onChange={e => setAlarmLabel(e.target.value)}
                placeholder="Label"
                className="w-full h-8 px-3 rounded text-xs text-[var(--text-primary)] outline-none mb-2 placeholder:text-[var(--text-disabled)]"
                style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)' }}
              />
              <div className="flex gap-1 mb-3">
                {DAY_NAMES.map((d, i) => (
                  <button
                    key={i}
                    onClick={() => setAlarmRepeat(prev => prev.map((v, j) => j === i ? !v : v))}
                    className="w-7 h-7 rounded-full text-[10px] font-medium transition-colors"
                    style={{
                      background: alarmRepeat[i] ? 'var(--accent-primary)' : 'var(--bg-input)',
                      color: alarmRepeat[i] ? 'white' : 'var(--text-secondary)',
                    }}
                  >
                    {d}
                  </button>
                ))}
              </div>
              <div className="flex gap-2">
                <button onClick={() => setShowAddAlarm(false)} className="px-3 py-1.5 rounded text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]">Cancel</button>
                <button onClick={addAlarm} className="px-4 py-1.5 rounded text-xs font-medium text-white" style={{ background: 'var(--accent-primary)' }}>Save</button>
              </div>
            </div>
          )}

          <div className="space-y-2">
            {alarms.map(alarm => (
              <div key={alarm.id} className="flex items-center justify-between px-4 py-3 rounded-lg" style={{ background: 'var(--bg-titlebar)' }}>
                <div>
                  <div className="text-2xl font-light text-[var(--text-primary)]">
                    {String(alarm.hour).padStart(2, '0')}:{String(alarm.minute).padStart(2, '0')}
                  </div>
                  <div className="text-xs text-[var(--text-secondary)]">{alarm.label}</div>
                  <div className="flex gap-0.5 mt-1">
                    {alarm.repeat.map((r, i) => (
                      <span key={i} className="text-[10px]" style={{ color: r ? 'var(--accent-primary)' : 'var(--text-disabled)' }}>{DAY_NAMES[i]}</span>
                    ))}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={() => toggleAlarm(alarm.id)} className="relative h-6 rounded-full transition-colors" style={{ width: 40, background: alarm.enabled ? 'var(--accent-primary)' : 'var(--border-default)' }}>
                    <div className="absolute top-0.5 w-5 h-5 bg-white rounded-full shadow-sm transition-all" style={{ left: alarm.enabled ? 18 : 2 }} />
                  </button>
                  <button onClick={() => deleteAlarm(alarm.id)} className="text-[var(--text-secondary)] hover:text-[var(--accent-error)]">
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Timer */}
      {tab === 'timer' && (
        <div className="flex-1 flex flex-col items-center justify-center p-4">
          {/* Circular progress */}
          <div className="relative w-48 h-48 mb-6">
            <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="45" fill="none" stroke="var(--border-subtle)" strokeWidth="4" />
              <circle
                cx="50" cy="50" r="45" fill="none"
                stroke="var(--accent-primary)"
                strokeWidth="4"
                strokeLinecap="round"
                strokeDasharray={`${2 * Math.PI * 45}`}
                strokeDashoffset={`${2 * Math.PI * 45 * (1 - timerProgress / 100)}`}
                className="transition-all duration-1000"
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-3xl font-light text-[var(--text-primary)]" style={{ fontVariantNumeric: 'tabular-nums' }}>
                {formatTimer(timerLeft)}
              </span>
            </div>
          </div>

          {/* Presets */}
          <div className="flex gap-1.5 mb-4 flex-wrap justify-center">
            {[1, 5, 10, 15, 25, 30].map(m => (
              <button
                key={m}
                onClick={() => { setTimerRunning(false); setTimerHours(0); setTimerMinutes(m); setTimerSeconds(0); setTimerLeft(m * 60); }}
                className="px-2.5 py-1 rounded text-[10px] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] transition-colors"
                style={{ border: '1px solid var(--border-default)' }}
              >
                {m}m
              </button>
            ))}
          </div>

          {/* Custom inputs */}
          <div className="flex items-center gap-2 mb-4">
            <div className="text-center">
              <input
                type="number"
                value={timerHours}
                onChange={e => { setTimerHours(Number(e.target.value)); if (!timerRunning) setTimerLeft(Number(e.target.value) * 3600 + timerMinutes * 60 + timerSeconds); }}
                className="w-14 h-10 text-center rounded text-sm text-[var(--text-primary)] outline-none"
                style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)' }}
              />
              <div className="text-[10px] text-[var(--text-secondary)]">HRS</div>
            </div>
            <span className="text-lg text-[var(--text-secondary)]">:</span>
            <div className="text-center">
              <input
                type="number"
                value={timerMinutes}
                onChange={e => { setTimerMinutes(Number(e.target.value)); if (!timerRunning) setTimerLeft(timerHours * 3600 + Number(e.target.value) * 60 + timerSeconds); }}
                className="w-14 h-10 text-center rounded text-sm text-[var(--text-primary)] outline-none"
                style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)' }}
              />
              <div className="text-[10px] text-[var(--text-secondary)]">MIN</div>
            </div>
            <span className="text-lg text-[var(--text-secondary)]">:</span>
            <div className="text-center">
              <input
                type="number"
                value={timerSeconds}
                onChange={e => { setTimerSeconds(Number(e.target.value)); if (!timerRunning) setTimerLeft(timerHours * 3600 + timerMinutes * 60 + Number(e.target.value)); }}
                className="w-14 h-10 text-center rounded text-sm text-[var(--text-primary)] outline-none"
                style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)' }}
              />
              <div className="text-[10px] text-[var(--text-secondary)]">SEC</div>
            </div>
          </div>

          {/* Controls */}
          <div className="flex gap-3">
            {!timerRunning ? (
              <button onClick={startTimer} className="flex items-center gap-2 px-6 py-2.5 rounded-lg text-sm font-medium text-white" style={{ background: 'var(--accent-success)' }}>
                <Play size={16} /> Start
              </button>
            ) : (
              <button onClick={pauseTimer} className="flex items-center gap-2 px-6 py-2.5 rounded-lg text-sm font-medium text-white" style={{ background: 'var(--accent-warning)' }}>
                <Pause size={16} /> Pause
              </button>
            )}
            <button onClick={resetTimer} className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]">
              <RotateCcw size={16} /> Reset
            </button>
          </div>
        </div>
      )}

      {/* Stopwatch */}
      {tab === 'stopwatch' && (
        <div className="flex-1 flex flex-col items-center p-4">
          <div className="text-5xl font-light text-[var(--text-primary)] mt-8 mb-6" style={{ fontVariantNumeric: 'tabular-nums' }}>
            {formatDuration(swElapsed)}
          </div>

          <div className="flex gap-3 mb-6">
            {!swRunning ? (
              <button onClick={startStopwatch} className="flex items-center gap-2 px-6 py-2.5 rounded-lg text-sm font-medium text-white" style={{ background: 'var(--accent-success)' }}>
                <Play size={16} /> Start
              </button>
            ) : (
              <button onClick={pauseStopwatch} className="flex items-center gap-2 px-6 py-2.5 rounded-lg text-sm font-medium text-white" style={{ background: 'var(--accent-warning)' }}>
                <Pause size={16} /> Stop
              </button>
            )}
            {swRunning && (
              <button onClick={lapStopwatch} className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm text-[var(--text-primary)] hover:bg-[var(--bg-hover)]">
                <Clock size={16} /> Lap
              </button>
            )}
            <button onClick={resetStopwatch} className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]">
              <RotateCcw size={16} /> Reset
            </button>
          </div>

          {/* Laps */}
          {swLaps.length > 0 && (
            <div className="w-full max-w-xs overflow-y-auto custom-scrollbar" style={{ maxHeight: 200 }}>
              <table className="w-full">
                <thead>
                  <tr className="text-[10px] text-[var(--text-secondary)] uppercase">
                    <th className="text-left py-1">Lap</th>
                    <th className="text-right py-1">Split</th>
                    <th className="text-right py-1">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {swLaps.map((lap, i) => (
                    <tr key={i} className="border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                      <td className="text-xs text-[var(--text-primary)] py-1.5">{i + 1}</td>
                      <td className="text-xs text-[var(--text-primary)] text-right py-1.5" style={{ fontVariantNumeric: 'tabular-nums' }}>
                        {formatDuration(i === 0 ? lap : lap - swLaps[i - 1])}
                      </td>
                      <td className="text-xs text-[var(--text-secondary)] text-right py-1.5" style={{ fontVariantNumeric: 'tabular-nums' }}>
                        {formatDuration(lap)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ClockApp;

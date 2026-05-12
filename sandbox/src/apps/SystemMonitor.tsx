// ============================================================
// System Monitor — Processes, Resources, and File Systems
// ============================================================

import { useState, useEffect, useMemo } from 'react';
import { Search, Activity, Cpu, HardDrive, Wifi, XCircle } from 'lucide-react';

type Tab = 'processes' | 'resources' | 'disks';

interface Process {
  pid: number;
  name: string;
  cpu: number;
  memory: number;
  status: 'running' | 'sleeping' | 'idle';
  user: string;
}

interface DiskInfo {
  device: string;
  directory: string;
  type: string;
  total: string;
  used: string;
  free: string;
  usedPercent: number;
}

const INITIAL_PROCESSES: Process[] = [
  { pid: 1, name: 'systemd', cpu: 0.1, memory: 12, status: 'running', user: 'root' },
  { pid: 412, name: 'Xorg', cpu: 2.3, memory: 45, status: 'running', user: 'root' },
  { pid: 623, name: 'gnome-shell', cpu: 5.1, memory: 128, status: 'running', user: 'user' },
  { pid: 701, name: 'gnome-terminal', cpu: 0.8, memory: 32, status: 'running', user: 'user' },
  { pid: 823, name: 'firefox', cpu: 8.5, memory: 256, status: 'running', user: 'user' },
  { pid: 912, name: 'nautilus', cpu: 1.2, memory: 48, status: 'sleeping', user: 'user' },
  { pid: 1023, name: 'node', cpu: 12.4, memory: 89, status: 'running', user: 'user' },
  { pid: 1101, name: 'code-oss', cpu: 15.2, memory: 312, status: 'running', user: 'user' },
  { pid: 1205, name: 'spotify', cpu: 3.1, memory: 78, status: 'sleeping', user: 'user' },
  { pid: 1301, name: 'dockerd', cpu: 1.5, memory: 156, status: 'running', user: 'root' },
  { pid: 1402, name: 'NetworkManager', cpu: 0.3, memory: 18, status: 'sleeping', user: 'root' },
  { pid: 1501, name: 'postgres', cpu: 0.6, memory: 64, status: 'sleeping', user: 'postgres' },
  { pid: 1603, name: 'redis-server', cpu: 0.2, memory: 8, status: 'sleeping', user: 'redis' },
  { pid: 1701, name: 'nginx', cpu: 0.1, memory: 5, status: 'sleeping', user: 'www-data' },
  { pid: 1802, name: 'Dulus OS-shell', cpu: 4.2, memory: 96, status: 'running', user: 'user' },
];

const DISKS: DiskInfo[] = [
  { device: '/dev/sda1', directory: '/', type: 'ext4', total: '256 GB', used: '89 GB', free: '167 GB', usedPercent: 35 },
  { device: '/dev/sda2', directory: '/home', type: 'ext4', total: '512 GB', used: '201 GB', free: '311 GB', usedPercent: 39 },
  { device: '/dev/sdb1', directory: '/mnt/data', type: 'ntfs', total: '1 TB', used: '654 GB', free: '346 GB', usedPercent: 65 },
];

const STATUS_COLORS: Record<string, string> = {
  running: 'var(--accent-success)',
  sleeping: 'var(--accent-info)',
  idle: 'var(--text-disabled)',
};

const LineChart: React.FC<{ data: number[]; color: string; maxValue?: number; fillColor?: string }> = ({ data, color, maxValue = 100, fillColor }) => {
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * 100;
    const y = 100 - (Math.min(v, maxValue) / maxValue) * 100;
    return `${x},${y}`;
  }).join(' ');

  const areaPoints = fillColor ? `0,100 ${points} 100,100` : '';

  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="w-full h-full">
      {fillColor && (
        <polygon points={areaPoints} fill={fillColor} />
      )}
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
};

const SystemMonitor: React.FC = () => {
  const [tab, setTab] = useState<Tab>('processes');
  const [processes, setProcesses] = useState<Process[]>(INITIAL_PROCESSES);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'cpu' | 'memory' | 'name' | 'pid'>('cpu');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [selectedPid, setSelectedPid] = useState<number | null>(null);

  // Resource history
  const [cpuHistory, setCpuHistory] = useState<number[]>(Array(60).fill(0));
  const [memHistory, setMemHistory] = useState<number[]>(Array(60).fill(0));
  const [netDownHistory, setNetDownHistory] = useState<number[]>(Array(60).fill(0));
  const [netUpHistory, setNetUpHistory] = useState<number[]>(Array(60).fill(0));

  // Simulate process updates every 2s
  useEffect(() => {
    const interval = setInterval(() => {
      setProcesses(prev => prev.map(p => ({
        ...p,
        cpu: Math.max(0, Math.min(100, p.cpu + (Math.random() - 0.5) * 5)),
        memory: Math.max(1, Math.min(512, p.memory + (Math.random() - 0.5) * 8)),
        status: Math.random() > 0.95 ? (p.status === 'running' ? 'sleeping' : 'running') : p.status,
      })));
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  // Simulate resource history every 1s
  useEffect(() => {
    const interval = setInterval(() => {
      const totalCpu = processes.reduce((sum, p) => sum + p.cpu, 0);
      const totalMem = processes.reduce((sum, p) => sum + p.memory, 0);
      const memPercent = (totalMem / 8192) * 100;

      setCpuHistory(prev => [...prev.slice(1), Math.min(100, totalCpu * 0.8)]);
      setMemHistory(prev => [...prev.slice(1), Math.min(100, memPercent)]);
      setNetDownHistory(prev => [...prev.slice(1), Math.random() * 12]);
      setNetUpHistory(prev => [...prev.slice(1), Math.random() * 3]);
    }, 1000);
    return () => clearInterval(interval);
  }, [processes]);

  const filteredProcesses = useMemo(() => {
    let filtered = processes.filter(p =>
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      String(p.pid).includes(searchQuery)
    );
    filtered.sort((a, b) => {
      const dir = sortDir === 'asc' ? 1 : -1;
      if (sortBy === 'name') return a.name.localeCompare(b.name) * dir;
      return ((a[sortBy] as number) - (b[sortBy] as number)) * dir;
    });
    return filtered;
  }, [processes, searchQuery, sortBy, sortDir]);

  const handleSort = (col: typeof sortBy) => {
    if (sortBy === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortBy(col); setSortDir('desc'); }
  };

  const endProcess = (pid: number) => {
    setProcesses(prev => prev.filter(p => p.pid !== pid));
    setSelectedPid(null);
  };

  const SortHeader: React.FC<{ label: string; col: typeof sortBy }> = ({ label, col }) => (
    <button
      onClick={() => handleSort(col)}
      className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
    >
      {label}
      {sortBy === col && <span className="text-[var(--accent-primary)]">{sortDir === 'asc' ? '↑' : '↓'}</span>}
    </button>
  );

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-window)' }}>
      {/* Tab bar */}
      <div className="flex items-center gap-0 border-b shrink-0" style={{ borderColor: 'var(--border-subtle)' }}>
        {(['processes', 'resources', 'disks'] as Tab[]).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className="flex items-center gap-1.5 px-4 py-2.5 text-sm capitalize transition-colors relative"
            style={{
              color: tab === t ? 'var(--accent-primary)' : 'var(--text-secondary)',
            }}
          >
            {t === 'processes' && <Activity size={14} />}
            {t === 'resources' && <Cpu size={14} />}
            {t === 'disks' && <HardDrive size={14} />}
            {t}
            {tab === t && (
              <div className="absolute bottom-0 left-4 right-4 h-0.5 rounded-full" style={{ background: 'var(--accent-primary)' }} />
            )}
          </button>
        ))}
      </div>

      {/* Processes tab */}
      {tab === 'processes' && (
        <div className="flex flex-col flex-1 overflow-hidden">
          {/* Toolbar */}
          <div className="flex items-center gap-2 px-3 py-2 border-b shrink-0" style={{ borderColor: 'var(--border-subtle)' }}>
            <div className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg" style={{ background: 'var(--bg-input)' }}>
              <Search size={14} className="text-[var(--text-secondary)]" />
              <input
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="Search processes..."
                className="flex-1 bg-transparent text-xs text-[var(--text-primary)] outline-none placeholder:text-[var(--text-disabled)] w-40"
              />
            </div>
            {selectedPid && (
              <button
                onClick={() => endProcess(selectedPid)}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium text-white"
                style={{ background: 'var(--accent-error)' }}
              >
                <XCircle size={14} /> End Process
              </button>
            )}
            <div className="flex-1" />
            <div className="text-xs text-[var(--text-secondary)]">{filteredProcesses.length} processes</div>
          </div>

          {/* Process table */}
          <div className="flex-1 overflow-auto custom-scrollbar">
            <table className="w-full">
              <thead className="sticky top-0" style={{ background: 'var(--bg-titlebar)' }}>
                <tr>
                  <th className="text-left px-3 py-2"><SortHeader label="Name" col="name" /></th>
                  <th className="text-left px-3 py-2"><SortHeader label="PID" col="pid" /></th>
                  <th className="text-left px-3 py-2"><SortHeader label="CPU%" col="cpu" /></th>
                  <th className="text-left px-3 py-2"><SortHeader label="Memory" col="memory" /></th>
                  <th className="text-left px-3 py-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Status</th>
                  <th className="text-left px-3 py-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">User</th>
                </tr>
              </thead>
              <tbody>
                {filteredProcesses.map(p => (
                  <tr
                    key={p.pid}
                    onClick={() => setSelectedPid(p.pid)}
                    className="cursor-pointer transition-colors"
                    style={{
                      background: selectedPid === p.pid ? 'var(--bg-selected)' : 'transparent',
                    }}
                    onMouseEnter={e => { if (selectedPid !== p.pid) e.currentTarget.style.background = 'var(--bg-hover)'; }}
                    onMouseLeave={e => { if (selectedPid !== p.pid) e.currentTarget.style.background = 'transparent'; }}
                  >
                    <td className="px-3 py-1.5 text-xs text-[var(--text-primary)] flex items-center gap-2">
                      <Activity size={12} style={{ color: STATUS_COLORS[p.status] }} />
                      {p.name}
                    </td>
                    <td className="px-3 py-1.5 text-xs text-[var(--text-secondary)]">{p.pid}</td>
                    <td className="px-3 py-1.5">
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--border-subtle)' }}>
                          <div
                            className="h-full rounded-full transition-all"
                            style={{
                              width: `${Math.min(p.cpu, 100)}%`,
                              background: p.cpu > 80 ? 'var(--accent-error)' : p.cpu > 50 ? 'var(--accent-warning)' : 'var(--accent-success)',
                            }}
                          />
                        </div>
                        <span className="text-xs text-[var(--text-primary)] w-10">{p.cpu.toFixed(1)}</span>
                      </div>
                    </td>
                    <td className="px-3 py-1.5 text-xs text-[var(--text-primary)]">{p.memory.toFixed(0)} MB</td>
                    <td className="px-3 py-1.5">
                      <span className="text-xs capitalize" style={{ color: STATUS_COLORS[p.status] }}>{p.status}</span>
                    </td>
                    <td className="px-3 py-1.5 text-xs text-[var(--text-secondary)]">{p.user}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Resources tab */}
      {tab === 'resources' && (
        <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4">
          {/* CPU */}
          <div className="rounded-lg p-3" style={{ background: 'var(--bg-titlebar)' }}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Cpu size={14} className="text-[var(--accent-primary)]" />
                <span className="text-sm font-semibold text-[var(--text-primary)]">CPU</span>
              </div>
              <span className="text-xl font-light text-[var(--text-primary)]">{cpuHistory[cpuHistory.length - 1].toFixed(1)}%</span>
            </div>
            <div className="h-28 w-full">
              <LineChart data={cpuHistory} color="var(--accent-primary)" fillColor="rgba(124,77,255,0.15)" />
            </div>
          </div>

          {/* Memory */}
          <div className="rounded-lg p-3" style={{ background: 'var(--bg-titlebar)' }}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <HardDrive size={14} className="text-[var(--accent-info)]" />
                <span className="text-sm font-semibold text-[var(--text-primary)]">Memory</span>
              </div>
              <span className="text-xl font-light text-[var(--text-primary)]">{memHistory[memHistory.length - 1].toFixed(1)}%</span>
            </div>
            <div className="h-28 w-full">
              <LineChart data={memHistory} color="var(--accent-info)" fillColor="rgba(33,150,243,0.15)" />
            </div>
            <div className="flex items-center gap-2 mt-2">
              <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: 'var(--border-subtle)' }}>
                <div className="h-full rounded-full" style={{ width: `${memHistory[memHistory.length - 1]}%`, background: 'var(--accent-info)' }} />
              </div>
              <span className="text-xs text-[var(--text-secondary)]">{memHistory[memHistory.length - 1].toFixed(1)}% of 8 GB</span>
            </div>
          </div>

          {/* Network */}
          <div className="rounded-lg p-3" style={{ background: 'var(--bg-titlebar)' }}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Wifi size={14} className="text-[var(--accent-success)]" />
                <span className="text-sm font-semibold text-[var(--text-primary)]">Network</span>
              </div>
              <div className="flex gap-4">
                <span className="text-xs text-[var(--text-secondary)]">↓ {(netDownHistory[netDownHistory.length - 1]).toFixed(1)} MB/s</span>
                <span className="text-xs text-[var(--text-secondary)]">↑ {(netUpHistory[netUpHistory.length - 1]).toFixed(1)} MB/s</span>
              </div>
            </div>
            <div className="h-28 w-full relative">
              <LineChart data={netDownHistory} color="var(--accent-info)" maxValue={15} />
              <div className="absolute inset-0">
                <LineChart data={netUpHistory} color="var(--accent-secondary)" maxValue={15} />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Disks tab */}
      {tab === 'disks' && (
        <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4">
          {DISKS.map(disk => (
            <div key={disk.device} className="rounded-lg p-4" style={{ background: 'var(--bg-titlebar)' }}>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <HardDrive size={14} className="text-[var(--accent-primary)]" />
                  <span className="text-sm font-semibold text-[var(--text-primary)]">{disk.directory}</span>
                  <span className="text-xs text-[var(--text-secondary)]">({disk.device} — {disk.type})</span>
                </div>
                <span className="text-xs text-[var(--text-secondary)]">{disk.used} / {disk.total}</span>
              </div>
              <div className="h-3 rounded-full overflow-hidden" style={{ background: 'var(--border-subtle)' }}>
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${disk.usedPercent}%`,
                    background: disk.usedPercent > 85 ? 'var(--accent-error)' : disk.usedPercent > 60 ? 'var(--accent-warning)' : 'var(--accent-success)',
                  }}
                />
              </div>
              <div className="flex items-center justify-between mt-2">
                <span className="text-xs text-[var(--text-secondary)]">{disk.free} free</span>
                <span className="text-xs font-medium" style={{ color: disk.usedPercent > 85 ? 'var(--accent-error)' : 'var(--text-primary)' }}>{disk.usedPercent}% used</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default SystemMonitor;

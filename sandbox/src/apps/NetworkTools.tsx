import { useState, useEffect, useRef, useCallback, type ReactElement } from 'react';
import {
  Wifi, Activity, Globe, Server, Search, Play, X, Loader2,
  CheckCircle, XCircle, HelpCircle
} from 'lucide-react';

type ToolTab = 'ping' | 'traceroute' | 'portscan' | 'dns';

interface PingResult {
  seq: number;
  bytes: number;
  time: number;
  ttl: number;
}

interface TraceHop {
  hop: number;
  host: string;
  ip: string;
  times: number[];
}

interface PortResult {
  port: number;
  service: string;
  status: 'open' | 'closed' | 'filtered';
}

interface DNSRecord {
  type: string;
  value: string;
  ttl: number;
}

const TABS: { id: ToolTab; label: string; icon: ReactElement }[] = [
  { id: 'ping', label: 'Ping', icon: <Activity size={14} /> },
  { id: 'traceroute', label: 'Traceroute', icon: <Globe size={14} /> },
  { id: 'portscan', label: 'Port Scan', icon: <Server size={14} /> },
  { id: 'dns', label: 'DNS Lookup', icon: <Search size={14} /> },
];

const COMMON_PORTS = [
  { port: 22, service: 'SSH' },
  { port: 80, service: 'HTTP' },
  { port: 443, service: 'HTTPS' },
  { port: 3306, service: 'MySQL' },
  { port: 5432, service: 'PostgreSQL' },
  { port: 8080, service: 'HTTP-Alt' },
  { port: 21, service: 'FTP' },
  { port: 25, service: 'SMTP' },
  { port: 53, service: 'DNS' },
  { port: 110, service: 'POP3' },
  { port: 143, service: 'IMAP' },
  { port: 3389, service: 'RDP' },
];

const generatePingResults = (host: string, count: number): PingResult[] => {
  const results: PingResult[] = [];
  for (let i = 0; i < count; i++) {
    const baseTime = 15 + Math.random() * 30;
    results.push({
      seq: i + 1,
      bytes: 64,
      time: parseFloat(baseTime.toFixed(2)),
      ttl: 56 + Math.floor(Math.random() * 8),
    });
  }
  return results;
};

const generateTraceroute = (host: string): TraceHop[] => {
  const hops: TraceHop[] = [];
  const ispNames = ['router.local', 'isp-core-1.net', 'isp-backbone-2.net', 'ix-exchange.net', 'tier1-provider.net', 'remote-isp.net', 'target-prefix.net'];
  for (let i = 1; i <= 15; i++) {
    const baseLatency = i * 3 + Math.random() * 8;
    const hostName = i < 15 ? `${ispNames[Math.min(i - 1, ispNames.length - 1)]}` : host || 'destination.host';
    hops.push({
      hop: i,
      host: hostName,
      ip: `192.168.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}`,
      times: [baseLatency, baseLatency + Math.random() * 3, baseLatency + Math.random() * 2].map(t => parseFloat(t.toFixed(2))),
    });
  }
  return hops;
};

const generatePortScan = (host: string): PortResult[] => {
  return COMMON_PORTS.map(cp => {
    const rand = Math.random();
    let status: 'open' | 'closed' | 'filtered';
    if (rand < 0.25) status = 'open';
    else if (rand < 0.7) status = 'closed';
    else status = 'filtered';
    return { port: cp.port, service: cp.service, status };
  });
};

const generateDNSRecords = (domain: string): DNSRecord[] => {
  if (!domain) return [];
  const cleanDomain = domain.replace(/^https?:\/\//, '').split('/')[0];
  return [
    { type: 'A', value: `${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}`, ttl: 300 },
    { type: 'A', value: `${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}`, ttl: 300 },
    { type: 'AAAA', value: `2606:2800:220:1:${Math.floor(Math.random() * 9999)}:${Math.floor(Math.random() * 9999)}:${Math.floor(Math.random() * 9999)}:${Math.floor(Math.random() * 9999)}`, ttl: 300 },
    { type: 'MX', value: `10 mail.${cleanDomain}.`, ttl: 3600 },
    { type: 'MX', value: `20 mail2.${cleanDomain}.`, ttl: 3600 },
    { type: 'NS', value: `ns1.${cleanDomain}.`, ttl: 86400 },
    { type: 'NS', value: `ns2.${cleanDomain}.`, ttl: 86400 },
    { type: 'TXT', value: '"v=spf1 include:_spf.${cleanDomain} ~all"', ttl: 3600 },
  ];
};

export default function NetworkTools() {
  const [activeTab, setActiveTab] = useState<ToolTab>('ping');
  const [target, setTarget] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [pingResults, setPingResults] = useState<PingResult[]>([]);
  const [pingSummary, setPingSummary] = useState('');
  const [traceResults, setTraceResults] = useState<TraceHop[]>([]);
  const [portResults, setPortResults] = useState<PortResult[]>([]);
  const [dnsResults, setDnsResults] = useState<DNSRecord[]>([]);
  const [liveOutput, setLiveOutput] = useState<string[]>([]);
  const outputEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => { outputEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [liveOutput]);

  const runPing = async () => {
    if (!target) return;
    setIsRunning(true);
    setPingResults([]);
    setLiveOutput([`PING ${target} (${target}) 56(84) bytes of data.`]);
    const results = generatePingResults(target, 8);
    for (let i = 0; i < results.length; i++) {
      await new Promise(r => setTimeout(r, 600 + Math.random() * 400));
      setPingResults(prev => [...prev, results[i]]);
      setLiveOutput(prev => [...prev, `64 bytes from ${target}: icmp_seq=${results[i].seq} ttl=${results[i].ttl} time=${results[i].time} ms`]);
    }
    const times = results.map(r => r.time);
    const min = Math.min(...times).toFixed(2);
    const avg = (times.reduce((a, b) => a + b, 0) / times.length).toFixed(2);
    const max = Math.max(...times).toFixed(2);
    setPingSummary(`--- ${target} ping statistics ---\n${results.length} packets transmitted, ${results.length} received, 0% packet loss\nrtt min/avg/max = ${min}/${avg}/${max} ms`);
    setLiveOutput(prev => [...prev, `--- ${target} ping statistics ---`, `${results.length} packets transmitted, ${results.length} received, 0% packet loss`, `rtt min/avg/max = ${min}/${avg}/${max} ms`]);
    setIsRunning(false);
  };

  const runTraceroute = async () => {
    if (!target) return;
    setIsRunning(true);
    setTraceResults([]);
    setLiveOutput([`traceroute to ${target}, 15 hops max`]);    const hops = generateTraceroute(target);
    for (let i = 0; i < hops.length; i++) {
      await new Promise(r => setTimeout(r, 400 + Math.random() * 600));
      setTraceResults(prev => [...prev, hops[i]]);
      const t = hops[i].times.map(tm => `${tm} ms`).join('  ');
      setLiveOutput(prev => [...prev, `${hops[i].hop.toString().padStart(2)}  ${hops[i].host} (${hops[i].ip})  ${t}`]);
    }
    setLiveOutput(prev => [...prev, `Trace complete.`]);
    setIsRunning(false);
  };

  const runPortScan = async () => {
    if (!target) return;
    setIsRunning(true);
    setPortResults([]);
    setLiveOutput([`Starting port scan on ${target}...`, `Scanning ${COMMON_PORTS.length} common ports...`]);
    const results = generatePortScan(target);
    for (let i = 0; i < results.length; i++) {
      await new Promise(r => setTimeout(r, 200 + Math.random() * 300));
      setPortResults(prev => [...prev, results[i]]);
      setLiveOutput(prev => [...prev, `Port ${results[i].port}/${results[i].service}: ${results[i].status.toUpperCase()}`]);
    }
    const open = results.filter(r => r.status === 'open').length;
    setLiveOutput(prev => [...prev, `Scan complete. ${open} open port(s) found.`]);
    setIsRunning(false);
  };

  const runDNS = async () => {
    if (!target) return;
    setIsRunning(true);
    setDnsResults([]);
    setLiveOutput([`Looking up DNS records for ${target}...`]);
    await new Promise(r => setTimeout(r, 800));
    const records = generateDNSRecords(target);
    setDnsResults(records);
    records.forEach(r => {
      setLiveOutput(prev => [...prev, `${target}.  ${r.ttl}  IN  ${r.type}  ${r.value}`]);
    });
    setIsRunning(false);
  };

  const runTool = () => {
    switch (activeTab) {
      case 'ping': runPing(); break;
      case 'traceroute': runTraceroute(); break;
      case 'portscan': runPortScan(); break;
      case 'dns': runDNS(); break;
    }
  };

  const clear = () => {
    setPingResults([]); setPingSummary(''); setTraceResults([]); setPortResults([]);
    setDnsResults([]); setLiveOutput([]);
  };

  const statusIcon = (status: string) => {
    if (status === 'open') return <CheckCircle size={12} style={{ color: 'var(--accent-success)' }} />;
    if (status === 'closed') return <XCircle size={12} style={{ color: 'var(--accent-error)' }} />;
    return <HelpCircle size={12} style={{ color: 'var(--accent-warning)' }} />;
  };

  const statusColor = (status: string) => {
    if (status === 'open') return 'var(--accent-success)';
    if (status === 'closed') return 'var(--accent-error)';
    return 'var(--accent-warning)';
  };

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-window)' }}>
      {/* Tabs */}
      <div className="flex items-center gap-0.5 px-2 pt-1 border-b" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-panel)' }}>
        {TABS.map(tab => (
          <button key={tab.id} onClick={() => { setActiveTab(tab.id); clear(); }} className="flex items-center gap-1 px-3 py-1.5 rounded-t-md text-xs transition-colors" style={{ background: activeTab === tab.id ? 'var(--bg-window)' : 'transparent', color: activeTab === tab.id ? 'var(--accent-primary)' : 'var(--text-secondary)', borderBottom: activeTab === tab.id ? '2px solid var(--accent-primary)' : '2px solid transparent' }}>
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {/* Input */}
      <div className="flex items-center gap-2 px-3 py-2 border-b" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-panel)' }}>
        <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{activeTab === 'dns' ? 'Domain:' : activeTab === 'portscan' ? 'IP/Host:' : 'Host:'}</span>
        <input value={target} onChange={e => setTarget(e.target.value)} onKeyDown={e => e.key === 'Enter' && !isRunning && runTool()} placeholder={activeTab === 'dns' ? 'example.com' : '8.8.8.8'} className="flex-1 px-2.5 py-1 rounded-md text-xs outline-none" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }} />
        <button onClick={runTool} disabled={isRunning || !target} className="flex items-center gap-1 px-3 py-1 rounded-md text-xs font-medium" style={{ background: 'var(--accent-primary)', color: '#fff', opacity: isRunning || !target ? 0.6 : 1 }}>
          {isRunning ? <Loader2 size={10} className="animate-spin" /> : <Play size={10} />} Start
        </button>
        <button onClick={clear} className="p-1 rounded" style={{ color: 'var(--text-secondary)' }}><X size={12} /></button>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-auto custom-scrollbar">
        {/* Live Output */}
        {liveOutput.length > 0 && (
          <div className="p-3 border-b font-mono text-xs" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-panel)', color: 'var(--text-secondary)', maxHeight: '150px', overflow: 'auto' }}>
            {liveOutput.map((line, i) => <div key={i} className="leading-4">{line}</div>)}
            <div ref={outputEndRef} />
          </div>
        )}

        {/* Ping results */}
        {activeTab === 'ping' && pingResults.length > 0 && (
          <div className="p-3">
            <table className="w-full text-xs">
              <thead><tr style={{ color: 'var(--text-secondary)' }}><th className="text-left py-1">Seq</th><th className="text-left">Bytes</th><th className="text-left">Time</th><th className="text-left">TTL</th></tr></thead>
              <tbody>
                {pingResults.map((r, i) => (
                  <tr key={i} style={{ color: 'var(--text-primary)', borderBottom: '1px solid var(--border-subtle)' }}>
                    <td className="py-1">{r.seq}</td><td>{r.bytes}</td><td style={{ color: r.time > 40 ? 'var(--accent-warning)' : 'var(--accent-success)' }}>{r.time} ms</td><td>{r.ttl}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {pingSummary && <pre className="mt-2 p-2 rounded text-xs font-mono" style={{ background: 'var(--bg-panel)', color: 'var(--text-secondary)' }}>{pingSummary}</pre>}
          </div>
        )}

        {/* Traceroute results */}
        {activeTab === 'traceroute' && traceResults.length > 0 && (
          <div className="p-3">
            <table className="w-full text-xs">
              <thead><tr style={{ color: 'var(--text-secondary)' }}><th className="text-left py-1 w-8">Hop</th><th className="text-left">Host</th><th className="text-left">IP</th><th className="text-left">Times</th></tr></thead>
              <tbody>
                {traceResults.map((h, i) => (
                  <tr key={i} style={{ color: 'var(--text-primary)', borderBottom: '1px solid var(--border-subtle)' }}>
                    <td className="py-1">{h.hop}</td>
                    <td>{h.host}</td>
                    <td style={{ color: 'var(--text-disabled)' }}>{h.ip}</td>
                    <td>{h.times.map(t => `${t}ms`).join('  ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Port scan results */}
        {activeTab === 'portscan' && portResults.length > 0 && (
          <div className="p-3">
            <div className="grid grid-cols-1 gap-1">
              {portResults.map((p, i) => (
                <div key={i} className="flex items-center gap-2 px-2 py-1.5 rounded text-xs" style={{ background: 'var(--bg-panel)' }}>
                  {statusIcon(p.status)}
                  <span className="w-10 font-mono" style={{ color: 'var(--text-primary)' }}>{p.port}</span>
                  <span className="w-20" style={{ color: 'var(--text-secondary)' }}>{p.service}</span>
                  <span className="capitalize font-medium" style={{ color: statusColor(p.status) }}>{p.status}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* DNS results */}
        {activeTab === 'dns' && dnsResults.length > 0 && (
          <div className="p-3">
            <table className="w-full text-xs">
              <thead><tr style={{ color: 'var(--text-secondary)' }}><th className="text-left py-1">Type</th><th className="text-left">Value</th><th className="text-left">TTL</th></tr></thead>
              <tbody>
                {dnsResults.map((r, i) => (
                  <tr key={i} style={{ color: 'var(--text-primary)', borderBottom: '1px solid var(--border-subtle)' }}>
                    <td className="py-1"><span className="px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-hover)', color: 'var(--accent-primary)' }}>{r.type}</span></td>
                    <td className="font-mono" style={{ color: 'var(--text-primary)' }}>{r.value}</td>
                    <td style={{ color: 'var(--text-disabled)' }}>{r.ttl}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

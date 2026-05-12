// ============================================================
// useSystemNetwork — Real network status via Navigator API
// ============================================================

import { useState, useEffect } from 'react';

export interface NetworkInfo {
  online: boolean;
  type: string;        // 'wifi' | '4g' | etc
  effectiveType: string; // '4g' | '3g' | '2g' | 'slow-2g'
  downlink: number;    // Mbps
  rtt: number;         // ms
  supported: boolean;
}

export function useSystemNetwork(): NetworkInfo {
  const [net, setNet] = useState<NetworkInfo>({
    online: navigator.onLine,
    type: 'unknown',
    effectiveType: '4g',
    downlink: 0,
    rtt: 0,
    supported: false,
  });

  useEffect(() => {
    const connection =
      // @ts-expect-error — Network Information API
      navigator.connection || navigator.mozConnection || navigator.webkitConnection;

    const updateNetwork = () => {
      setNet({
        online: navigator.onLine,
        type: connection?.type || 'unknown',
        effectiveType: connection?.effectiveType || '4g',
        downlink: connection?.downlink || 0,
        rtt: connection?.rtt || 0,
        supported: !!connection,
      });
    };

    updateNetwork();

    window.addEventListener('online', updateNetwork);
    window.addEventListener('offline', updateNetwork);
    connection?.addEventListener?.('change', updateNetwork);

    return () => {
      window.removeEventListener('online', updateNetwork);
      window.removeEventListener('offline', updateNetwork);
      connection?.removeEventListener?.('change', updateNetwork);
    };
  }, []);

  return net;
}

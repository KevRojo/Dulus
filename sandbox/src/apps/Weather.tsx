// ============================================================
// Weather — Real weather data via Open-Meteo (no API key needed)
// ============================================================

import { useState, useMemo, useCallback, useEffect, memo } from 'react';
import {
  Search, Sun, Cloud, CloudRain, CloudSnow, CloudLightning, Wind, Droplets,
  Thermometer, Eye, Gauge, Sunrise, Sunset, MapPin, RefreshCw, Loader2, CloudSun
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

// ---- Types ----
type WeatherCondition = 'sunny' | 'cloudy' | 'rainy' | 'snowy' | 'stormy' | 'partly-cloudy';

interface HourlyForecast {
  time: string;
  temp: number;
  condition: WeatherCondition;
}

interface DailyForecast {
  day: string;
  low: number;
  high: number;
  condition: WeatherCondition;
}

interface CityWeather {
  name: string;
  country: string;
  condition: WeatherCondition;
  temp: number;
  feelsLike: number;
  humidity: number;
  wind: number;
  pressure: number;
  visibility: number;
  uvIndex: number;
  sunrise: string;
  sunset: string;
  hourly: HourlyForecast[];
  daily: DailyForecast[];
}

interface GeoResult {
  id: number;
  name: string;
  latitude: number;
  longitude: number;
  country: string;
  admin1?: string;
}

// ---- WMO Weather Code Mapping ----
function wmoToCondition(code: number): WeatherCondition {
  if (code === 0 || code === 1) return 'sunny';
  if (code === 2) return 'partly-cloudy';
  if (code === 3 || code === 45 || code === 48) return 'cloudy';
  if ([51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82].includes(code)) return 'rainy';
  if ([71, 73, 75, 77, 85, 86].includes(code)) return 'snowy';
  if ([95, 96, 99].includes(code)) return 'stormy';
  return 'partly-cloudy';
}

function wmoToLabel(code: number): string {
  const labels: Record<number, string> = {
    0: 'Clear Sky', 1: 'Mainly Clear', 2: 'Partly Cloudy', 3: 'Overcast',
    45: 'Fog', 48: 'Depositing Rime Fog',
    51: 'Light Drizzle', 53: 'Moderate Drizzle', 55: 'Dense Drizzle',
    56: 'Light Freezing Drizzle', 57: 'Dense Freezing Drizzle',
    61: 'Slight Rain', 63: 'Moderate Rain', 65: 'Heavy Rain',
    66: 'Light Freezing Rain', 67: 'Heavy Freezing Rain',
    71: 'Slight Snow', 73: 'Moderate Snow', 75: 'Heavy Snow',
    77: 'Snow Grains', 80: 'Slight Rain Showers', 81: 'Moderate Rain Showers', 82: 'Violent Rain Showers',
    85: 'Slight Snow Showers', 86: 'Heavy Snow Showers',
    95: 'Thunderstorm', 96: 'Thunderstorm with Hail', 99: 'Heavy Thunderstorm with Hail',
  };
  return labels[code] || 'Unknown';
}

// ---- Weather Icon Mapping ----
const WeatherIcon = memo(function WeatherIcon({ condition, size = 24, className = '' }: { condition: WeatherCondition; size?: number; className?: string }) {
  const icons: Record<WeatherCondition, LucideIcon> = {
    sunny: Sun,
    cloudy: Cloud,
    'partly-cloudy': CloudSun,
    rainy: CloudRain,
    snowy: CloudSnow,
    stormy: CloudLightning,
  };
  const colors: Record<WeatherCondition, string> = {
    sunny: '#FFB300',
    cloudy: '#90A4AE',
    'partly-cloudy': '#64B5F6',
    rainy: '#42A5F5',
    snowy: '#B0BEC5',
    stormy: '#7E57C2',
  };
  const Icon = icons[condition];
  return <Icon size={size} className={className} style={{ color: colors[condition] }} />;
});

// ---- Mock Fallback Data ----
const CITY_DATA: Record<string, CityWeather> = {
  'san francisco': {
    name: 'San Francisco', country: 'United States', condition: 'partly-cloudy', temp: 18, feelsLike: 16,
    humidity: 72, wind: 19, pressure: 1015, visibility: 16, uvIndex: 5, sunrise: '6:42 AM', sunset: '7:28 PM',
    hourly: [
      { time: 'Now', temp: 18, condition: 'partly-cloudy' }, { time: '1PM', temp: 19, condition: 'sunny' },
      { time: '2PM', temp: 20, condition: 'sunny' }, { time: '3PM', temp: 20, condition: 'partly-cloudy' },
      { time: '4PM', temp: 19, condition: 'cloudy' }, { time: '5PM', temp: 18, condition: 'cloudy' },
      { time: '6PM', temp: 17, condition: 'partly-cloudy' }, { time: '7PM', temp: 16, condition: 'partly-cloudy' },
      { time: '8PM', temp: 15, condition: 'cloudy' }, { time: '9PM', temp: 14, condition: 'cloudy' },
      { time: '10PM', temp: 14, condition: 'rainy' }, { time: '11PM', temp: 13, condition: 'rainy' },
    ],
    daily: [
      { day: 'Today', low: 12, high: 20, condition: 'partly-cloudy' },
      { day: 'Tue', low: 11, high: 19, condition: 'sunny' },
      { day: 'Wed', low: 13, high: 21, condition: 'sunny' },
      { day: 'Thu', low: 14, high: 22, condition: 'partly-cloudy' },
      { day: 'Fri', low: 12, high: 18, condition: 'rainy' },
      { day: 'Sat', low: 11, high: 17, condition: 'cloudy' },
      { day: 'Sun', low: 10, high: 18, condition: 'sunny' },
    ],
  },
};

const CONDITION_LABELS: Record<WeatherCondition, string> = {
  sunny: 'Sunny',
  cloudy: 'Cloudy',
  'partly-cloudy': 'Partly Cloudy',
  rainy: 'Rainy',
  snowy: 'Snowy',
  stormy: 'Thunderstorm',
};

// ---- Open-Meteo API ----
async function fetchGeoCity(name: string): Promise<GeoResult | null> {
  try {
    const r = await fetch(
      `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(name)}&count=1&language=en&format=json`
    );
    if (!r.ok) return null;
    const data = await r.json();
    if (!data.results || data.results.length === 0) return null;
    const res = data.results[0];
    return {
      id: res.id,
      name: res.name,
      latitude: res.latitude,
      longitude: res.longitude,
      country: res.country || '',
      admin1: res.admin1 || '',
    };
  } catch {
    return null;
  }
}

async function fetchWeather(lat: number, lon: number): Promise<CityWeather | null> {
  try {
    const url =
      `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}` +
      `&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,pressure_msl,visibility` +
      `&hourly=temperature_2m,weather_code` +
      `&daily=weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset` +
      `&timezone=auto&forecast_days=7`;
    const r = await fetch(url);
    if (!r.ok) return null;
    const data = await r.json();

    const current = data.current;
    const hourly = data.hourly;
    const daily = data.daily;

    // Build hourly forecast: next 12 hours from now
    const nowHourIdx = Math.max(0, hourly.time.findIndex((t: string) => {
      const ht = new Date(t);
      const now = new Date();
      return ht >= now;
    }));
    const hourlyForecasts: HourlyForecast[] = [];
    for (let i = nowHourIdx; i < nowHourIdx + 12 && i < hourly.time.length; i++) {
      const t = hourly.time[i];
      const date = new Date(t);
      const isNow = i === nowHourIdx;
      hourlyForecasts.push({
        time: isNow ? 'Now' : date.toLocaleTimeString([], { hour: 'numeric', hour12: true }),
        temp: Math.round(hourly.temperature_2m[i]),
        condition: wmoToCondition(hourly.weather_code[i]),
      });
    }

    // Build daily forecast
    const dailyForecasts: DailyForecast[] = daily.time.map((t: string, i: number) => {
      const date = new Date(t);
      const today = new Date();
      const isToday = date.toDateString() === today.toDateString();
      return {
        day: isToday ? 'Today' : date.toLocaleDateString([], { weekday: 'short' }),
        low: Math.round(daily.temperature_2m_min[i]),
        high: Math.round(daily.temperature_2m_max[i]),
        condition: wmoToCondition(daily.weather_code[i]),
      };
    });

    // Format sunrise/sunset
    const fmtTime = (iso: string) => {
      const d = new Date(iso);
      return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', hour12: true });
    };

    return {
      name: '', // filled later
      country: '',
      condition: wmoToCondition(current.weather_code),
      temp: Math.round(current.temperature_2m),
      feelsLike: Math.round(current.apparent_temperature),
      humidity: current.relative_humidity_2m,
      wind: Math.round(current.wind_speed_10m),
      pressure: Math.round(current.pressure_msl),
      visibility: current.visibility ? Math.round(current.visibility / 1000) : 10,
      uvIndex: 0, // Open-Meteo UV requires separate param, skip for simplicity
      sunrise: fmtTime(daily.sunrise[0]),
      sunset: fmtTime(daily.sunset[0]),
      hourly: hourlyForecasts,
      daily: dailyForecasts,
    };
  } catch {
    return null;
  }
}

// ---- Main Weather Component ----
export default function Weather() {
  const [currentCity, setCurrentCity] = useState<CityWeather>(CITY_DATA['san francisco']);
  const [searchQuery, setSearchQuery] = useState('');
  const [unit, setUnit] = useState<'C' | 'F'>('C');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isRealData, setIsRealData] = useState(false);

  const convert = useCallback((temp: number) => (unit === 'C' ? temp : Math.round(temp * 9 / 5 + 32)), [unit]);

  const loadCity = useCallback(async (query: string) => {
    const q = query.trim();
    if (!q) return;
    setLoading(true);
    setError(null);

    // Try Open-Meteo first
    const geo = await fetchGeoCity(q);
    if (geo) {
      const weather = await fetchWeather(geo.latitude, geo.longitude);
      if (weather) {
        weather.name = geo.name;
        weather.country = geo.country;
        setCurrentCity(weather);
        setIsRealData(true);
        setLoading(false);
        setSearchQuery('');
        return;
      }
    }

    // Fallback to mock data
    const key = q.toLowerCase();
    if (CITY_DATA[key]) {
      setCurrentCity(CITY_DATA[key]);
      setIsRealData(false);
      setLoading(false);
      setSearchQuery('');
      return;
    }

    setError(`City "${q}" not found. Try: San Francisco, New York, London, Tokyo...`);
    setLoading(false);
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    loadCity(searchQuery);
  };

  const handleRefresh = () => {
    if (isRealData && currentCity.name) {
      loadCity(currentCity.name);
    } else {
      // Simulate refresh for mock data
      setLoading(true);
      setTimeout(() => setLoading(false), 800);
    }
  };

  // Load default city on mount with real data
  useEffect(() => {
    loadCity('San Francisco');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const tempRange = useMemo(() => {
    const allTemps = currentCity.daily.flatMap((d) => [d.low, d.high]);
    return { min: Math.min(...allTemps) - 2, max: Math.max(...allTemps) + 2 };
  }, [currentCity]);

  return (
    <div className="flex flex-col h-full custom-scrollbar overflow-y-auto" style={{ background: 'var(--bg-window)' }}>
      {/* Search Bar */}
      <div className="flex items-center gap-2 px-4 py-3 shrink-0" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
        <form onSubmit={handleSearch} className="flex-1 flex items-center gap-2 px-3" style={{ height: 36, borderRadius: 18, background: 'var(--bg-input)', border: '1px solid var(--border-default)' }}>
          <Search size={14} style={{ color: 'var(--text-disabled)', flexShrink: 0 }} />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search city..."
            className="flex-1 bg-transparent outline-none"
            style={{ color: 'var(--text-primary)', fontSize: '13px' }}
          />
        </form>
        <button
          onClick={() => setUnit(unit === 'C' ? 'F' : 'C')}
          className="flex items-center justify-center rounded-lg transition-all hover:bg-[var(--bg-hover)] font-semibold"
          style={{ width: 36, height: 36, fontSize: '13px', color: 'var(--accent-primary)' }}
        >
          °{unit}
        </button>
        <button
          onClick={handleRefresh}
          disabled={loading}
          className="flex items-center justify-center rounded-lg transition-all hover:bg-[var(--bg-hover)] disabled:opacity-50"
          style={{ width: 32, height: 32 }}
        >
          {loading ? <Loader2 size={14} className="animate-spin" style={{ color: 'var(--text-secondary)' }} /> : <RefreshCw size={14} style={{ color: 'var(--text-secondary)' }} />}
        </button>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="mx-4 mt-2 px-3 py-2 rounded-lg text-xs" style={{ background: 'var(--accent-error)15', color: 'var(--accent-error)', border: '1px solid var(--accent-error)30' }}>
          {error}
        </div>
      )}

      {/* Real Data Badge */}
      {isRealData && (
        <div className="mx-4 mt-2 flex items-center gap-1.5">
          <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ background: 'var(--accent-success)' }} />
          <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Live data via Open-Meteo</span>
        </div>
      )}

      {/* Current Weather */}
      <div className="flex flex-col items-center py-6">
        <div className="flex items-center gap-2 mb-1">
          <MapPin size={16} style={{ color: 'var(--accent-primary)' }} />
          <h1 style={{ fontSize: '20px', fontWeight: 600, color: 'var(--text-primary)' }}>{currentCity.name}</h1>
        </div>
        <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{currentCity.country}</span>

        <div className="flex items-center gap-4 mt-4">
          <div className="animate-float">
            <WeatherIcon condition={currentCity.condition} size={72} />
          </div>
          <div className="flex flex-col">
            <span style={{ fontSize: '48px', fontWeight: 300, color: 'var(--text-primary)', lineHeight: 1 }}>
              {convert(currentCity.temp)}°
            </span>
            <span style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>{CONDITION_LABELS[currentCity.condition]}</span>
          </div>
        </div>

        {/* Details Grid */}
        <div className="grid grid-cols-4 gap-3 w-full px-6 mt-5" style={{ maxWidth: 400 }}>
          <DetailItem icon={Thermometer} label="Feels Like" value={`${convert(currentCity.feelsLike)}°`} />
          <DetailItem icon={Droplets} label="Humidity" value={`${currentCity.humidity}%`} />
          <DetailItem icon={Wind} label="Wind" value={`${currentCity.wind} km/h`} />
          <DetailItem icon={Sun} label="UV Index" value={`${currentCity.uvIndex || '-'}`} />
        </div>

        <div className="grid grid-cols-2 gap-3 w-full px-6 mt-3" style={{ maxWidth: 400 }}>
          <DetailItem icon={Gauge} label="Pressure" value={`${currentCity.pressure} hPa`} />
          <DetailItem icon={Eye} label="Visibility" value={`${currentCity.visibility} km`} />
        </div>
      </div>

      {/* Hourly Forecast */}
      <div className="px-4 py-3" style={{ borderTop: '1px solid var(--border-subtle)' }}>
        <h3 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '10px' }}>Hourly Forecast</h3>
        <div className="flex gap-2 overflow-x-auto custom-scrollbar pb-1">
          {currentCity.hourly.map((h, i) => (
            <div
              key={i}
              className="flex flex-col items-center gap-1 py-2 px-2 rounded-lg shrink-0"
              style={{ width: 56, background: i === 0 ? 'var(--bg-selected)' : 'transparent' }}
            >
              <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{h.time}</span>
              <WeatherIcon condition={h.condition} size={24} />
              <span style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)' }}>{convert(h.temp)}°</span>
            </div>
          ))}
        </div>
      </div>

      {/* 7-Day Forecast */}
      <div className="px-4 py-3 flex-1" style={{ borderTop: '1px solid var(--border-subtle)' }}>
        <h3 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '10px' }}>7-Day Forecast</h3>
        <div className="flex flex-col gap-1">
          {currentCity.daily.map((day, i) => (
            <div key={i} className="flex items-center gap-3 px-2 py-2" style={{ height: 44, borderBottom: '1px solid var(--border-subtle)' }}>
              <span className="w-12 shrink-0" style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)' }}>{day.day}</span>
              <WeatherIcon condition={day.condition} size={22} />
              <span className="w-8 text-right shrink-0" style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{convert(day.low)}°</span>
              <div className="flex-1 relative" style={{ height: 4, background: 'var(--border-subtle)', borderRadius: 2 }}>
                <div
                  className="absolute h-full rounded-full"
                  style={{
                    left: `${((day.low - tempRange.min) / (tempRange.max - tempRange.min)) * 100}%`,
                    right: `${100 - ((day.high - tempRange.min) / (tempRange.max - tempRange.min)) * 100}%`,
                    background: 'linear-gradient(90deg, var(--accent-primary), var(--accent-secondary))',
                  }}
                />
              </div>
              <span className="w-8 text-right shrink-0" style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-primary)' }}>{convert(day.high)}°</span>
            </div>
          ))}
        </div>
      </div>

      {/* Sunrise/Sunset */}
      <div className="px-4 py-3" style={{ borderTop: '1px solid var(--border-subtle)' }}>
        <div className="flex items-center justify-around">
          <div className="flex items-center gap-2">
            <Sunrise size={20} style={{ color: 'var(--accent-secondary)' }} />
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Sunrise</div>
              <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)' }}>{currentCity.sunrise}</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Sunset size={20} style={{ color: 'var(--accent-secondary)' }} />
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Sunset</div>
              <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)' }}>{currentCity.sunset}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---- Detail Item Component ----
function DetailItem({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) {
  return (
    <div className="flex flex-col items-center gap-1 py-2 rounded-lg" style={{ background: 'var(--bg-titlebar)' }}>
      <Icon size={16} style={{ color: 'var(--text-secondary)' }} />
      <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-primary)' }}>{value}</span>
      <span style={{ fontSize: '10px', color: 'var(--text-disabled)' }}>{label}</span>
    </div>
  );
}

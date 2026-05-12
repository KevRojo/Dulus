// ============================================================
// Weather — City search with realistic mock weather data
// ============================================================

import { useState, useMemo, useCallback, memo } from 'react';
import {
  Search, Sun, Cloud, CloudRain, CloudSnow, CloudLightning, Wind, Droplets, Thermometer, Eye, Gauge, Sunrise, Sunset, MapPin, RefreshCw
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

// ---- Types ----
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

type WeatherCondition = 'sunny' | 'cloudy' | 'rainy' | 'snowy' | 'stormy' | 'partly-cloudy';

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

// ---- Weather Icon Mapping ----
const WeatherIcon = memo(function WeatherIcon({ condition, size = 24, className = '' }: { condition: WeatherCondition; size?: number; className?: string }) {
  const icons: Record<WeatherCondition, LucideIcon> = {
    sunny: Sun,
    cloudy: Cloud,
    'partly-cloudy': Cloud,
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

// ---- Mock Weather Data ----
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
  'new york': {
    name: 'New York', country: 'United States', condition: 'sunny', temp: 24, feelsLike: 26,
    humidity: 55, wind: 12, pressure: 1020, visibility: 20, uvIndex: 7, sunrise: '5:55 AM', sunset: '8:12 PM',
    hourly: [
      { time: 'Now', temp: 24, condition: 'sunny' }, { time: '1PM', temp: 25, condition: 'sunny' },
      { time: '2PM', temp: 26, condition: 'sunny' }, { time: '3PM', temp: 26, condition: 'sunny' },
      { time: '4PM', temp: 25, condition: 'partly-cloudy' }, { time: '5PM', temp: 24, condition: 'partly-cloudy' },
      { time: '6PM', temp: 23, condition: 'partly-cloudy' }, { time: '7PM', temp: 22, condition: 'cloudy' },
      { time: '8PM', temp: 21, condition: 'cloudy' }, { time: '9PM', temp: 20, condition: 'cloudy' },
      { time: '10PM', temp: 19, condition: 'partly-cloudy' }, { time: '11PM', temp: 18, condition: 'partly-cloudy' },
    ],
    daily: [
      { day: 'Today', low: 18, high: 26, condition: 'sunny' },
      { day: 'Tue', low: 19, high: 27, condition: 'sunny' },
      { day: 'Wed', low: 20, high: 28, condition: 'partly-cloudy' },
      { day: 'Thu', low: 18, high: 25, condition: 'rainy' },
      { day: 'Fri', low: 17, high: 24, condition: 'stormy' },
      { day: 'Sat', low: 16, high: 23, condition: 'cloudy' },
      { day: 'Sun', low: 18, high: 25, condition: 'sunny' },
    ],
  },
  'london': {
    name: 'London', country: 'United Kingdom', condition: 'rainy', temp: 14, feelsLike: 12,
    humidity: 82, wind: 16, pressure: 1008, visibility: 10, uvIndex: 2, sunrise: '5:18 AM', sunset: '9:12 PM',
    hourly: [
      { time: 'Now', temp: 14, condition: 'rainy' }, { time: '1PM', temp: 14, condition: 'rainy' },
      { time: '2PM', temp: 15, condition: 'cloudy' }, { time: '3PM', temp: 15, condition: 'cloudy' },
      { time: '4PM', temp: 14, condition: 'rainy' }, { time: '5PM', temp: 13, condition: 'rainy' },
      { time: '6PM', temp: 13, condition: 'cloudy' }, { time: '7PM', temp: 12, condition: 'cloudy' },
      { time: '8PM', temp: 12, condition: 'cloudy' }, { time: '9PM', temp: 11, condition: 'rainy' },
      { time: '10PM', temp: 11, condition: 'rainy' }, { time: '11PM', temp: 10, condition: 'rainy' },
    ],
    daily: [
      { day: 'Today', low: 9, high: 15, condition: 'rainy' },
      { day: 'Tue', low: 8, high: 14, condition: 'cloudy' },
      { day: 'Wed', low: 9, high: 16, condition: 'partly-cloudy' },
      { day: 'Thu', low: 10, high: 17, condition: 'sunny' },
      { day: 'Fri', low: 11, high: 18, condition: 'partly-cloudy' },
      { day: 'Sat', low: 10, high: 16, condition: 'rainy' },
      { day: 'Sun', low: 9, high: 15, condition: 'cloudy' },
    ],
  },
  'tokyo': {
    name: 'Tokyo', country: 'Japan', condition: 'cloudy', temp: 22, feelsLike: 24,
    humidity: 68, wind: 8, pressure: 1012, visibility: 18, uvIndex: 4, sunrise: '4:38 AM', sunset: '6:52 PM',
    hourly: [
      { time: 'Now', temp: 22, condition: 'cloudy' }, { time: '1PM', temp: 23, condition: 'partly-cloudy' },
      { time: '2PM', temp: 24, condition: 'partly-cloudy' }, { time: '3PM', temp: 24, condition: 'sunny' },
      { time: '4PM', temp: 23, condition: 'sunny' }, { time: '5PM', temp: 22, condition: 'partly-cloudy' },
      { time: '6PM', temp: 21, condition: 'cloudy' }, { time: '7PM', temp: 20, condition: 'cloudy' },
      { time: '8PM', temp: 19, condition: 'cloudy' }, { time: '9PM', temp: 19, condition: 'cloudy' },
      { time: '10PM', temp: 18, condition: 'rainy' }, { time: '11PM', temp: 18, condition: 'rainy' },
    ],
    daily: [
      { day: 'Today', low: 17, high: 24, condition: 'cloudy' },
      { day: 'Tue', low: 18, high: 25, condition: 'partly-cloudy' },
      { day: 'Wed', low: 19, high: 26, condition: 'sunny' },
      { day: 'Thu', low: 20, high: 27, condition: 'sunny' },
      { day: 'Fri', low: 18, high: 24, condition: 'rainy' },
      { day: 'Sat', low: 17, high: 23, condition: 'rainy' },
      { day: 'Sun', low: 18, high: 25, condition: 'partly-cloudy' },
    ],
  },
  'sydney': {
    name: 'Sydney', country: 'Australia', condition: 'sunny', temp: 26, feelsLike: 28,
    humidity: 60, wind: 22, pressure: 1018, visibility: 22, uvIndex: 9, sunrise: '6:05 AM', sunset: '8:08 PM',
    hourly: [
      { time: 'Now', temp: 26, condition: 'sunny' }, { time: '1PM', temp: 27, condition: 'sunny' },
      { time: '2PM', temp: 28, condition: 'sunny' }, { time: '3PM', temp: 28, condition: 'sunny' },
      { time: '4PM', temp: 27, condition: 'sunny' }, { time: '5PM', temp: 26, condition: 'partly-cloudy' },
      { time: '6PM', temp: 25, condition: 'partly-cloudy' }, { time: '7PM', temp: 24, condition: 'partly-cloudy' },
      { time: '8PM', temp: 23, condition: 'cloudy' }, { time: '9PM', temp: 22, condition: 'cloudy' },
      { time: '10PM', temp: 21, condition: 'cloudy' }, { time: '11PM', temp: 21, condition: 'cloudy' },
    ],
    daily: [
      { day: 'Today', low: 19, high: 28, condition: 'sunny' },
      { day: 'Tue', low: 20, high: 29, condition: 'sunny' },
      { day: 'Wed', low: 21, high: 30, condition: 'partly-cloudy' },
      { day: 'Thu', low: 20, high: 27, condition: 'rainy' },
      { day: 'Fri', low: 19, high: 26, condition: 'stormy' },
      { day: 'Sat', low: 18, high: 25, condition: 'cloudy' },
      { day: 'Sun', low: 19, high: 27, condition: 'sunny' },
    ],
  },
  'paris': {
    name: 'Paris', country: 'France', condition: 'partly-cloudy', temp: 19, feelsLike: 18,
    humidity: 65, wind: 10, pressure: 1016, visibility: 14, uvIndex: 4, sunrise: '5:52 AM', sunset: '9:35 PM',
    hourly: [
      { time: 'Now', temp: 19, condition: 'partly-cloudy' }, { time: '1PM', temp: 20, condition: 'sunny' },
      { time: '2PM', temp: 21, condition: 'sunny' }, { time: '3PM', temp: 21, condition: 'partly-cloudy' },
      { time: '4PM', temp: 20, condition: 'partly-cloudy' }, { time: '5PM', temp: 19, condition: 'cloudy' },
      { time: '6PM', temp: 18, condition: 'cloudy' }, { time: '7PM', temp: 17, condition: 'partly-cloudy' },
      { time: '8PM', temp: 16, condition: 'partly-cloudy' }, { time: '9PM', temp: 15, condition: 'cloudy' },
      { time: '10PM', temp: 15, condition: 'cloudy' }, { time: '11PM', temp: 14, condition: 'cloudy' },
    ],
    daily: [
      { day: 'Today', low: 12, high: 21, condition: 'partly-cloudy' },
      { day: 'Tue', low: 13, high: 22, condition: 'sunny' },
      { day: 'Wed', low: 14, high: 23, condition: 'sunny' },
      { day: 'Thu', low: 12, high: 20, condition: 'rainy' },
      { day: 'Fri', low: 11, high: 19, condition: 'cloudy' },
      { day: 'Sat', low: 12, high: 21, condition: 'partly-cloudy' },
      { day: 'Sun', low: 13, high: 22, condition: 'sunny' },
    ],
  },
  'dubai': {
    name: 'Dubai', country: 'UAE', condition: 'sunny', temp: 38, feelsLike: 42,
    humidity: 45, wind: 14, pressure: 1005, visibility: 18, uvIndex: 11, sunrise: '5:35 AM', sunset: '7:10 PM',
    hourly: [
      { time: 'Now', temp: 38, condition: 'sunny' }, { time: '1PM', temp: 39, condition: 'sunny' },
      { time: '2PM', temp: 40, condition: 'sunny' }, { time: '3PM', temp: 40, condition: 'sunny' },
      { time: '4PM', temp: 39, condition: 'sunny' }, { time: '5PM', temp: 38, condition: 'sunny' },
      { time: '6PM', temp: 36, condition: 'sunny' }, { time: '7PM', temp: 34, condition: 'sunny' },
      { time: '8PM', temp: 32, condition: 'partly-cloudy' }, { time: '9PM', temp: 31, condition: 'partly-cloudy' },
      { time: '10PM', temp: 30, condition: 'partly-cloudy' }, { time: '11PM', temp: 29, condition: 'cloudy' },
    ],
    daily: [
      { day: 'Today', low: 28, high: 40, condition: 'sunny' },
      { day: 'Tue', low: 29, high: 41, condition: 'sunny' },
      { day: 'Wed', low: 30, high: 42, condition: 'sunny' },
      { day: 'Thu', low: 29, high: 41, condition: 'sunny' },
      { day: 'Fri', low: 28, high: 40, condition: 'sunny' },
      { day: 'Sat', low: 28, high: 39, condition: 'partly-cloudy' },
      { day: 'Sun', low: 27, high: 39, condition: 'sunny' },
    ],
  },
  'singapore': {
    name: 'Singapore', country: 'Singapore', condition: 'stormy', temp: 31, feelsLike: 38,
    humidity: 85, wind: 6, pressure: 1009, visibility: 8, uvIndex: 6, sunrise: '6:55 AM', sunset: '7:10 PM',
    hourly: [
      { time: 'Now', temp: 31, condition: 'stormy' }, { time: '1PM', temp: 30, condition: 'stormy' },
      { time: '2PM', temp: 30, condition: 'rainy' }, { time: '3PM', temp: 29, condition: 'rainy' },
      { time: '4PM', temp: 29, condition: 'rainy' }, { time: '5PM', temp: 29, condition: 'cloudy' },
      { time: '6PM', temp: 28, condition: 'cloudy' }, { time: '7PM', temp: 28, condition: 'cloudy' },
      { time: '8PM', temp: 27, condition: 'cloudy' }, { time: '9PM', temp: 27, condition: 'cloudy' },
      { time: '10PM', temp: 27, condition: 'rainy' }, { time: '11PM', temp: 26, condition: 'rainy' },
    ],
    daily: [
      { day: 'Today', low: 25, high: 32, condition: 'stormy' },
      { day: 'Tue', low: 25, high: 31, condition: 'rainy' },
      { day: 'Wed', low: 26, high: 32, condition: 'rainy' },
      { day: 'Thu', low: 25, high: 31, condition: 'cloudy' },
      { day: 'Fri', low: 25, high: 32, condition: 'partly-cloudy' },
      { day: 'Sat', low: 26, high: 33, condition: 'sunny' },
      { day: 'Sun', low: 26, high: 32, condition: 'stormy' },
    ],
  },
  'berlin': {
    name: 'Berlin', country: 'Germany', condition: 'cloudy', temp: 16, feelsLike: 14,
    humidity: 70, wind: 18, pressure: 1014, visibility: 12, uvIndex: 3, sunrise: '4:58 AM', sunset: '9:25 PM',
    hourly: [
      { time: 'Now', temp: 16, condition: 'cloudy' }, { time: '1PM', temp: 17, condition: 'partly-cloudy' },
      { time: '2PM', temp: 18, condition: 'partly-cloudy' }, { time: '3PM', temp: 18, condition: 'sunny' },
      { time: '4PM', temp: 17, condition: 'sunny' }, { time: '5PM', temp: 16, condition: 'partly-cloudy' },
      { time: '6PM', temp: 15, condition: 'cloudy' }, { time: '7PM', temp: 14, condition: 'cloudy' },
      { time: '8PM', temp: 14, condition: 'cloudy' }, { time: '9PM', temp: 13, condition: 'rainy' },
      { time: '10PM', temp: 12, condition: 'rainy' }, { time: '11PM', temp: 12, condition: 'cloudy' },
    ],
    daily: [
      { day: 'Today', low: 10, high: 18, condition: 'cloudy' },
      { day: 'Tue', low: 11, high: 19, condition: 'partly-cloudy' },
      { day: 'Wed', low: 12, high: 20, condition: 'sunny' },
      { day: 'Thu', low: 13, high: 21, condition: 'sunny' },
      { day: 'Fri', low: 11, high: 19, condition: 'rainy' },
      { day: 'Sat', low: 10, high: 18, condition: 'cloudy' },
      { day: 'Sun', low: 11, high: 19, condition: 'partly-cloudy' },
    ],
  },
  'mumbai': {
    name: 'Mumbai', country: 'India', condition: 'rainy', temp: 29, feelsLike: 34,
    humidity: 88, wind: 11, pressure: 1006, visibility: 6, uvIndex: 3, sunrise: '6:08 AM', sunset: '7:18 PM',
    hourly: [
      { time: 'Now', temp: 29, condition: 'rainy' }, { time: '1PM', temp: 29, condition: 'rainy' },
      { time: '2PM', temp: 28, condition: 'stormy' }, { time: '3PM', temp: 28, condition: 'rainy' },
      { time: '4PM', temp: 28, condition: 'rainy' }, { time: '5PM', temp: 27, condition: 'rainy' },
      { time: '6PM', temp: 27, condition: 'cloudy' }, { time: '7PM', temp: 27, condition: 'cloudy' },
      { time: '8PM', temp: 26, condition: 'cloudy' }, { time: '9PM', temp: 26, condition: 'cloudy' },
      { time: '10PM', temp: 26, condition: 'rainy' }, { time: '11PM', temp: 25, condition: 'rainy' },
    ],
    daily: [
      { day: 'Today', low: 24, high: 30, condition: 'rainy' },
      { day: 'Tue', low: 24, high: 29, condition: 'stormy' },
      { day: 'Wed', low: 24, high: 30, condition: 'rainy' },
      { day: 'Thu', low: 25, high: 31, condition: 'cloudy' },
      { day: 'Fri', low: 25, high: 31, condition: 'partly-cloudy' },
      { day: 'Sat', low: 24, high: 30, condition: 'rainy' },
      { day: 'Sun', low: 24, high: 29, condition: 'rainy' },
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

// ---- Main Weather Component ----
export default function Weather() {
  const [currentCity, setCurrentCity] = useState<CityWeather>(CITY_DATA['san francisco']);
  const [searchQuery, setSearchQuery] = useState('');
  const [unit, setUnit] = useState<'C' | 'F'>('C');

  const convert = useCallback((temp: number) => unit === 'C' ? temp : Math.round(temp * 9 / 5 + 32), [unit]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const key = searchQuery.toLowerCase().trim();
    if (CITY_DATA[key]) {
      setCurrentCity(CITY_DATA[key]);
      setSearchQuery('');
    }
  };

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
        <button className="flex items-center justify-center rounded-lg transition-all hover:bg-[var(--bg-hover)]" style={{ width: 32, height: 32 }}>
          <RefreshCw size={14} style={{ color: 'var(--text-secondary)' }} />
        </button>
      </div>

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
          <DetailItem icon={Sun} label="UV Index" value={`${currentCity.uvIndex}`} />
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

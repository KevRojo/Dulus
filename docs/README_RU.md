<div align="center">

<img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/dulus-bird.png" alt="Dulus — Пальмовый ткач" width="280">

<h1>DULUS</h1>

<h3>Ваш AI Компаньон. Не Чатбот. Друг, Который Летит Рядом.</h3>

<p>
  <strong>Используйте передовой ИИ без ключа API. $0. Без карты. Без подписки.</strong>
</p>

<p>
  <a href="https://pypi.org/project/dulus/"><img src="https://img.shields.io/pypi/v/dulus.svg?style=flat-square&color=ff6b1f&labelColor=07070a&label=pypi" alt="PyPI"/></a>
  <a href="https://pypi.org/project/dulus/"><img src="https://static.pepy.tech/badge/dulus?style=flat-square" alt="Загрузки"/></a>
  <img src="https://img.shields.io/badge/python-3.11+-ff6b1f?style=flat-square&labelColor=07070a" alt="Python"/>
  <img src="https://img.shields.io/badge/лицензия-GPLv3-ff6b1f?style=flat-square&labelColor=07070a" alt="Лицензия"/>
  <img src="https://img.shields.io/badge/провайдеры-100%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="Провайдеры"/>
  <img src="https://img.shields.io/badge/инструменты-30%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="Инструменты"/>
  <img src="https://img.shields.io/badge/тесты-263%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="Тесты"/>
  <a href="https://x.com/KevRojo"><img src="https://img.shields.io/badge/x-%40KevRojo-ff6b1f?style=flat-square&labelColor=07070a&logo=x" alt="X"/></a>
</p>

<p>
  <a href="#быстрый-старт"><b>Быстрый Старт</b></a> ·
  <a href="#функции"><b>Функции</b></a> ·
  <a href="#провайдеры"><b>Провайдеры</b></a> ·
  <a href="#архитектура"><b>Архитектура</b></a> ·
</p>

</div>

---

> Назван в честь **Пальмового ткача** (*Dulus dominicus*), национальной птицы Доминиканской Республики — символ свободы, стойкости и совместного полета. Dulus — это не чатбот. Это ваш компаньон, ваш друг, ваш AI-партнер, который летит рядом.

---

## Почему Dulus?

| | Закрытые Экосистемы | Сложные Фреймворки | **Dulus** |
|---|---|---|---|
| **Время настройки** | Часы + одобрения | Дни конфигурации | **30 секунд** |
| **Начальная стоимость** | $$$ + ключи API | $$$ + инфраструктура | **$0** |
| **Привязка к провайдеру** | Один провайдер | Один провайдер | **100+ провайдеров** |
| **Кодовая база** | Черный ящик | 100K+ строк | **~56K строк собственного Python-кода** |
| **Голос** | Только облако | Не включено | **Офлайн Whisper** |
| **Память** | Только контекст | Вручную | **Семантическая MemPalace** |

**Проблема:** Современные ИИ-агенты либо привязаны к одному провайдеру, либо требуют докторской степени в ML-инжиниринге для настройки. И все хотят вашу кредитную карту до того, как вы сможете их попробовать.

**Решение:** Dulus. Автономный Python-агент, подключающийся к любой модели — от бесплатных браузерных сессий до 100+ платных провайдеров через LiteLLM и локальных моделей на вашем собственном оборудовании. ~56K строк собственного Python-кода. Без шага сборки. Без ограничений.

---

## Быстрый Старт

### Установка за 30 Секунд

```bash
pip install dulus && dulus
```

Вот и все. При первом запуске Dulus открывает браузер, захватывает **гостевую сессию Gemini** (без входа, без ключа API, без карты), и вы общаетесь с передовым ИИ менее чем за 30 секунд.

### Установщик One-liner (рекомендуется)

```bash
curl -fsSL https://raw.githubusercontent.com/KevRojo/Dulus/main/install.sh | bash
```

### Docker (без локальной настройки)

```bash
curl -fsSLO https://raw.githubusercontent.com/KevRojo/Dulus/main/docker-compose.yml
curl -fsSLO https://raw.githubusercontent.com/KevRojo/Dulus/main/.env.example
mv .env.example .env
docker compose up -d
```

---

## Функции

| Функция | Описание |
|---|---|
| Мультипровайдер | 11 нативных + 100+ через LiteLLM |
| Ноль Ключа API | Захват бесплатных браузерных сессий |
| 30+ Встроенных Инструментов | Файлы, shell, веб, OCR, голос и др. |
| Авто-Адаптер | Установка любого Python-репо как плагина |
| MemPalace | Семантическая память на ChromaDB |
| Голос I/O | Офлайн STT через Whisper. Мультидвижок TTS |
| Субагенты | Типизированные агенты в изолированных git worktree —— Стая |
| Круглый Стол | Мультимодельные дебаты |
| Sandbox OS | Мини-ОС в браузере с 58 приложениями |
| Telegram Мост | Запуск Dulus с телефона |
| MCP Поддержка | Model Context Protocol |
| Мозговой Штурм | Совет экспертов ИИ |
| SSJ Режим | 10 цепочек рабочих процессов |
| Контрольные Точки | Снапшот и откат любого хода |
| Сжатие Контекста | Автосжатие длинных сессий |
| Локальный OCR | Извлечение текста из изображений без токенов зрения |
| Мультиязычность | Команда `/lang` — 34 ISO-кода |
| Composio | 1,000+ SaaS-интеграций |
| WebBridge | Автоматизация браузера через Playwright |

---

## Провайдеры

### Бесплатные (Без Ключа API)

| Провайдер | Модели | Настройка |
|---|---|---|
| **Gemini Guest** | gemini-2.0-flash | Открыть браузер → ввести "привет" → готово |
| **Claude.ai** | claude-sonnet-4-6 | Ваша существующая сессия claude.ai |
| **Kimi.com** | kimi-k2.5 | Ваша существующая сессия kimi.com |
| **Qwen** | qwen-max, qwen-plus | Ваша существующая сессия qwen.ai |
| **DeepSeek** | deepseek-chat | Ваша существующая сессия deepseek |
| **NVIDIA NIM** | 14 моделей, по 40 RPM каждая | Бесплатная регистрация на build.nvidia.com |
| **Ollama** | Любая локальная модель | `ollama pull qwen2.5-coder` |

### Cloud API (Требуется Ключ API)

| Провайдер | Модели | Переменная Окружения |
|---|---|---|
| Anthropic | claude-opus-4-6, claude-sonnet-4-6 | `ANTHROPIC_API_KEY` |
| OpenAI | gpt-4o, gpt-4o-mini, o3-mini | `OPENAI_API_KEY` |
| Google | gemini-2.5-pro, gemini-2.0-flash | `GEMINI_API_KEY` |
| DeepSeek | deepseek-chat, deepseek-reasoner | `DEEPSEEK_API_KEY` |
| Qwen | qwen-max, qwen-plus, qwq-32b | `DASHSCOPE_API_KEY` |
| Kimi | moonshot-v1-8k/32k/128k, kimi-k2.5 | `MOONSHOT_API_KEY` |
| LiteLLM | 100+ бэкендов через один шлюз | Ключ конкретного бэкенда |

---

## Архитектура

```
Ввод Пользователя
    |
    v
dulus.py —— REPL, слэш-команды, голос, Telegram, GUI
    |
    ├── agent.py —— Мультитуровой цикл, ворота разрешений, управление
    |       |
    |       ├── providers.py —— Мультипровайдерный стриминг
    |       ├── tool_registry.py —— Система плагинов
    |       ├── tools.py —— 30+ встроенных инструментов
    |       ├── compaction.py —— Управление окном контекста
    |       ├── governance.py —— Управление бюджетом/разрешениями
    |       └── multi_agent/ —— Субагенты (Стая)
    |
    ├── context.py —— Конструктор системного промпта
    |       └── memory/ —— MemPalace семантическая память
    |
    ├── skill/ —— Система навыков
    ├── checkpoint/ —— Снапшоты + откат
    ├── plugin/ —— Система Авто-Адаптера
    ├── voice/ —— STT (Whisper) + TTS (мультидвижок)
    ├── task/ —— Управление задачами
    ├── webbridge/ —— Автоматизация Playwright
    └── dulus_mcp/ —— MCP клиент
```

---

## Стая (Субагенты)

Dulus может генерировать типизированных агентов, работающих в**изолированных git worktree**.

```
/agents
Agent(type="coder",    task="refactor auth")
Agent(type="reviewer", task="review #042")
Agent(type="tester",   task="run e2e on auth")
```

---

## Разрешения

| Режим | Поведение |
|---|---|
| `auto` *(по умолчанию)* | Чтение всегда разрешено. Запрос перед записью/shell. |
| `accept-all` | Без запросов. Все авто-одобрено. **YOLO.** |
| `manual` | Запрос для каждой операции. |
| `plan` | Только чтение. Только план-файл доступен для записи. |

---

## Слэш-Команды

| Команда | Описание |
|---|---|
| `/model [имя]` | Показать или переключить модель |
| `/memory [запрос]` | Постоянная семантическая память |
| `/voice` | Голосовой ввод (офлайн Whisper) |
| `/brainstorm [тема]` | Совет призраков |
| `/ssj` | Меню мощи (10 ярлыков) |
| `/telegram [токен] [ID]` | Telegram мост |
| `/checkpoint [ID]` | Список / откат контрольных точек |
| `/plan [описание]` | Вход / выход из режима плана |
| `/lang [код]` | Смена языка (34 кода) |
| `/cost` | Потребленные токены и USD |
| `/help` | Все команды |

---

## Лицензия

GPLv3. Форкайте, модифицируйте, распространяйте —— но держите открытым.

> *Назван в честь птицы, а не ракеты. Мы продолжаем лететь.*

---

<div align="center">

<p><sub>Построено когтями <a href="https://github.com/KevRojo">KevRojo</a> · Санто-Доминго, Доминиканская Республика · 2026</sub></p>

</div>

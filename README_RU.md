# Self-Improving AI Agent v1.0

> **[English version](README.md)**

Самоулучшающийся AI-агент с полноценными agentic capabilities: планирование, память, инструменты, под-агенты. Поддерживает **5 провайдеров**: Groq, SambaNova, Cerebras, Zhipu и Anthropic.

## Что нового в v1.0

- **Planning System** — управление задачами как в Claude Code
- **MCP Integration** — Model Context Protocol для внешних инструментов
- **Code Tools** — работа с файлами, git, shell, поиск
- **Agentic Memory** — персистентная память между сессиями
- **Sub-agents** — специализированные агенты (CodeReviewer, TestWriter, Debugger)
- **Human-in-the-Loop** — diff preview, подтверждения, undo
- **Web Tools** — поиск и загрузка веб-страниц

## Ключевая идея

В отличие от обычных чат-ботов, где "память" сжимается со временем, этот агент **перманентно улучшает свой системный промпт** на основе вашего фидбека. Каждое улучшение сохраняется навсегда.

> **Полностью бесплатно**: Работает с бесплатными моделями через Groq!

```
Вы: "Слишком длинный ответ"
     ↓
[Analyzer] анализирует логи, формулирует гипотезы
     ↓
[Versioner] генерирует улучшенный промпт
     ↓
Новая версия промпта сохраняется (v1 → v2 → v3...)
     ↓
Следующие ответы уже с новым "мозгом"
```

## Быстрый старт

### Docker (рекомендуется)

```bash
git clone https://github.com/xmaks82/self-improving-agent.git
cd self-improving-agent

cp .env.example .env
nano .env  # Добавить GROQ_API_KEY

make run
```

### Локальная установка

```bash
git clone https://github.com/xmaks82/self-improving-agent.git
cd self-improving-agent

python -m venv venv
source venv/bin/activate
pip install -e .

cp .env.example .env
agent
```

### API ключи

```bash
# Groq - рекомендуется (бесплатно, быстро)
GROQ_API_KEY=gsk_...          # https://console.groq.com/

# SambaNova - САМЫЙ БЫСТРЫЙ (580 t/s, бесплатно)
SAMBANOVA_API_KEY=...         # https://cloud.sambanova.ai/

# Cerebras - 1M токенов/день бесплатно, ультра-быстрый
CEREBRAS_API_KEY=...          # https://cloud.cerebras.ai/

# Zhipu AI (glm-4.5-flash бесплатно, остальные платно)
ZHIPU_API_KEY=...             # https://open.bigmodel.cn/
```

> Достаточно одного Groq ключа для полного функционала!

## CLI команды

### Основные

| Команда | Описание |
|---------|----------|
| `/help` | Все команды |
| `/model [NAME]` | Показать/сменить модель |
| `/quit` | Выход |

### Задачи

| Команда | Описание |
|---------|----------|
| `/tasks` | Список задач |
| `/task add TEXT` | Создать задачу |
| `/task done ID` | Завершить задачу |
| `/task start ID` | Начать задачу |
| `/task delete ID` | Удалить задачу |
| `/task clear` | Очистить завершённые |

### MCP и инструменты

| Команда | Описание |
|---------|----------|
| `/tools` | Список доступных инструментов |
| `/mcp list` | Список MCP серверов |
| `/mcp connect NAME` | Подключить MCP сервер |
| `/mcp disconnect NAME` | Отключить сервер |

### Промпты и версии

| Команда | Описание |
|---------|----------|
| `/prompt` | Текущий системный промпт |
| `/versions` | История версий |
| `/rollback N` | Откатить к версии N |
| `/feedback TEXT` | Отправить фидбек |

### Прочее

| Команда | Описание |
|---------|----------|
| `/stats` | Статистика сессии |
| `/history` | История диалога |
| `/status` | Статус улучшения |
| `/reset` | Сбросить диалог |
| `/clear` | Очистить экран |

## Модели

### Бесплатные (4 провайдера)

#### Groq (рекомендуется)

| Модель | ID |
|--------|-----|
| Llama 4 Maverick | `llama-4-maverick` |
| Llama 3.3 70B | `llama-3.3-70b` |
| Qwen3 32B | `qwen3-32b` |
| Kimi K2 | `kimi-k2` |

#### SambaNova (580 t/s — самый быстрый!)

| Модель | ID |
|--------|-----|
| Llama 3.3 70B | `samba-llama-70b` |
| Llama 3.1 8B | `samba-llama-8b` |
| DeepSeek V3 | `deepseek-v3` |
| DeepSeek R1 70B | `deepseek-r1-70b` |
| QwQ 32B | `qwq-32b` |

#### Cerebras (1M токенов / день)

| Модель | ID |
|--------|-----|
| Llama 3.1 8B | `llama3.1-8b` |

#### Zhipu AI

| Модель | ID |
|--------|-----|
| GLM 4.5 Flash | `glm-4.5-flash` |

### Платные

#### Zhipu AI

| Модель | ID | Цена (input/output за 1M) |
|--------|-----|--------------------------|
| GLM 4.7 | `glm-4.7` | $0.60 / $2.20 |
| GLM 4.5 Air | `glm-4.5-air` | $0.20 / $1.10 |

#### Anthropic

| Модель | ID | Примечание |
|--------|-----|-----------|
| Claude Opus 4.6 | `claude-opus-4.6` | Флагман, 200K контекст, 128K вывод |
| Claude Sonnet 4.5 | `claude-sonnet` | Баланс скорости и качества |
| Claude Haiku 4.5 | `claude-haiku` | Быстрая и дешёвая |
| Claude Opus 4.5 | `claude-opus-4.5` | Legacy |

## Конфигурация

```bash
# API ключи
GROQ_API_KEY=gsk_...
SAMBANOVA_API_KEY=...
CEREBRAS_API_KEY=...

# Модель по умолчанию (бесплатная)
DEFAULT_MODEL=llama-4-maverick

# Pipeline улучшения (требует Anthropic API key)
ANALYZER_MODEL=claude-sonnet
VERSIONER_MODEL=claude-sonnet
FEEDBACK_MODEL=claude-haiku
```

## Docker

```bash
make help     # Все команды
make run      # Запустить
make build    # Собрать образ
make update   # Обновить (git pull + rebuild)
make version  # Версия
make shell    # Shell в контейнере
```

## Лицензия

MIT

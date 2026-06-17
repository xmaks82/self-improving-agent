# Самоулучшающийся AI-агент

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://github.com/xmaks82/self-improving-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/xmaks82/self-improving-agent/actions)

> **[English version](README.md)**

**Терминальный кодинг-агент, который реально исполняет инструменты — и переписывает собственный системный промпт по твоему фидбэку.**

Он гоняет настоящий цикл `думать → инструмент → результат` (чтение/правка/запись/shell/git/поиск/web),
спрашивает перед изменениями, умеет откат, и обращается к внешним **MCP-серверам** прямо в разговоре.
Когда ты даёшь фидбэк, фоновый конвейер анализирует логи и выкатывает улучшенный
системный промпт — с **метриками и авто-откатом**, если новая версия хуже. Работает
бесплатно из коробки через локальный роутер моделей **FCM**, либо на 6 keyed-провайдерах /
твоей подписке Claude.

```
Ты: "Ответы слишком длинные"
     ↓ FeedbackDetector  (рабочие команды вроде "исправь баг" не считаются критикой)
[Analyzer] читает логи, строит гипотезы
     ↓
[Versioner] пишет улучшенный промпт  (мета-агенты защищены от переписывания)
     ↓
Новая версия активна  →  метрики фидбэка отслеживаются
     ↓
Если хуже (≥60% негатива за ≥4 сэмпла) → авто-откат к родительской версии
```

## Главное (v1.5.1)

- **Честность и эпистемика** — статичная (неэволюционирующая) секция системного
  промпта: не выдумывать пути к файлам, имена символов, сигнатуры API и вывод
  команд; проверять делом (прочитать файл, выполнить команду), а не угадывать;
  правдиво сообщать результат; признавать ошибки спокойно, без самобичевания.
- **Настоящий агентный цикл** — `think → tool_use → tool_result → repeat`, лимит
  итераций, защита от зацикливания, ошибки инструментов возвращаются для
  восстановления, реальный учёт токенов. Вывод **стримится по токенам во время
  работы с инструментами** (Anthropic + OpenAI-совместимые/FCM), с graceful-фолбэком.
- **Инструменты с защитой** — чтение / **точечная правка** / запись (атомарная +
  детект внешних изменений) / shell / git / поиск / web / worktree / notebook.
  Подтверждение записи/команд, рабочий **undo**, закрыта shell-инъекция (валидируется
  голова каждого под-командного сегмента; редиректы/сабшеллы запрещены), SSRF-guard
  с проверкой каждого редирект-хопа.
- **MCP в цикле** — инструменты любого подключённого MCP-сервера (например, сервера
  памяти) доступны модели прямо в разговоре.
- **Замкнутый контур самоулучшения** — метрики по версиям + авто-откат; детектор
  фидбэка не путает «исправь баг в X» с критикой себя; versioner не может переписать
  свой/analyzer промпт.
- **Субагенты с инструментами** — CodeReviewer / TestWriter / Debugger / Researcher /
  Refactorer и adversarial-верификатор гоняют тот же tool-loop.
- **Бесплатно по умолчанию** — роутер `fcm` агрегирует free-модели с health-probe и
  авто-failover, поэтому нет устаревающих model-id, которые надо поддерживать.

## LLM-провайдеры
| Провайдер | Заметки | Ключ |
|-----------|---------|------|
| **FCM** (по умолчанию) | Локальный роутер: агрегация free-моделей, health-probe, авто-failover | не нужен — задай `FCM_BASE_URL` |
| **Groq** | Быстрый free-tier | [console.groq.com](https://console.groq.com/) |
| **SambaNova** | ~580 т/с | [cloud.sambanova.ai](https://cloud.sambanova.ai/) |
| **Cerebras** | Free, очень быстро | [cloud.cerebras.ai](https://cloud.cerebras.ai/) |
| **OpenRouter** | Free-tier, 1M контекст | [openrouter.ai/keys](https://openrouter.ai/keys) |
| **Zhipu** | GLM flash free | [open.bigmodel.cn](https://open.bigmodel.cn/) |
| **Anthropic** | Claude через OAuth-подписку или API-ключ (авто-фолбэк) | [console.anthropic.com](https://console.anthropic.com/) |

У keyed-провайдеров есть курированные шорткаты моделей; считай их статичные списки
best-effort и предпочитай `fcm` (или проверяй своим ключом) — каталоги провайдеров
часто меняются.

## Быстрый старт

```bash
git clone https://github.com/xmaks82/self-improving-agent.git
cd self-improving-agent
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
agent      # по умолчанию бесплатно через FCM (ключ не нужен)
```

Чтобы использовать keyed-провайдера: положи ключ в `.env` (`cp .env.example .env`)
и задай `DEFAULT_MODEL` (например `llama-3.3-70b` для Groq). Docker: `make run`.

### Подключить память (опционально)

Укажи MCP-сервер памяти в `~/.agent/mcp.yaml`:

```yaml
servers:
  memory:
    command: /путь/к/python
    args: [/путь/к/memory_server.py]
    env: {MEMORY_DIR: /путь/к/памяти}
    enabled: true
```

Его инструменты (search/save/recall…) автоматически попадают в цикл при старте.

## Конфигурация (env)

```bash
# Бесплатно по умолчанию — ничего не требуется. Чтобы пинуть модель роутера:
FCM_BASE_URL=http://localhost:9999/v1   # OpenAI-совместимый эндпоинт
FCM_MODEL=fcm                            # или fcm:free-coding

# Keyed-провайдеры (опционально) — ключ + выбор модели
GROQ_API_KEY=gsk_...
OPENROUTER_API_KEY=sk-or-...
ANTHROPIC_API_KEY=sk-ant-...             # или Claude OAuth: claude setup-token → /auth paste
DEFAULT_MODEL=fcm                        # по умолчанию; напр. llama-3.3-70b, claude-haiku, …

# Тюнинг
AGENT_MAX_TOOL_ITERATIONS=25
FACT_DISTILL=1
```

## Основные команды CLI

| Команда | Описание |
|---------|----------|
| `/model [ИМЯ]` | Показать/сменить модель |
| `/tools` | Все инструменты (локальные + MCP) |
| `/mcp connect\|list` | Управление MCP-серверами |
| `/plan ЗАДАЧА` · `/explore ЗАПРОС` | Read-only дизайн / поиск по коду |
| `/fork ИМЯ ЗАДАЧА` · `/forks` | Фоновые клоны агента |
| `/verify` | Adversarial-верификация (с инструментами) |
| `/auth [status\|paste]` | Авторизация подписки Claude |
| `/compact` · `/sessions` · `/resume ID` | История / сессии |
| `/cost` · `/stats` · `/export [md\|json]` | Расход, статистика, экспорт |
| `/commit` · `/review [PR]` · `/simplify` · `/debug` | Навыки |
| `/feedback ТЕКСТ` · `/versions` · `/diff [V1] [V2]` · `/prompt` | Самоулучшение |
| `/team` · `/summary` · `/plugins` · `/voice` | Память, заметки, плагины, голос |

## Структура проекта

```
src/agent/
├── main.py            # Точка входа (registry → pipeline → CLI)
├── config.py          # Конфиг (модель по умолчанию: fcm)
├── agents/            # main_agent, субагенты, verification, analyzer, versioner,
│                      #   pipeline, _tool_loop (общий ограниченный tool-loop)
├── tools/             # filesystem(edit/atomic/stale), shell(hardened), git, search,
│                      #   web(SSRF-guard), worktree, notebook, registry, permissions
├── approval/          # подтверждение + undo (проведены в registry)
├── clients/           # клиенты провайдеров + FCM + OpenAI-compat + OAuth; stream_with_tools
├── mcp/               # MCP клиент/менеджер + мост в registry инструментов
├── memory/            # SQLite гибридная память (вектор+keyword RRF), secret scanner, bounds
├── core/              # feedback (замкнутый контур), cost, compaction, session memory
├── storage/           # версионированные промпты (метрики + авто-откат), логи, сессии
├── prompts/ · skills/ · plugins/ · planning/ · interfaces/   # composer, slash-навыки, плагины, задачи, CLI+голос
tests/                 # loop, tool-safety, MCP-мост, self-improve, streaming, …
```

## Разработка

```bash
pip install -e ".[dev]"
pytest -q
ruff check src tests
```

## Лицензия

MIT

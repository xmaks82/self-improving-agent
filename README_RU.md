# Self-Improving AI Agent

> **[English version](README.md)**

Мультиагентная система с **16 взаимосвязанными агентами**, композитными промптами, перманентной эволюцией промпта из фидбека и **гибридной долговременной памятью** (вектор + ключевые слова). Работает на **6 бесплатных LLM-провайдерах** или подписке Claude через OAuth.

## 16 агентов в едином pipeline

| # | Агент | Роль |
|---|-------|------|
| 1 | **MainAgent** | Основной разговорный агент |
| 2 | **AnalyzerAgent** | Анализ логов, формулировка гипотез |
| 3 | **VersionerAgent** | Генерация улучшенных промптов |
| 4-8 | **5 Sub-agents** | CodeReviewer, TestWriter, Debugger, Researcher, Refactorer |
| 9 | **VerificationAgent** | Adversarial тестирование (авто после 3+ правок) |
| 10 | **ExploreAgent** | Read-only поиск по коду (`/explore`) |
| 11 | **PlanAgent** | Архитектурное проектирование (`/plan`) |
| 12 | **ForkManager** | Фоновые клоны с контекстом (`/fork`) |
| 13 | **AgentOrchestrator** | Координация sub-agents |
| 14-16 | **LLM-сервисы** | SessionMemory, Compactor, FeedbackDetector |

## 6 бесплатных провайдеров

| Провайдер | Модели | Ключ |
|-----------|--------|------|
| **Groq** | Llama 4 Scout, 3.3 70B, Qwen3 32B, GPT-OSS 120B/20B | [console.groq.com](https://console.groq.com/) |
| **SambaNova** (580 t/s) | Llama 4 Maverick, DeepSeek V3.1/V3.2, MiniMax M2.7, Gemma 4 | [cloud.sambanova.ai](https://cloud.sambanova.ai/) |
| **Cerebras** (1M/день) | Llama 3.1, Qwen3 235B, GPT-OSS, GLM 4.7 | [cloud.cerebras.ai](https://cloud.cerebras.ai/) |
| **OpenRouter** (free) | Qwen3-Next, Qwen3-Coder, Kimi K2.6, GLM 4.5 Air | [openrouter.ai/keys](https://openrouter.ai/keys) |
| **Zhipu** (без лимитов) | GLM 4.5/4.7 Flash (free), GLM 5.1/5/4.7 | [open.bigmodel.cn](https://open.bigmodel.cn/) |
| **Anthropic** (OAuth/API) | Claude Opus 4.8/4.7/4.6, Sonnet 4.6, Haiku 4.5 | OAuth подписка или API |

**Подписка Claude**: `/auth paste` с setup-token. Авто-fallback на API key при блокировке.

## Быстрый старт

```bash
git clone https://github.com/xmaks82/self-improving-agent.git
cd self-improving-agent
cp .env.example .env   # Добавить хотя бы один бесплатный ключ
make run
```

## CLI команды (35+)

| Команда | Описание |
|---------|----------|
| `/model` | Показать/сменить модель |
| `/plan ЗАДАЧА` | Архитектурный план (read-only) |
| `/explore ЗАПРОС` | Поиск по коду (read-only) |
| `/fork ИМЯ ЗАДАЧА` | Фоновый клон агента |
| `/verify` | Adversarial верификация |
| `/auth` | Управление OAuth подпиской |
| `/commit` | Умный git commit |
| `/review [PR]` | Ревью PR через gh |
| `/simplify` | Проверка качества кода |
| `/debug` | Структурная отладка |
| `/compact` | Сжатие истории |
| `/sessions` `/resume` | Сохранение/возобновление |
| `/cost` | Токены и расходы |
| `/export` | Экспорт в md/json |
| `/config` | Настройки на лету |
| `/diff` | Diff версий промпта |
| `/style` | Стиль вывода |
| `/summary` | Заметки сессии |
| `/team` | Командная память |
| `/plugins` | Плагины |
| `/voice` | Голосовой ввод |
| `/tasks` | Управление задачами |
| `/stats` | Статистика |

## Память

- **Гибридный поиск** — векторное сходство (эмбеддинги) + ключевые слова, слияние через Reciprocal Rank Fusion (RRF).
- **Опционально и без поломок** — нет бэкенда эмбеддингов → автоматический откат на ключевой поиск, агент работает «из коробки».
- **Любой OpenAI-совместимый endpoint** через `EMBEDDINGS_URL` (локальный llama-server, Ollama, OpenAI). Адрес — только в твоём приватном `.env`, в репозиторий ничего не попадает.
- **4 типа памяти** — episodic / semantic / procedural / working, с decay важности и промоушеном (консолидация).
- **Юникод-токенизация** — ключевой поиск теперь работает и для русского (был баг: ASCII-only regex отбрасывал кириллицу).

```bash
# Включить гибридную память (опционально):
EMBEDDINGS_URL=http://localhost:8090/v1/embeddings
```

## Безопасность

- 6-уровневая проверка bash (инъекции, редиректы, переменные, контрольные символы, git)
- Command semantics (grep exit 1 ≠ ошибка)
- Read-before-edit (обязательное чтение перед записью)
- Permission system (auto-approve / confirm / block)
- Secret scanner (8 паттернов кредов)
- OAuth fallback (блокировка → API key)
- File permissions 0600 на credentials

## Конфигурация

```bash
GROQ_API_KEY=gsk_...          # Бесплатно
OPENROUTER_API_KEY=sk-or-...  # Бесплатно, 1M контекст
DEFAULT_MODEL=llama-4-scout
```

## Лицензия

MIT

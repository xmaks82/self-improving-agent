# Self-Improving AI Agent v1.3

> **[English version](README.md)**

Самоулучшающийся AI-агент с композитными промптами, верификацией, памятью, инструментами и под-агентами. Поддерживает **5 провайдеров** включая бесплатные API.

## Что нового

### v1.2 — Архитектурные паттерны
- **Composable System Prompt** — секционная архитектура промпта (intro, tasks, actions, tools, style)
- **Verification Agent** — adversarial верификация после 3+ изменений файлов (PASS/FAIL/PARTIAL)
- **Explore Agent** — быстрый read-only поиск по кодовой базе
- **Enhanced Bash Security** — 6 уровней проверки (command substitution, redirects, переменные, git safety)
- **Read-Before-Edit** — файлы должны быть прочитаны перед изменением
- **Bounded Memory** — лимит 200 строк / 25KB с усечением
- **Tool Prompts** — детальные инструкции для каждого инструмента

### v1.1 — 10 улучшений
- Context Compaction, Session Persistence, Cost Tracking
- Permission System, Git Safety, Runtime Config
- Export, Prompt Diff, Enhanced Search, Deferred Tools

### v1.0 — Базовый функционал
- Planning, MCP, Code Tools, Memory, Sub-agents, Human-in-the-Loop

## Ключевая идея

Этот агент **перманентно улучшает свой системный промпт** на основе фидбека. Каждое улучшение сохраняется навсегда.

```
Вы: "Слишком длинный ответ"
     ↓
[Analyzer] анализирует логи, формулирует гипотезы
     ↓
[Versioner] генерирует улучшенный промпт
     ↓
v1 → v2 → v3... Следующие ответы уже с новым "мозгом"
```

> **Полностью бесплатно** — работает с бесплатными моделями!

## Быстрый старт

```bash
git clone https://github.com/xmaks82/self-improving-agent.git
cd self-improving-agent
cp .env.example .env
nano .env  # Добавить GROQ_API_KEY
make run
```

## Модели

### Бесплатные (4 провайдера)

#### Groq (рекомендуется)
| Модель | ID |
|--------|-----|
| Llama 4 Scout | `llama-4-scout` |
| Llama 3.3 70B | `llama-3.3-70b` |
| Qwen3 32B | `qwen3-32b` |
| Kimi K2 | `kimi-k2` |
| GPT-OSS 120B | `gpt-oss-120b` |

#### SambaNova (580 t/s)
| Модель | ID |
|--------|-----|
| Llama 4 Maverick | `llama-4-maverick` |
| Llama 3.3 70B | `samba-llama-70b` |
| DeepSeek V3.2 | `deepseek-v3.2` |
| DeepSeek R1 | `deepseek-r1` |
| MiniMax M2.5 | `minimax-m2.5` |

#### Cerebras (1M токенов/день)
| Модель | ID |
|--------|-----|
| Llama 3.1 8B | `llama3.1-8b` |
| Qwen3 235B | `qwen3-235b` |
| GPT-OSS 120B | `gpt-oss-120b-cerebras` |
| GLM 4.7 | `glm-4.7-cerebras` |

#### Zhipu AI (без лимитов)
| Модель | ID |
|--------|-----|
| GLM 4.5 Flash | `glm-4.5-flash` |
| GLM 4.7 Flash | `glm-4.7-flash` |

### Платные

#### Zhipu AI
| Модель | ID | Цена (за 1M токенов) |
|--------|-----|---------------------|
| GLM 5.1 | `glm-5.1` | $1.00 / $3.20 |
| GLM 5 | `glm-5` | $1.00 / $3.20 |
| GLM 5 Code | `glm-5-code` | $1.20 / $5.00 |
| GLM 4.7 | `glm-4.7` | $0.60 / $2.20 |

#### Anthropic
| Модель | ID | Цена (за 1M токенов) |
|--------|-----|---------------------|
| Claude Opus 4.6 | `claude-opus-4.6` | $5.00 / $25.00 |
| Claude Sonnet 4.6 | `claude-sonnet-4.6` | $3.00 / $15.00 |
| Claude Haiku 4.5 | `claude-haiku` | $1.00 / $5.00 |
| Claude Opus 4.5 | `claude-opus-4.5` | $5.00 / $25.00 |

## CLI команды

| Команда | Описание |
|---------|----------|
| `/model [NAME]` | Показать/сменить модель |
| `/compact` | Сжать историю |
| `/sessions` | Список сохранённых сессий |
| `/resume ID` | Возобновить сессию |
| `/cost` | Токены и расходы |
| `/export [md\|json]` | Экспорт диалога |
| `/config [set K V]` | Конфигурация на лету |
| `/diff [V1] [V2]` | Diff версий промпта |
| `/tasks` | Список задач |
| `/task add/done/start/delete` | Управление задачами |
| `/tools` | Инструменты |
| `/mcp list/connect/disconnect` | MCP серверы |
| `/prompt` | Текущий промпт |
| `/versions` | История версий |
| `/rollback N` | Откат к версии N |
| `/feedback TEXT` | Фидбек для улучшения |
| `/stats` | Статистика |

## Конфигурация

```bash
DEFAULT_MODEL=llama-4-scout
ANALYZER_MODEL=llama-3.3-70b
VERSIONER_MODEL=llama-3.3-70b
FEEDBACK_MODEL=llama-4-scout
```

## Docker

```bash
make run      # Запустить
make build    # Собрать
make update   # Обновить
make shell    # Shell в контейнере
```

## Лицензия

MIT

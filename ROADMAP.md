# Self-Improving Agent — Roadmap v2.0

## Обзор

Трансформация из простого self-improving agent в полноценный **Agentic Coding Platform** на основе лучших практик 2026 года.

---

## Фаза 1: Planning/TODO System
**Сложность: Низкая | Срок: 1 неделя**

Система планирования задач как у Claude Code — агент декомпозирует сложные задачи.

### Компоненты

```
src/agent/
├── planning/
│   ├── __init__.py
│   ├── task.py          # Task dataclass
│   ├── planner.py       # TaskPlanner agent
│   └── renderer.py      # CLI renderer для TODO
```

### Модель данных

```python
@dataclass
class Task:
    id: str
    content: str
    status: Literal["pending", "in_progress", "completed", "blocked"]
    priority: int = 0
    parent_id: Optional[str] = None
    subtasks: list[str] = field(default_factory=list)
    created_at: datetime
    completed_at: Optional[datetime] = None
```

### Интеграция

1. **Перед выполнением**: агент создаёт план
2. **Во время**: обновляет статус задач
3. **После**: показывает результат

### CLI команды

| Команда | Описание |
|---------|----------|
| `/plan` | Показать текущий план |
| `/plan create` | Создать план для задачи |
| `/plan clear` | Очистить план |

---

## Фаза 2: MCP Integration
**Сложность: Средняя | Срок: 2 недели**

Model Context Protocol — стандарт для подключения внешних инструментов.

### Архитектура

```
src/agent/
├── mcp/
│   ├── __init__.py
│   ├── client.py        # MCP Client
│   ├── server.py        # MCP Server (для внешних агентов)
│   ├── registry.py      # Registry подключённых серверов
│   └── tools/
│       ├── filesystem.py    # Встроенный: файловая система
│       ├── shell.py         # Встроенный: bash команды
│       └── git.py           # Встроенный: git операции
```

### Конфигурация

```yaml
# ~/.agent/mcp.yaml
servers:
  - name: filesystem
    command: npx
    args: ["@anthropic/mcp-server-filesystem", "/home/user/projects"]

  - name: github
    command: npx
    args: ["@anthropic/mcp-server-github"]
    env:
      GITHUB_TOKEN: ${GITHUB_TOKEN}

  - name: browser
    command: npx
    args: ["@anthropic/mcp-server-puppeteer"]
```

### Встроенные MCP Tools

| Tool | Описание |
|------|----------|
| `read_file` | Чтение файлов |
| `write_file` | Запись файлов |
| `edit_file` | Редактирование (diff-based) |
| `list_directory` | Листинг директории |
| `run_command` | Выполнение bash (sandboxed) |
| `git_status` | Git статус |
| `git_diff` | Git diff |
| `git_commit` | Git commit |
| `search_files` | Поиск по файлам (grep) |
| `search_code` | Поиск по коду (AST) |

### CLI команды

| Команда | Описание |
|---------|----------|
| `/tools` | Список доступных инструментов |
| `/mcp list` | Список MCP серверов |
| `/mcp connect <server>` | Подключить сервер |
| `/mcp disconnect <server>` | Отключить сервер |

---

## Фаза 3: Code Tools (без MCP)
**Сложность: Средняя | Срок: 1 неделя**

Базовые инструменты для работы с кодом — можно реализовать до MCP.

### Компоненты

```
src/agent/
├── tools/
│   ├── __init__.py
│   ├── base.py          # BaseTool interface
│   ├── filesystem.py    # File operations
│   ├── shell.py         # Command execution
│   ├── git.py           # Git operations
│   └── search.py        # Code search
```

### Tool Interface

```python
class BaseTool(ABC):
    name: str
    description: str
    parameters: dict  # JSON Schema

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        pass

@dataclass
class ToolResult:
    success: bool
    output: str
    error: Optional[str] = None
```

### Sandbox

```python
class SandboxExecutor:
    """Безопасное выполнение команд."""

    allowed_commands: list[str]
    working_dir: Path
    timeout: int = 30

    async def execute(self, command: str) -> str:
        # Проверка whitelist
        # Выполнение в subprocess
        # Таймаут
```

---

## Фаза 4: Agentic Memory
**Сложность: Высокая | Срок: 3 недели**

Долгосрочная память между сессиями с адаптивным обучением.

### Архитектура

```
src/agent/
├── memory/
│   ├── __init__.py
│   ├── types.py         # Memory types
│   ├── store.py         # Storage backend (SQLite/ChromaDB)
│   ├── retriever.py     # Semantic retrieval
│   ├── consolidator.py  # Memory consolidation
│   └── manager.py       # MemoryManager
```

### Типы памяти

```python
class MemoryType(Enum):
    EPISODIC = "episodic"      # Конкретные взаимодействия
    SEMANTIC = "semantic"       # Общие знания о пользователе
    PROCEDURAL = "procedural"   # Как выполнять задачи
    WORKING = "working"         # Текущий контекст

@dataclass
class Memory:
    id: str
    type: MemoryType
    content: str
    embedding: list[float]
    importance: float  # 0-1
    access_count: int
    last_accessed: datetime
    created_at: datetime
    metadata: dict
```

### Storage

```
data/
├── memory/
│   ├── episodic.db      # SQLite для структурированных данных
│   ├── semantic.db      # ChromaDB для vector search
│   └── index/           # FAISS/Annoy индексы
```

### Retrieval Flow

```
User Message
    ↓
[1] Extract entities & intent
    ↓
[2] Query semantic memory (top-k similar)
    ↓
[3] Query episodic memory (recent relevant)
    ↓
[4] Rank by importance + recency
    ↓
[5] Inject into system prompt
    ↓
Agent Response
    ↓
[6] Store new memories
[7] Update importance scores
```

### Consolidation

Периодическая консолидация памяти:
- Объединение похожих воспоминаний
- Удаление устаревших
- Обновление importance scores

---

## Фаза 5: Sub-agents
**Сложность: Высокая | Срок: 2 недели**

Специализированные под-агенты для конкретных задач.

### Архитектура

```
src/agent/
├── agents/
│   ├── base.py          # BaseAgent (существует)
│   ├── main_agent.py    # MainAgent (существует)
│   ├── analyzer.py      # Analyzer (существует)
│   ├── versioner.py     # Versioner (существует)
│   ├── orchestrator.py  # NEW: AgentOrchestrator
│   ├── code_reviewer.py # NEW: CodeReviewer
│   ├── test_writer.py   # NEW: TestWriter
│   ├── researcher.py    # NEW: WebResearcher
│   └── debugger.py      # NEW: Debugger
```

### Orchestrator

```python
class AgentOrchestrator:
    """Координатор под-агентов."""

    agents: dict[str, BaseAgent]

    async def delegate(
        self,
        task: str,
        agent_type: str,
        context: dict,
    ) -> AgentResult:
        agent = self.agents[agent_type]
        return await agent.execute(task, context)

    async def parallel_execute(
        self,
        tasks: list[tuple[str, str, dict]],
    ) -> list[AgentResult]:
        """Параллельное выполнение задач разными агентами."""
        pass
```

### Специализированные агенты

| Агент | Задача | Tools |
|-------|--------|-------|
| `CodeReviewer` | Ревью кода, поиск проблем | read_file, search_code |
| `TestWriter` | Генерация тестов | read_file, write_file |
| `Researcher` | Поиск информации | web_search, fetch_url |
| `Debugger` | Анализ ошибок | read_file, run_command, search_code |
| `Refactorer` | Рефакторинг кода | read_file, edit_file |

---

## Фаза 6: Human-in-the-Loop
**Сложность: Низкая | Срок: 1 неделя**

Улучшенное взаимодействие с пользователем.

### Компоненты

```
src/agent/
├── approval/
│   ├── __init__.py
│   ├── diff_viewer.py   # Показ diff перед изменениями
│   ├── confirmator.py   # Запрос подтверждения
│   └── dry_run.py       # Режим preview
```

### Функционал

1. **Diff Preview**: показ изменений перед записью файла
2. **Confirmation**: запрос подтверждения для деструктивных операций
3. **Dry Run**: режим, где агент показывает что сделает, но не делает
4. **Undo**: возможность отката последних изменений

### CLI

```
Agent: Я хочу изменить файл main.py:

╭─────────────── Diff Preview ────────────────╮
│ @@ -10,3 +10,5 @@                           │
│  def main():                                │
│ -    pass                                   │
│ +    print("Hello")                         │
│ +    return 0                               │
╰─────────────────────────────────────────────╯

Apply changes? [y/n/edit]:
```

---

## Фаза 7: Web Tools
**Сложность: Средняя | Срок: 1 неделя**

Инструменты для работы с интернетом.

### Компоненты

```
src/agent/
├── tools/
│   ├── web_search.py    # Поиск (DuckDuckGo/SearXNG)
│   ├── web_fetch.py     # Загрузка страниц
│   └── web_browser.py   # Browser automation (Playwright)
```

### Tools

| Tool | Описание |
|------|----------|
| `web_search` | Поиск в интернете |
| `fetch_url` | Загрузка и парсинг страницы |
| `browse` | Интерактивный браузер |

---

## Итоговая архитектура v2.0

```
┌─────────────────────────────────────────────────────────────────────┐
│                              CLI / API                               │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────┐
│                         MAIN AGENT + PLANNER                         │
│                    Planning, Task Decomposition                      │
└───────┬───────────────────────────────────────────────────┬─────────┘
        │                                                   │
        ▼                                                   ▼
┌───────────────────┐                           ┌───────────────────────┐
│   SUB-AGENTS      │                           │    MEMORY SYSTEM      │
│                   │                           │                       │
│ • CodeReviewer    │                           │ • Episodic Memory     │
│ • TestWriter      │                           │ • Semantic Memory     │
│ • Researcher      │                           │ • Working Memory      │
│ • Debugger        │                           │ • Consolidation       │
│ • Analyzer        │                           │                       │
│ • Versioner       │                           │                       │
└───────┬───────────┘                           └───────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────────────┐
│                              TOOLS LAYER                              │
│                                                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │  Filesystem │  │    Shell    │  │     Git     │  │  Web/Search │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                     MCP Server Registry                          │ │
│  │  GitHub, Slack, Database, Browser, Custom Servers...             │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────┐
│                         IMPROVEMENT PIPELINE                          │
│                                                                       │
│     Feedback Detection → Analyzer → Versioner → Prompt Update        │
└───────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────┐
│                            STORAGE LAYER                              │
│                                                                       │
│  data/prompts/     data/logs/     data/memory/     ~/.agent/mcp.yaml │
└───────────────────────────────────────────────────────────────────────┘
```

---

## Timeline

| Фаза | Название | Срок | Зависимости |
|------|----------|------|-------------|
| 1 | Planning/TODO | 1 неделя | — |
| 2 | Code Tools | 1 неделя | — |
| 3 | Human-in-the-Loop | 1 неделя | Фаза 2 |
| 4 | MCP Integration | 2 недели | Фаза 2 |
| 5 | Web Tools | 1 неделя | Фаза 2 |
| 6 | Sub-agents | 2 недели | Фаза 1, 2 |
| 7 | Agentic Memory | 3 недели | — |

**Общий срок: ~8-10 недель**

---

## Версионирование

- **v0.3.x** — текущая версия (self-improving prompts)
- **v0.4.0** — Planning + Code Tools
- **v0.5.0** — MCP Integration
- **v0.6.0** — Sub-agents
- **v1.0.0** — Agentic Memory + полная интеграция

---

## Начало работы

Рекомендуемый порядок реализации:

1. **Planning/TODO** — быстрая win, улучшает UX
2. **Code Tools** — базовый функционал для coding agent
3. **Human-in-the-Loop** — безопасность и контроль
4. **MCP** — расширяемость
5. **Sub-agents** — специализация
6. **Agentic Memory** — персонализация

# Context Compaction Engine

Production-ready context compaction system for AI agent frameworks. Optimizes token usage by intelligently summarizing and pruning conversation history.

## Features

- **Token Estimation**: Accurate token counting for GPT-4, Claude, and other models
- **Priority Ranking**: Intelligent message importance classification
- **LLM Summarization**: AI-powered compression using OpenAI, Anthropic, or Ollama
- **REST API**: FastAPI server for integration
- **Storage**: LanceDB for history and analytics
- **CLI Commands**: Slash commands for OpenClaw integration

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

```python
from src import CompactionEngine, CompactionConfig

# Configure
config = CompactionConfig(
    model="gpt-4",
    max_context_percentage=80.0,
    enable_summarization=True
)

# Initialize engine
engine = CompactionEngine(config)

# Analyze messages
messages = [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there!"},
]

analysis = engine.analyze(messages)
print(f"Tokens: {analysis['tokens'].total}")

# Compact if needed
compacted, result = engine.compact(messages)
print(f"Saved: {result.tokens_saved} tokens")
```

## REST API

Start the API server:

```bash
python src/api.py
```

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service info |
| `/health` | GET | Health check |
| `/compact` | POST | Compact messages |
| `/estimate` | POST | Estimate tokens |
| `/stats` | GET | Get statistics |
| `/config` | GET | Get config |
| `/config` | POST | Update config |
| `/history` | GET | Get history |

### Example

```bash
# Estimate tokens
curl -X POST http://localhost:8000/estimate \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello"}]}'

# Compact
curl -X POST http://localhost:8000/compact \
  -H "Content-Type: application/json" \
  -d '{"messages": [...]}'
```

## CLI Commands

```bash
# Estimate tokens
python -m src.cli estimate messages.json

# Compact
python -m src.cli compact messages.json --session-id abc123

# Stats
python -m src.cli stats
```

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| model | gpt-4 | Model for context limit |
| max_context_percentage | 80.0 | Trigger compaction at % of context |
| keep_recent | 10 | Keep last N messages intact |
| keep_user | true | Always keep user messages |
| keep_tools_recent | 5 | Keep recent tool results |
| strategy | oldest_first | Selection strategy |
| enable_summarization | true | Use LLM summarization |
| min_savings_percentage | 10.0 | Minimum savings to trigger |

## Summarizer Providers

Configure LLM summarization:

```python
from src.summarizer import create_summarizer

# OpenAI
summarizer = create_summarizer(
    provider="openai",
    api_key="sk-...",
    model="gpt-4o-mini"
)

# Anthropic
summarizer = create_summarizer(
    provider="anthropic",
    api_key="sk-ant-...",
    model="claude-3-haiku"
)

# Ollama (local)
summarizer = create_summarizer(
    provider="ollama",
    model="llama2"
)
```

## Docker

```bash
docker build -t context-compaction .
docker run -p 8000:8000 context-compaction
```

## License

MIT

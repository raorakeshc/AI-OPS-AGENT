# Deployment Guide & Assumptions

## Requirements
- Python 3.11+
- A valid Google Gemini API Key.
- Network access to Google's Generative AI endpoints.

## Packaging
The application is packaged using Docker for consistent environment reproducibility.

### Building the image
```bash
docker build -t ai-ops-agent .
```

### Running locally
```bash
docker run -it -e GOOGLE_API_KEY="your-api-key-here" ai-ops-agent
```

## Logging & Tracing
All agent actions, API calls, tool invocations, latency, and errors are captured by the Python `logging` module and stored in the `logs/agent.log` file.
When deployed as a container, it is recommended to mount the `logs` and `data` directories to a host volume to persist feedback and logs:
```bash
docker run -it -v $(pwd)/logs:/app/logs -v $(pwd)/data:/app/data -e GOOGLE_API_KEY="..." ai-ops-agent
```

### LangSmith Distributed Tracing
Because this project is built on LangChain and LangGraph, it natively supports **LangSmith** for advanced observability, cost tracking, latency analysis, and visual debugging—with absolutely **zero code changes** required!

To enable LangSmith tracing, simply add the following to your `.env` file or export them as environment variables:
```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT="https://api.smith.langchain.com"
LANGCHAIN_API_KEY="your-langsmith-api-key"
LANGCHAIN_PROJECT="ai-ops-agent"
```
Once added, every single agent step, LLM invocation, and tool call will automatically be logged visually in your LangSmith dashboard.

## Graceful Failure Handling
The `SupportAgent.ask()` method is wrapped in a `try/except` block. If the underlying LLM fails (e.g. rate limit, network timeout, model quota exhaustion), the agent catches the exception, logs it to `agent.log` with latency metrics, and returns a graceful user-facing error message instead of crashing the process.

## Assumptions & Limitations
- **State Storage**: Currently, `MemorySaver` uses an in-memory SQLite store by default or ephemeral state. For production, `checkpointer` should be replaced with a persistent backend (e.g., PostgreSQL or Redis Checkpointer for LangGraph) so that conversation state survives container restarts.
- **Feedback Storage**: Feedback is stored locally in `data/feedback.json`. In a distributed deployment (multiple containers), this should be migrated to a shared database.
- **Rate Limits**: The agent relies on `gemini-flash-lite-latest` which has generous free-tier limits, but high concurrency will require a paid Google Cloud project.

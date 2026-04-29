# Ella Speaks Calmly Local Overrides

These project-local notes apply on top of the shared `anywhere-agents` defaults.

## Project Summary

- `Ella Speaks Calmly` is an AI counseling system with chat, voice, RAG, personality-aware responses, and crisis detection.
- Backend: FastAPI in `src/`, typically on port `5050`.
- Frontend: React 18 + Vite in `frontend/client`, typically on port `5173`.
- Voice worker: LiveKit agent in `src/voice/agent.py`.

## Repo-Specific Layout

- `src/main.py` is the backend entrypoint.
- `src/ai_layer/` contains LLM-facing integrations.
- `src/crisis/` contains the shared crisis detection and alerting pipeline.
- `src/rag_layer/` contains Pinecone-backed retrieval logic.
- `src/database/` contains Supabase-facing services.
- `frontend/client/src/` is the actual frontend app source. Treat `frontend/client` as the Vite root.
- `start.sh` and `start.bat` are the main local launchers.

## Working Defaults

- Preserve existing mental-health and crisis-safety behavior unless the task explicitly changes it.
- Prefer small, surgical changes over broad refactors in crisis, voice, and auth flows.
- Keep backend and frontend contracts aligned when changing API payloads.
- If a change touches both text and voice behavior, verify both paths because crisis logic is shared.

## Agent Guidance

- Use `AGENTS.local.md` for cross-agent repo rules.
- Keep `CLAUDE.local.md` as the more detailed Claude-specific project guide.
- If this repo needs Codex-specific overrides later, add `agents/codex.local.md` instead of editing generated files.

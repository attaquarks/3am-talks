# Ella Speaks Calmly (3AM Talks)

**Ella Speaks Calmly** (formerly 3AM Talks) is an AI-powered therapy and counseling system that provides personalized mental health support. It combines personality-aware responses, retrieval-augmented generation (RAG), and evidence-based therapeutic techniques to offer a calm, supportive conversational experience.

## What It Does

- **Personality-aware support** — The system adapts to your personality (assessed via a short questionnaire and ongoing conversation) so responses feel natural and tailored to you.
- **Evidence-based therapy** — Uses techniques from CBT, DBT, ACT, and other modalities, retrieved and applied based on what you share.
- **Conversation memory** — Your sessions and profile are stored so the assistant can maintain context and continuity across conversations.
- **Web interface** — A React frontend talks to a Python backend (FastAPI) so you can chat with Ella in the browser.

## Tech Overview

- **Backend**: Python with FastAPI; conversation logic, personality assessment (BERT-based), and RAG (Pinecone) for technique retrieval.
- **AI**: Local LLM via Ollama (e.g. PsychoCounsel) for private, on-device generation.
- **Data**: Supabase for user profiles, conversations, and messages (configurable via environment variables).

## Getting Started

1. Install Python dependencies from `requirements.txt`.
2. Set up a `.env` file with your Supabase and Pinecone credentials (and any other required keys).
3. Run Ollama and load the therapy model (e.g. PsychoCounsel).
4. Start the backend API and the frontend (see `start.bat` / `start.sh` for your environment).

For detailed setup, refer to the project’s environment and run scripts in the repo.

## License

See the repository for license and contribution details.

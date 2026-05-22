# AccessFix

AccessFix is an automated pipeline that uses LLMs and RAG (Retrieval-Augmented Generation) to detect and fix WCAG accessibility violations. It features an **Agentic Feedback Loop** that rescans corrected HTML to ensure compliance.

## Repository Structure

```text
/SPL_3
  /backend          <-- Shared logic & API
    engine.py       <-- The unified AI Engine
    llm_functions.py <-- Dynamic RAG handler
    main.py         <-- FastAPI Server
  /frontend         <-- Angular web interface
  /tests            <-- Playwright scripts
  /data             <-- HTML storage
  currentTool.py    <-- CLI Entry Point
  playwright.config.ts
  package.json
  requirements.txt
```

## Setup

### 1. Prerequisites
- Python 3.10+
- Node.js (for Playwright)
- [Ollama](https://ollama.com/) (running `codegemma:latest` and `mxbai-embed-large`)

### 2. Installation
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Playwright
npm install
npx playwright install
```

## Running AccessFix

### Option A: CLI Mode
Run the tool directly from your terminal:
```bash
python currentTool.py
```

### Option B: Web/API Mode
Start the FastAPI backend:
```bash
# From the root directory
uvicorn backend.main:app --reload
```
Then start the Angular frontend:
```bash
cd frontend
npm install
npm start
```

# AccessFix: Agentic Accessibility Engine

AccessFix is an automated pipeline that uses LLMs and RAG (Retrieval-Augmented Generation) to detect and fix WCAG accessibility violations. It features an **Agentic Feedback Loop** that rescans corrected HTML to ensure compliance.

## 📁 Repository Structure

```text
/SPL_3
  /backend          <-- Shared logic & API
    engine.py       <-- The unified AI Engine (Shared by CLI & API)
    llm_functions.py <-- LLM/RAG handler
    main.py         <-- FastAPI Server
    wcag.json       <-- WCAG knowledge base
  /frontend         <-- Angular web interface
  /tests            <-- Playwright scripts
  /data             <-- HTML storage
  currentTool.py    <-- CLI Entry Point
  playwright.config.ts
  package.json
  requirements.txt
```

## 🛠️ Setup

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

### 3. Environment
Create a `.env` file in the root:
```env
OPENAI_API_KEY=your_key_here  # Optional if not using Ollama
```

## 🚀 Running AccessFix

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

## 🧠 Methodology
For a deep dive into the AI architecture, RAG retrieval, and Agentic Loop, see [methodology.md](./methodology.md).

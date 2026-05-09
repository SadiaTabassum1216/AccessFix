# AccessFix: Automated Accessibility Validator

AccessFix is an automated pipeline that detects and automatically fixes web accessibility (WCAG) violations using Large Language Models (LLMs). The project features an Angular frontend for user interaction and a FastAPI/Playwright Python backend for execution.

## Project Structure
- `frontend/`: Angular-based user interface.
- `backend/`: FastAPI server that handles accessibility code scans using Playwright and LLMs via `fixation.py`.
- `currentTool.py`: Standalone Python script for headless URL scanning and CLI-based pipeline execution.

---

## 🚀 Backend Setup (FastAPI & Playwright)

The backend runs on Python and uses FastAPI to serve endpoints. It requires Playwright for headless browser testing and `ollama` or `openai` for generating the accessibility fixes.

### 1. Navigate to the backend directory
```powershell
cd backend
```

### 2. Set up a virtual environment (Recommended)
```powershell
python -m venv venv
# Activate the virtual environment
.\venv\Scripts\activate
```

### 3. Install Python dependencies
```powershell
pip install -r requirements.txt
```

### 4. Install Playwright Browsers
Playwright requires local browser binaries to run the `axe-core` accessibility scans.
```powershell
npx playwright install
```

### 5. Start the Backend Server
```powershell
uvicorn main:app --reload
```
The backend API will be available at `http://127.0.0.1:8000`.

---

## 💻 Frontend Setup (Angular)

The frontend is built with Angular 16 and TailwindCSS.

### 1. Navigate to the frontend directory
```powershell
cd frontend
```

### 2. Install Node dependencies
```powershell
npm install
```

### 3. Start the Development Server
```powershell
npm start
```
The frontend application will be available at `http://localhost:4200`.

---

## 🛠️ Standalone CLI Execution (Optional)

If you wish to run the entire pipeline directly via command line without the UI, you can use the `currentTool.py` script located in the root directory.

```powershell
# Ensure you have your Python virtual environment activated
python currentTool.py
```

### Configuring Models
By default, the pipeline uses local LLMs via Ollama (`codegemma:latest`). You can edit `currentTool.py` to point to OpenAI models if preferred.

```python
# In currentTool.py
self.gpt_functions = LLMFunctions(provider='openai', model='gpt-4o-mini')
```

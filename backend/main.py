from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any
import os
from backend.engine import AccessFixEngine

app = FastAPI()
engine = AccessFixEngine()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CodeAnalysisRequest(BaseModel):
    code: str

class UrlAnalysisRequest(BaseModel):
    url: str

def _run_analysis(html_source: str | None, file_path: str) -> dict[str, Any]:
    """Shared analysis logic for all endpoints.
    
    Args:
        html_source: URL or None if using file_path directly
        file_path: Path to HTML file
        
    Returns:
        Analysis results dict with scores and violations
    """
    initial_score, result_df = engine.run_agentic_loop(html_source, file_path)
    final_score = engine.calculate_severity_score(result_df, 'finalScore')
    improvement = ((1 - (final_score / initial_score)) * 100) if initial_score > 0 else 0
    
    result = {
        "total_initial_severity_score": float(initial_score),
        "total_final_severity_score": float(final_score),
        "total_improvement": float(improvement),
        "violations": result_df.to_dict(orient='records')
    }
    
    # Add corrected HTML if available
    if os.path.exists('data/corrected.html'):
        with open('data/corrected.html', 'r', encoding='utf-8') as f:
            result["corrected_html"] = f.read()
    
    return result

@app.post("/analyzeCode")
async def analyze_code(request: CodeAnalysisRequest):
    """Analyze HTML code provided directly."""
    try:
        path = os.path.join('data', 'input.html')
        os.makedirs('data', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(request.code)
        return _run_analysis(None, path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyzeUrl")
async def analyze_url(request: UrlAnalysisRequest):
    """Analyze HTML from URL."""
    try:
        path = os.path.join('data', 'input.html')
        return _run_analysis(request.url, path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyzeFile")
async def analyze_file(file: UploadFile = File(...)):
    """Analyze HTML uploaded as file."""
    try:
        content = await file.read()
        path = os.path.join('data', 'input.html')
        os.makedirs('data', exist_ok=True)
        with open(path, 'wb') as f:
            f.write(content)
        return _run_analysis(None, path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
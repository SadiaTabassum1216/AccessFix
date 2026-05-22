

## Methodology

### 1. Retrieval (Dynamic RAG)
When a violation is detected (e.g., by Playwright), it comes with a **Success Criterion ID** (e.g., `1.1.1`).
- **Search Target**: The system performs a direct lookup in `wcag_enriched.json` using the ID.
- **Retrieved Content**: 
    - **Rule Text**: The official description of the requirement.
    - **Dynamic Examples**: Authentic W3C code snippets showing how to properly implement the fix.
- **Inclusion**: These snippets are injected into the prompt as "Sufficient Techniques," giving the LLM a standard-compliant template to follow.

### 2. Prompt Architecture
The system uses a highly structured prompt to minimize hallucinations. The skeleton looks like this:

```text
SYSTEM: You are an expert Web Accessibility Engineer.
CONTEXT: [Parent DOM snippet for hierarchy awareness]
RULE: [Text retrieved via RAG for SC 1.1.1]
EXAMPLES: [Official W3C Techniques retrieved via RAG]
TARGET CODE: [The specific HTML element that is failing]

INSTRUCTION: Output a JSON object containing the patch. 
Format: {"selector": "...", "action": "replace", "new_content": "..."}
```

### 3. LLM Output & Integration
The LLM (e.g., `codegemma`) does NOT output free-form code. It must output a **JSON Patch**.
- **The Action**: Usually `replace` or `append_child`.
- **Integration**: The `AccessFixEngine` uses **BeautifulSoup** to locate the element via the CSS selector and apply the `new_content`. This ensures that only the violating element is changed, preserving the rest of the page's integrity.

### 4. Error Calculation & Verification
The system measures success through an **Agentic Feedback Loop**:
- **Initial Error Count**: A baseline Playwright/Axe-core scan of the original HTML.
- **Remediation**: The engine applies the fixes.
- **Final Error Count**: The engine performs a **Rescan** of the modified HTML.
- **Success Metric**: `(Initial Errors - Final Errors) / Initial Errors`. 

If the rescan shows new or remaining errors, the system can perform another "pass" by sending the new error log back to the LLM for self-correction.

### 5. The Scanning Layer: Playwright + Axe-core
The system uses Playwright to render the DOM and `axe-core` to perform the accessibility audit. 

**What Playwright Provides:**
- **Dynamic Rendering**: Handles JavaScript-heavy pages (React, Angular, etc.) to ensure the "computed" DOM is scanned.
- **Structured Violation Output**: Axe-core returns a list of violations. A single violation object looks like this:

```json
{
  "id": "color-contrast",
  "impact": "serious",
  "description": "Ensures contrast between foreground and background colors meets WCAG 2 AA thresholds.",
  "help": "Elements must have sufficient color contrast",
  "nodes": [
    {
      "target": ["#submit-btn"], 
      "html": "<button id='submit-btn' style='color: #fff; background: #eee'>Submit</button>",
      "failureSummary": "Element has insufficient color contrast of 1.22 (Expected 4.5:1)"
    }
  ]
}
```

**How this is used:**
### 6. Hybrid Retrieval Strategy
The system does not rely on a single search method. It uses a **Hybrid RAG** approach to find the best possible context:
- **Direct Mapping (Success Criterion ID)**: Uses the exact WCAG ID (e.g., `1.1.1`) to pull the authoritative rule text and W3C techniques. This ensures the "Ground Truth" is always present.
- **Semantic Search (Vector DB)**: Uses ChromaDB to find similar *past* violations or manual few-shot examples. This is useful for complex layout issues where the "Rule" is clear but the "Implementation" is tricky.

### 7. Context Truncation & Token Management
To prevent "Context Overflow" and keep the LLM focused, the engine performs **Intelligent Pruning**:
- **Target Selection**: Only the failing node and its immediate parent hierarchy (up to 3 levels) are extracted.
- **Sibling Pruning**: Irrelevant siblings of the failing node are removed from the snippet.
- **Example**: If a single `<img>` in a massive `<div>` is failing, the LLM only sees the `<div>` and the specific `<img>`, not the entire 1000-line page.

### 8. Agentic Self-Correction (The Feedback Loop)
This is the "Agentic" heart of the system. If a fix fails the rescan, the system initiates a **Reflection Cycle**:

1.  **Pass 1**: LLM proposes a fix (e.g., adds `alt=""`).
2.  **Verification**: Playwright rescans. If it finds the `alt` is still missing or invalid (e.g., "alt text cannot be a filename"), it logs a **Correction Failure**.
3.  **Reflection**: The engine sends the **Original Code + Failed Patch + New Error Message** back to the LLM.
4.  **Pass 2**: The LLM analyzes *why* the first fix failed and proposes a refined version (e.g., `alt="Description of image"`).

**Example Retry Prompt Snippet:**
> "Your previous attempt `alt='logo.png'` failed because 'alt text must not contain file extensions'. Please provide a descriptive text alternative instead."

## Pipeline details (concise)

- **Scan**: Playwright + `axe-core` generates violation list and node selectors.
- **Context extraction**: Parent-node HTML is extracted via BeautifulSoup (truncated to relevant length).
- **RAG**: Create an embedding for the violation description, query ChromaDB, and select top matches plus code examples from `wcag_examples.json`.
- **Prompt assembly**: Combine parent context, RAG results, and any previous retry history into a strict system + user prompt enforcing JSON output.
- **LLM**: The model returns one structured patch object (e.g., `modify_attributes` or `replace_html`).
- **Apply**: Patches are applied to the in-memory DOM using BeautifulSoup; corrections are saved to `data/corrected.html`.
- **Rescan**: The corrected HTML is rescanned to validate the fix; if not resolved, the failure is fed back for up to 3 iterations.

---

## Implementation notes & current defaults

- **Vector DB**: ChromaDB (local).
- **Embedding model**: `mxbai-embed-large` via Ollama (configured in `backend/llm_functions.py`).
- **LLM calls**: Dispatched concurrently via `ThreadPoolExecutor` from within `backend.engine`.
- **Caching**: Identical violations are cached in-memory per-run to avoid duplicate LLM calls.

---

## Maintenance & contribution checklist

- Update `wcag.json` for canonical text changes.
- Add concrete examples to `wcag_examples.json` when new patterns are identified.
- If embedding model or ChromaDB schema changes, update `backend/llm_functions.py` and `backend/engine.py` accordingly.
- Run `python -m pytest` or Playwright tests in `tests/` after modifying the engine.

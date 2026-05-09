# AccessFix Methodology

This document outlines the underlying methodology, architecture, and prompt engineering strategies used by the automated accessibility validator pipeline.

## 1. Pipeline Structure

The pipeline is designed to be highly parallelized and resilient, ensuring fast execution times and robust DOM manipulation.

### Step-by-Step Execution Flow:
1. **Input Reception**: The pipeline accepts either a live URL (which is scraped using Playwright) or raw HTML code (either pasted or uploaded via document formats).
2. **Baseline Accessibility Scan**: The raw HTML is loaded into a headless Playwright browser. The `axe-core` library analyzes the DOM and outputs a list of all WCAG violations, including impact severity, CSS target selectors, and descriptive error messages.
3. **DOM Context Extraction**: Instead of naively sending isolated HTML tags to the LLM, the pipeline parses the full DOM using `BeautifulSoup`. It uses the `axe-core` CSS selector to locate the exact violated node and extracts up to 1000 characters of its **Parent Node**.
4. **Retrieval-Augmented Generation (RAG)**: If enabled, the pipeline queries a local vector database to retrieve the official WCAG guidelines relevant to the specific violation.
5. **Parallel LLM Execution**: The violation details, parent context, and RAG guidelines are compiled into a prompt. A `ThreadPoolExecutor` dispatches multiple concurrent requests to the LLM (OpenAI or local Ollama), significantly accelerating the correction phase. 
6. **In-Memory Caching**: Identical violations (same HTML, same issue, same context) are cached in a dictionary. Subsequent encounters instantly return the cached fix without triggering an LLM API call.
7. **Robust DOM Injection**: The LLM's corrected HTML is parsed via `BeautifulSoup` and securely injected back into the DOM tree at the exact node location, preventing accidental substring replacement errors.
8. **Validation Scan**: The corrected DOM is rescanned by `axe-core` in Playwright. Severity scores are compared to calculate the total percentage improvement.

---

## 2. RAG (Retrieval-Augmented Generation) Structure

The RAG pipeline provides the LLM with authoritative context, grounding its fixes in official accessibility standards.

* **Document Corpus**: A structured `wcag.json` file containing WCAG success criteria, levels (A, AA, AAA), and descriptions.
* **Vector Database**: `ChromaDB` running locally.
* **Embedding Model**: `mxbai-embed-large` (via Ollama) is used to convert the text documents into dense vector embeddings.
* **Retrieval Strategy**: 
    * Rather than asking a conversational question, the system queries the database using a **semantic statement** combining the specific Issue Description and the Suggested Help text. 
    * The database performs a cosine-similarity search and retrieves the **Top 3** most relevant WCAG guidelines. 
    * **All 3 guidelines** are injected into the prompt, giving the LLM a comprehensive understanding of the accessibility rules it must follow.

---

## 3. Prompt Structure

The prompt is dynamically constructed for every single violation. It utilizes a **few-shot prompting** technique with dynamic context injection to maximize the LLM's accuracy.

### System Prompt
The System Prompt sets the persona and provides hardcoded examples of common accessibility fixes (e.g., empty heading tags, missing image alt text, empty links).

### User Prompt
The User Prompt is dynamically generated using 4 primary variables:

1. **Context (Parent Node)**: The surrounding HTML structure, allowing the LLM to understand how the broken element fits into the larger page.
2. **Relevant WCAG Guidelines**: The 3 guidelines retrieved by the RAG system.
3. **Incorrect HTML**: The exact string of broken HTML flagged by `axe-core`.
4. **Issue & Suggested Change**: The natural language description and hint provided by the `axe-core` engine.

### Example Prompt Output

```text
Provide a correction for the following HTML to fix the accessibility issue. 
Only output the corrected HTML code. Do not add conversational filler.

Context (Parent Node): <nav class="sidebar"> <ul> <li> <a href="#" class="icon-link"></a> </li> </ul> </nav>
        
Relevant WCAG Guidelines:
WCAG: 2.4.4 : Level-A - Link Purpose (In Context) - The purpose of each link can be determined from the link text alone...
WCAG: 1.1.1 : Level-A - Non-text Content - All non-text content that is presented to the user has a text alternative...

Incorrect: <a href="#" class="icon-link"></a>
Issue: Links must have discernible text.
Suggested change: Provide text that describes the purpose of the link.
```

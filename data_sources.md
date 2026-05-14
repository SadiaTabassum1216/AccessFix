# Data Source Documentation: Dynamic Accessibility Remediation

This document describes the data architecture for the accessibility remediation engine. The system utilizes a **Dynamic Retrieval-Augmented Generation (RAG)** approach to provide context-specific code examples to the LLM.

## 1. Primary Knowledge Source (Authentic)

### **Enriched WCAG Dataset (`wcag_enriched.json`)**
- **Nature:** High-Fidelity Knowledge Base.
- **Source:** [W3C WCAG 2.2 Understanding Pages](https://www.w3.org/WAI/WCAG22/Understanding/).
- **Methodology:** An automated pipeline (`enrich_wcag.py`) crawls the official "Understanding" page for every Success Criterion. It identifies linked **Sufficient Techniques** and **Common Failures** and extracts raw `<pre>` code blocks directly from the W3C repository.
- **Content:** 
    - Full text and metadata for 87 Success Criteria.
    - `dynamic_examples`: A curated list of real-world code snippets (Authentic examples).
- **Authenticity:** **High**. All code examples are sourced directly from the World Wide Web Consortium (W3C).

## 2. Supporting Datasets

### **Core Guidelines (`wcag.json`)**
- **Source:** [WCAG 2.2 Recommendation](https://www.w3.org/TR/WCAG22/).
- **Role:** Provides the structural baseline (Principles, Guidelines, and Success Criteria) used as the skeleton for the enrichment process.

### **Manual Fallback (`wcag_examples.json`)**
- **Nature:** Curated Dataset.
- **Role:** Provides high-quality, hand-verified "Fix" pairs for common violations. Used as a secondary fallback if the dynamic scraping pipeline is unable to find a specific technique.
- **Authenticity:** **Expert-Curated**.

## 3. Data Architecture Overview

| Data Layer | Primary File | Collection Method | Data Type |
| :--- | :--- | :--- | :--- |
| **Knowledge Base** | `wcag_enriched.json` | Automated Scraping (W3C) | Authentic Code |
| **Guidelines** | `wcag.json` | JSON Export (W3C TR) | Textual Rules |
| **Few-Shot Library** | `wcag_examples.json` | Manual Curation | Synthetic/Expert |
| **Evaluation** | `test_cases.json` | Benchmark Suite | Real-world violations |

## 4. Pipeline Logic
1. **Violation Detected**: The system identifies a specific WCAG ID (e.g., `1.1.1`).
2. **Dynamic Retrieval**: The engine queries `wcag_enriched.json` for the specific ID.
3. **Context Injection**: The `dynamic_examples` (real W3C code) are injected into the LLM prompt.
4. **Remediation**: The LLM uses these official "Sufficient Techniques" as a direct template for patching the user's code, significantly reducing hallucinations.

---
*Note: Redundant operational files (wcag_urls.json, wcag_url_batches.json) have been deprecated in favor of this direct-to-Understanding scraping model.*

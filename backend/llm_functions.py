import os
import pandas as pd
import re
# pyrefly: ignore [missing-import]
import ollama
import openai
import json
from .reranker import CrossEncoderReranker

try:
    import chromadb
except ImportError:
    chromadb = None

class LLMFunctions:
    def __init__(self, provider='ollama', model='codegemma:latest', use_rag=False):
        self.provider = provider
        self.model = model
        self.use_rag = use_rag
        
        # Load or create CSV file for violation tracking
        # Default to backend path; fallback to legacy path for compatibility
        self.csv_path = self._find_or_create_violations_csv()
        self.df = pd.read_csv(self.csv_path)
        self.cache = {}

        if self.use_rag:
            if chromadb is None:
                raise ImportError("chromadb is required for RAG but not installed")
            self.client = chromadb.Client()
            try:
                self.collection = self.client.get_collection(name="wcag_docs")
            except Exception:
                self.collection = self.client.create_collection(name="wcag_docs")
            
            # Locate wcag.json relative to this file
            base_dir = os.path.dirname(os.path.abspath(__file__))
            # Use enriched data if available, otherwise fallback to standard
            enriched_path = os.path.join(base_dir, 'wcag_enriched.json')
            standard_path = os.path.join(base_dir, 'wcag.json')
            
            wcag_path = enriched_path if os.path.exists(enriched_path) else standard_path
            
            if os.path.exists(wcag_path):
                with open(wcag_path, 'r', encoding='utf-8') as f:
                    self.wcag_data = json.load(f)
                
                # Create a map for fast SC lookup
                self.sc_map = {}
                for item in self.wcag_data:
                    for guideline in item['guidelines']:
                        for sc in guideline.get('success_criteria', []):
                            self.sc_map[sc['ref_id']] = sc
                
                self.populate_collection()
            else:
                print(f"Warning: RAG enabled but {wcag_path} not found. Proceeding without RAG.")
                self.use_rag = False
                self.sc_map = {}

            # Supplementary examples (fallback)
            examples_path = os.path.join(base_dir, 'wcag_examples.json')
            if os.path.exists(examples_path):
                with open(examples_path, 'r', encoding='utf-8') as f:
                    self.wcag_examples = json.load(f)
            else:
                self.wcag_examples = {}
                
            self.reranker = CrossEncoderReranker()

    def _find_or_create_violations_csv(self):
        """Find or create CSV file for storing violation records.
        
        Checks for existing CSV files in priority order:
        1. violationResult.csv (backend standard)
        2. violationsWithFixedContent.csv (legacy path)
        Creates default CSV if none exists.
        """
        csv_candidates = ["violationResult.csv", "violationsWithFixedContent.csv"]
        for candidate in csv_candidates:
            if os.path.exists(candidate):
                return candidate
        
        # Create default CSV if none exists
        default_path = csv_candidates[0]
        with open(default_path, "w") as f:
            f.write("id,impact,tags,description,help,helpUrl,nodeImpact,nodeHtml,nodeTarget,nodeType,message,numViolation\n")
        return default_path

    def populate_collection(self):
        existing_ids = set(self.collection.get()['ids'])
        
        for item in self.wcag_data:
            for guideline in item['guidelines']:
                for criterion in guideline.get('success_criteria', []):
                    ref_id = criterion['ref_id']
                    if ref_id in existing_ids:
                        continue
                    
                    existing_ids.add(ref_id)
                    doc = f"WCAG: {ref_id} : Level-{criterion['level']} - {criterion['title']} - {criterion['description']}\n"
                    
                    response = ollama.embeddings(model="mxbai-embed-large", prompt=doc)
                    embedding = response["embedding"]
                    
                    self.collection.add(
                        ids=[ref_id],
                        embeddings=[embedding],
                        documents=[doc]
                    )

    def GPT_response(self, system, user, row_index):
        print(f"\n...................................... Call : {row_index}...............................................")

        if self.provider == 'openai':
            response = openai.chat.completions.create(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': system},
                    {'role': 'user', 'content': user}
                ]
            )
            return response.choices[0].message.content
            
        elif self.provider == 'ollama':
            prompt = [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
            response = ollama.chat(model=self.model, messages=prompt)
            return response["message"]["content"]
            
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def generate_prompt(self, row_index, context_html=None, rag_guidelines=None, previous_failure=None, dynamic_examples=None):
        system_msg = """You are an expert web accessibility developer. Your task is to fix HTML accessibility violations.
You MUST output your fix as a strict JSON object. Do not include markdown formatting like ```json or any conversational text.

If you can fix the issue by simply adding, modifying, or removing attributes on the target node, use the "modify_attributes" action. 
This is the safest method.
{
  "action": "modify_attributes",
  "attributes": {"alt": "A descriptive alt text", "aria-label": "Navigation menu"}
}

If the issue requires structural changes (like changing the tag name, or wrapping the content), use the "replace_html" action.
{
  "action": "replace_html",
  "html": "<button type='button'>Click me</button>"
}
"""

        context_str = f"\nContext (Parent Node): {context_html}" if context_html else ""
        rag_str = f"\nRelevant WCAG Guidelines:\n{rag_guidelines}" if rag_guidelines else ""
        example_str = f"\nWCAG Code Examples:\n{dynamic_examples}" if dynamic_examples else ""
        
        failure_str = f"\nWARNING: Your previous attempt failed to fix the issue. Previous attempt: {previous_failure}\nPlease try a different approach." if previous_failure else ""

        # Use help field if available (it acts as suggested change)
        help_str = ""
        if 'help' in self.df.columns and pd.notna(self.df['help'][row_index]):
            help_str = f"\nSuggested change: {self.df['help'][row_index]}"

        user_msg = f"""
Provide a JSON correction for the following HTML to fix the accessibility issue.
{context_str}
{rag_str}
{example_str}
{failure_str}

Incorrect HTML: {self.df['nodeHtml'][row_index]}
Issue: {self.df['description'][row_index]}{help_str}
"""
        return system_msg, user_msg

    def get_correction(self, row_index, context_html=None, previous_failure=None):
        node_html = self.df["nodeHtml"][row_index]
        issue_desc = self.df["description"][row_index]
        help_text = self.df["help"][row_index] if 'help' in self.df.columns else ""
        
        rag_guidelines = None
        dynamic_examples = ""
        
        if self.use_rag:
            # Semantic query instead of question
            query_prompt = f"Issue: {issue_desc}. Suggestion: {help_text}"
            
            response = ollama.embeddings(
                prompt=query_prompt, 
                model="mxbai-embed-large"
            )
            results = self.collection.query(
                query_embeddings=[response["embedding"]], n_results=10
            )
            
            # Rerank retrieved documents
            if results["documents"] and results["documents"][0]:
                reranked_docs = self.reranker.rerank(query_prompt, results["documents"][0], top_k=3)
                rag_guidelines = "\n".join(reranked_docs)
                
                # Check for dynamic examples in enriched data
                for doc in reranked_docs:
                    match = re.search(r"WCAG: (\d+\.\d+\.\d+) :", doc)
                    if match:
                        ref_id = match.group(1)
                        # Priority 1: Enriched dynamic examples from scraping
                        if ref_id in self.sc_map and self.sc_map[ref_id].get('dynamic_examples'):
                            for ex in self.sc_map[ref_id]['dynamic_examples'][:2]: # Take top 2
                                dynamic_examples += f"Example for {ref_id} ({ex['title']}):\n{ex['description']}\nCode:\n{ex['code']}\n\n"
                        # Priority 2: Hardcoded examples (fallback)
                        elif ref_id in self.wcag_examples:
                            ex = self.wcag_examples[ref_id]
                            dynamic_examples += f"Rule {ref_id} ({ex['title']}):\nBad: {ex['bad_code']}\nGood: {ex['good_code']}\n\n"

        cache_key = (node_html, issue_desc, context_html, rag_guidelines, previous_failure)

        if cache_key in self.cache:
            print(f"Using cached correction for row {row_index}")
            return self.cache[cache_key]

        system_msg, user_msg = self.generate_prompt(row_index, context_html, rag_guidelines, previous_failure, dynamic_examples)
        response = self.GPT_response(system_msg, user_msg, row_index)
        print("LLM JSON Response:", response)

        # Clean JSON markdown if the LLM hallucinated it
        correction = response.strip()
        if correction.startswith("```json"):
            correction = correction[7:]
        elif correction.startswith("```"):
            correction = correction[3:]
        if correction.endswith("```"):
            correction = correction[:-3]
        correction = correction.strip()
        
        try:
            parsed_json = json.loads(correction)
            self.cache[cache_key] = parsed_json
            return parsed_json
        except json.JSONDecodeError:
            print(f"Failed to parse JSON from LLM: {correction}")
            # Fallback format
            fallback = {"action": "replace_html", "html": node_html}
            self.cache[cache_key] = fallback
            return fallback

        # Optional: Save guideline details like backend used to do
        if self.use_rag and rag_guidelines:
            # We just take the top one for reference tracking
            top_guideline = results["documents"][0][0] if results["documents"][0] else ""
            pattern = r"WCAG: (\S+) : Level-(\S+) - (.*?) -"
            match = re.search(pattern, top_guideline)
            if match:
                ref, level, description = match.groups()
                self.store_guideline_details(row_index, node_html, issue_desc, correction, ref, level, description)

        return correction if correction else node_html

    def store_guideline_details(self, index: int, errorCode: str, error: str, fix: str, ref: str, level: str, description: str):
        data_folder = 'data'
        if not os.path.exists(data_folder):
            os.makedirs(data_folder)
        
        csv_file_path = os.path.join(data_folder, 'guideline_details.csv')
        data = {
            'index': index,
            "errorCode": errorCode,
            'error': error,
            'fix': fix,
            'reference': ref,
            'level': level,
            'description': description
        }
        df = pd.DataFrame([data])
        df.to_csv(csv_file_path, mode='a', header=not os.path.exists(csv_file_path), index=False)

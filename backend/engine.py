import pandas as pd
import os
import platform
import time
import glob
import subprocess
from dotenv import load_dotenv
from backend.llm_functions import LLMFunctions
from backend.web_scrapper_and_file_handler import fetch_and_save_data

def run_playwright_test():
    """Run Playwright tests for accessibility scanning."""
    try:
        env = os.environ.copy()
        env['CI'] = '1'
        subprocess.run('npx playwright test', shell=True, check=True, env=env)
    except subprocess.CalledProcessError as e:
        print(f"Error running Playwright test: {e}")

class AccessFixEngine:
    def __init__(self):
        load_dotenv()
        self.gpt_functions = LLMFunctions(provider='ollama', model='codegemma:latest', use_rag=True)
        
        # Centralized temp directory
        self.temp_dir = 'temp'
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Temporary violation file path
        self.violations_csv = os.path.join(self.temp_dir, 'violations.csv')
        
        if not os.path.exists(self.violations_csv):
            with open(self.violations_csv, 'w') as file:
                file.write('id,impact,tags,description,help,helpUrl,nodeImpact,nodeHtml,nodeTarget,nodeType,message,numViolation\n')
        
        self.input_df = pd.read_csv(self.violations_csv)

    def compute_severity_score_column(self, df, column_name, insert_index):
        """Compute severity scores from impact ratings and insert into dataframe."""
        impact_values = {
            'critical': 5, 'serious': 4, 'moderate': 3, 'minor': 2, 'cosmetic': 1,
        }
        df['impactValue'] = df['impact'].map(impact_values)
        if column_name in df.columns:
            df.drop(columns=[column_name], inplace=True)
        df.insert(insert_index, column_name, df['impactValue'])
        df.drop(columns='impactValue', inplace=True)
        return df

    def calculate_severity_score(self, df, score_col):
        if df.empty or df.iloc[0]['id'] == 'None':
            return 0
        return df[score_col].sum()

    def _process_violation(self, index, row, dom_soup, failed_fixes):
        error_html = row['nodeHtml']
        target_selector = str(row['nodeTarget']).split('|')[0] if pd.notna(row['nodeTarget']) else ""
        
        context_html = None
        if target_selector:
            try:
                node = dom_soup.select_one(target_selector)
                if node and node.parent:
                    context_html = str(node.parent)[:1000] 
            except:
                pass
        
        previous_failure = failed_fixes.get(target_selector, None)
        fix_json = self.gpt_functions.get_correction(index, context_html=context_html, previous_failure=previous_failure)
        return index, target_selector, error_html, fix_json

    def apply_fixes_to_dom(self, dom, failed_fixes):
        from bs4 import BeautifulSoup
        import concurrent.futures
        
        # Keep LLM row lookups aligned with the current violation dataframe.
        self.input_df = self.input_df.reset_index(drop=True)
        self.gpt_functions.df = self.input_df

        soup = BeautifulSoup(dom, 'html.parser')
        results = []
        attempted_fixes = {}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_index = {
                executor.submit(self._process_violation, index, row, soup, failed_fixes): index
                for index, row in self.input_df.iterrows()
            }
            for future in concurrent.futures.as_completed(future_to_index):
                results.append(future.result())
                
        for index, target_selector, error_html, fix_json in results:
            if not isinstance(fix_json, dict): continue
            attempted_fixes[target_selector] = fix_json
                
            if target_selector:
                try:
                    node = soup.select_one(target_selector)
                    if node:
                        action = fix_json.get("action", "")
                        if action == "modify_attributes" and "attributes" in fix_json:
                            for attr, val in fix_json["attributes"].items():
                                node[attr] = val
                        elif action == "replace_html" and "html" in fix_json:
                            new_node = BeautifulSoup(fix_json["html"], 'html.parser')
                            node.replace_with(new_node)
                except Exception as e:
                    print(f"Error applying fix to {target_selector}: {e}")

        corrected_dom = str(soup)
        self.input_df['DOMCorrected'] = corrected_dom
        return corrected_dom, attempted_fixes

    def create_test_script(self, path, is_before=True):
        script_name = "before.spec.ts" if is_before else "after.spec.ts"

        # Temp directory may be removed at the end of a prior case.
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Ensure paths use forward slashes for the generated JS script
        output_csv = os.path.join(self.temp_dir, "violations_before.csv" if is_before else "violations_after.csv").replace("\\", "/")
        num_file = os.path.join(self.temp_dir, "num_v1.txt" if is_before else "num_v2.txt").replace("\\", "/")
        
        with open(path, 'r', encoding='utf-8') as text_file:
            dom = text_file.read()

        # Escape characters that would break JS template literals in generated tests.
        escaped_dom = dom.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")

        test_script_path = os.path.join("tests", script_name)
        os.makedirs("tests", exist_ok=True)
        
        with open(test_script_path, "w", encoding='utf-8') as f:
            f.write(f"""
                const {{ test }} = require('@playwright/test');
                const AxeBuilder = require('@axe-core/playwright').default;
                const fs = require('fs');

                function escapeCSV(v) {{
                    if (typeof v === 'string') {{
                        v = v.replace(/"/g, '""');
                        if (v.includes(',') || v.includes('\\n') || v.includes('\\r') || v.includes('"')) return `"${{v}}"`;
                    }}
                    return v;
                }}

                function toCSV(violations) {{
                    const h = ['id', 'impact', 'tags', 'description', 'help', 'helpUrl', 'nodeImpact', 'nodeHtml', 'nodeTarget', 'nodeType', 'message', 'numViolation'];
                    let csv = h.join(',') + '\\n';
                    violations.forEach(v => {{
                        v.nodes.forEach(n => {{
                            ['any', 'all', 'none'].forEach(t => {{
                                if (n[t] && n[t].length > 0) {{
                                    n[t].forEach(c => {{
                                        csv += [v.id, v.impact, v.tags.join('|'), v.description, v.help, v.helpUrl, c.impact || '', n.html, n.target.join('|'), t, c.message, violations.length].map(escapeCSV).join(',') + '\\n';
                                    }});
                                }}
                            }});
                        }});
                    }});
                    return csv;
                }}

                test('scan', async ({{ page }}) => {{
                    await page.setContent(`{escaped_dom}`);
                    const results = await new AxeBuilder({{ page }}).analyze();
                    fs.writeFileSync("{output_csv}", toCSV(results.violations));
                    fs.writeFileSync("{num_file}", String(results.violations.length));
                }});
            """)
        run_playwright_test()

    def corrections2violations(self, corrected_dom):
        # Temporary file for scanning
        temp_path = "temp_scan.html"
        with open(temp_path, "w", encoding='utf-8') as f:
            f.write(corrected_dom)
        
        self.create_test_script(temp_path, is_before=False)
        
        num_v2_path = os.path.join(self.temp_dir, "num_v2.txt")
        violations_after_path = os.path.join(self.temp_dir, "violations_after.csv")
        
        length = 0
        if os.path.exists(num_v2_path):
            with open(num_v2_path, "r") as f:
                length = int(f.readline().strip())

        if length > 0 and os.path.exists(violations_after_path):
            new_df = pd.read_csv(violations_after_path)
        else:
            new_df = pd.DataFrame({'id': ['None'], 'impact': ['None'], 'tags': ['None'], 'description': ['None'], 'help': ['None'], 'helpUrl': ['None'], 'nodeImpact': ['None'], 'nodeHtml': ['None'], 'nodeTarget': ['None'], 'nodeType': ['None'], 'message': ['None'], 'numViolation': [0]})

        # Cleanup intermediate files
        for f in [num_v2_path, violations_after_path, temp_path]:
            if os.path.exists(f): os.remove(f)

        return self.compute_severity_score_column(new_df, 'finalScore', 3)

    def run_agentic_loop(self, url, path, max_iterations=3):
        print(f"\n--- Starting Agentic Loop for {url} ---")
        if not os.path.exists(path):
            fetch_and_save_data(url, path)
            
        self.create_test_script(path, is_before=True)
        violations_v1 = os.path.join(self.temp_dir, 'violations_before.csv')
        if os.path.exists(violations_v1):
            self.input_df = pd.read_csv(violations_v1)
        self.input_df = self.compute_severity_score_column(self.input_df, 'initialScore', 5)
        initial_score = self.calculate_severity_score(self.input_df, 'initialScore')

        with open(path, 'r', encoding='utf-8') as f:
            current_dom = f.read()

        failed_fixes = {}
        for iteration in range(max_iterations):
            if self.input_df.empty or self.input_df.iloc[0]['id'] == 'None':
                print("All violations resolved!")
                break
                
            print(f"Iteration {iteration+1}/{max_iterations}...")
            current_dom, attempted_fixes = self.apply_fixes_to_dom(current_dom, failed_fixes)
            new_df = self.corrections2violations(current_dom)
            
            failed_fixes = {}
            if not new_df.empty and new_df.iloc[0]['id'] != 'None':
                for _, row in new_df.iterrows():
                    target = str(row['nodeTarget']).split('|')[0] if pd.notna(row['nodeTarget']) else ""
                    if target in attempted_fixes:
                        failed_fixes[target] = attempted_fixes[target]
            
            self.input_df = new_df

        # Save final result
        os.makedirs('data', exist_ok=True)
        with open('data/corrected.html', 'w', encoding='utf-8') as f:
            f.write(current_dom)
            
        # Final cleanup of temp directory
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            
        # Also cleanup root-level artifacts if they exist
        for root_file in ['violationsWithFixedContent.csv', 'num_violations.txt', 'data0.json']:
            if os.path.exists(root_file): os.remove(root_file)

        return initial_score, self.input_df

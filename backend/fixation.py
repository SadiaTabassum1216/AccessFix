import io
from typing import Any, Dict
import json
from fastapi import UploadFile
from bs4 import BeautifulSoup
import pandas as pd
import asyncio
import os
import time
import glob
import subprocess
import numpy as np
from dotenv import load_dotenv
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm_functions import LLMFunctions
from web_scrapper import fetch_and_save_data, save_code_to_path
from file_handler import FileExtractor
import re


def run_playwright_test():
    try:
        env = os.environ.copy()
        env['CI'] = '1'  # Set the CI variable

        subprocess.run('npx playwright test', shell=True, check=True, env=env)
    except subprocess.CalledProcessError as e:
        print(f"Error running Playwright test: {e}")



class CleanGPTModels:
    def __init__(self):
        load_dotenv()
        # self.gpt_functions = LLMFunctions()
        self.file_extractor = FileExtractor()
        self._initialize_violation_file()
        self.input_df = pd.DataFrame()
        csv_guideline_file_path = os.path.join('data', 'guideline_details.csv')
        self.clear_csv_file(csv_guideline_file_path)

    def _initialize_violation_file(self):
        """Initialize or clear the violation result file"""
        headers = 'id,impact,tags,description,help,helpUrl,nodeImpact,nodeHtml,nodeTarget,nodeType,numViolation\n'
        with open('violationResult.csv', 'w') as file:
            file.write(headers)

    def run_playwright_test(self):
        """Run Playwright test and ensure it completes"""
        try:
            env = os.environ.copy()
            env['CI'] = '1'
            result = subprocess.run('npx playwright test', shell=True, check=True, env=env)
            return result.returncode == 0
        except subprocess.CalledProcessError as e:
            print(f"Error running Playwright test: {e}")
            return False

    def wait_for_file(self, file_path, timeout=5):
        """Wait until the file is available or timeout expires"""
        start_time = time.time()
        while not os.path.exists(file_path):
            if time.time() - start_time > timeout:
                raise TimeoutError(f"File '{file_path}' not found within timeout")
            # time.sleep(0.1)
        
    def read_violation_file(self):
        """Read the violation CSV file into DataFrame"""
        try:
            self.input_df = pd.read_csv('violationResult.csv')
        except pd.errors.EmptyDataError:
            print("No violations found in the analysis")
            self.input_df = pd.DataFrame()
        except Exception as e:
            print(f"Error reading violation results: {e}")
            self.input_df = pd.DataFrame()

    def clear_csv_file(self, file_path):
        if os.path.exists(file_path):
            os.remove(file_path)
        # print("CSV file cleared.")



    def create_test_script(self, path):   
        print("Creating the violation file...........")

        # Step 1: Read DOM from the specified path
        try:
            with open(path, 'r', encoding='utf-8') as text_file:
                dom = text_file.read()
        except IOError as e:
            print(f"Error reading file at {path}: {e}")
            return

        # Step 2: Define the Playwright test script
        test_script_content = f"""
        // @ts-check
        const {{ test, expect }} = require('@playwright/test');
        const AxeBuilder = require('@axe-core/playwright').default;
        const fileReader = require('fs');

        function escapeCSV(value) {{
            if (typeof value === 'string') {{
                value = value.replace(/"/g, '""');
                if (value.includes(',') || value.includes('\\n') || value.includes('\\r') || value.includes('"')) {{
                    return `"${{value}}"`;
                }}
            }}
            return value;
        }}

        function violationsToCSV(violations) {{
            const headers = ['id', 'impact', 'tags', 'description', 'help', 'helpUrl', 'nodeImpact', 'nodeHtml', 'nodeTarget', 'nodeType', 'numViolation'];
            const uniqueRows = new Set();
            const totalViolations = violations.length;

            violations.forEach(violation => {{
                violation.nodes.forEach(node => {{
                    const row = [
                        escapeCSV(violation.id),
                        escapeCSV(violation.impact),
                        escapeCSV(violation.tags.join('|')),
                        escapeCSV(violation.description),
                        escapeCSV(violation.help),
                        escapeCSV(violation.helpUrl),
                        escapeCSV(node.any?.[0]?.impact || ''),
                        escapeCSV(node.html),
                        escapeCSV(node.target.join('|')),
                        'any',
                        totalViolations
                    ];
                    uniqueRows.add(row.join(','));
                }});
            }});

            return headers.join(',') + '\\n' + Array.from(uniqueRows).join('\\n');
        }}

        test('accessibility issues', async ({{ page }}) => {{
            await page.setContent(`{dom}`);
            const accessibilityScanResults = await new AxeBuilder({{ page }})
            .analyze();
            const violations = accessibilityScanResults.violations;

            // Write CSV data to file (overwrite mode)
            fileReader.writeFileSync("violationResult.csv", violationsToCSV(violations));
            // Write the number of violations to a file
            fileReader.writeFileSync("num_of_violations.txt", String(violations.length));
        }});
        """
       
        # Step 3: Write the test script content to a .ts file
        test_script_path = "./tests/before.spec.ts"
        try:
            with open(test_script_path, "w", encoding='utf-8') as f:
                f.write(test_script_content)
        except IOError as e:
            print(f"Error writing test script to {test_script_path}: {e}")
            return

        # Step 4: Execute the Playwright test script
        run_playwright_test()
        # time.sleep(0.5)

        # Step 5: Read the new violations after the test
        try:
            self.input_df = pd.read_csv('violationResult.csv')
        except pd.errors.EmptyDataError:
            print("No violations found in the new analysis")
            self.input_df = pd.DataFrame()
        except Exception as e:
            print(f"Error reading violation results: {e}")
            self.input_df = pd.DataFrame()

        # Step 6: Clean up temporary files
        if os.path.exists('num_of_violations.txt'):
            try:
                os.remove('num_of_violations.txt')
            except PermissionError:
                # time.sleep(0.5)
                os.remove('num_of_violations.txt')

    def add_severity_score(self, df, column_name, insert_index):
        impact_values = {
            'critical': 5,
            'serious': 4,
            'moderate': 3,
            'minor': 2,
            'cosmetic': 1,
        }
        df['impactValue'] = df['impact'].map(impact_values)
        df.insert(insert_index, column_name, df['impactValue'])
        df.drop(columns='impactValue', inplace=True)
        return df

    def calculate_severity_score(self, df, score):
        return df[score].sum()

    def _process_violation(self, index, row, dom_soup, failed_fixes):
        error_html = row['nodeHtml']
        target_selector = str(row['nodeTarget']).split('|')[0] if pd.notna(row['nodeTarget']) else ""
        
        context_html = None
        if target_selector:
            try:
                node = dom_soup.select_one(target_selector)
                if node and node.parent:
                    context_html = str(node.parent)[:1000] 
            except Exception as e:
                pass
        
        previous_failure = failed_fixes.get(target_selector, None)
        fix_json = self.gpt_functions.get_correction(index, context_html=context_html, previous_failure=previous_failure)
        return index, target_selector, error_html, fix_json

    def apply_fixes_to_dom(self, dom, failed_fixes):
        import concurrent.futures
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
                
        # Now apply the JSON fixes to the soup
        for index, target_selector, error_html, fix_json in results:
            if not isinstance(fix_json, dict):
                continue
                
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
                    print(f"Error applying JSON fix to {target_selector}: {e}")

        corrected_dom = str(soup)
        self.input_df['DOMCorrected'] = corrected_dom
        self.final_corrected_dom = corrected_dom
        return corrected_dom, attempted_fixes

    def run_agentic_loop(self, path, max_iterations=3):
        print("\n--- Starting Agentic Feedback Loop (Backend) ---")
        self.create_test_script(path)
        self.input_df = self.add_severity_score(self.input_df, 'initialScore', 5)
        
        total_initial_severity_score = self.calculate_severity_score(self.input_df, 'initialScore')
        print(f"Total Initial Violations: {len(self.input_df)}")

        with open(path, 'r', encoding='utf-8') as text_file:
            current_dom = text_file.read()

        failed_fixes = {}
        self.gpt_functions = LLMFunctions(use_rag=True)
        
        for iteration in range(max_iterations):
            if self.input_df.empty or len(self.input_df) == 0 or self.input_df.iloc[0]['id'] == 'None':
                break
                
            current_dom, attempted_fixes = self.apply_fixes_to_dom(current_dom, failed_fixes)
            new_df = self.correction_to_violations(current_dom)
            
            failed_fixes = {}
            if not new_df.empty and new_df.iloc[0]['id'] != 'None':
                for index, row in new_df.iterrows():
                    target = str(row['nodeTarget']).split('|')[0] if pd.notna(row['nodeTarget']) else ""
                    if target in attempted_fixes:
                        failed_fixes[target] = attempted_fixes[target]
            
            self.input_df = new_df

        corrected_path = os.path.join('data', 'corrected.html')
        os.makedirs('data', exist_ok=True)
        with open(corrected_path, 'w', encoding='utf-8') as corrected_file:
            corrected_file.write(current_dom)
            
        return total_initial_severity_score, self.input_df







    def remove_files_starting_with(self, pattern):
        files_to_remove = glob.glob(pattern)
        for file_path in files_to_remove:
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except OSError as e:
                print(f"Error while removing file '{file_path}': {e}")

    def correction_to_violations(self, corrected_dom):
        test_script_path = "./tests/after.spec.ts"
        try:
            with open(test_script_path, "w", encoding='utf-8') as f:
                f.write(f"""
                // @ts-check
                const {{ test, expect }} = require('@playwright/test');
                const AxeBuilder = require('@axe-core/playwright').default;
                const fileReader = require('fs');

                test('all violations', async ({{ page }}) => {{
                    await page.setContent(`{corrected_dom}`)
                    const accessibilityScanResults = await new AxeBuilder({{ page }})
                    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
                    .analyze();
                    const violations = accessibilityScanResults.violations;

                    fileReader.writeFile("num_of_violations.txt", String(violations.length), function(err) {{
                        if (err) console.log(err);
                    }});

                    for (let i = 0; i < violations.length; i++) {{
                        fileReader.writeFile("data" + i + ".json", JSON.stringify(violations[i]), function(err) {{
                            if (err) console.log(err);
                        }});
                    }}
                }});
                """)
        except IOError as e:
            print(f"Failed to write test script: {e}")
            return pd.DataFrame()  # Return an empty DataFrame or handle as needed

        run_playwright_test()

        length = 0
        try:
            if os.path.exists('num_of_violations.txt'):
                with open('num_of_violations.txt', "r") as length_file:
                    length = int(length_file.readline().strip())
        except Exception as e:
            print(f"Error reading num_of_violations.txt: {e}")

        new_df = pd.DataFrame()

        try:
            if length > 0:
                for i in range(length):
                    file_path = f"data{i}.json"
                    if os.path.exists(file_path):
                        with open(file_path, "r", encoding='utf-8') as file:
                            df_temp = pd.read_json(file, lines=True)
                        df_temp = df_temp.reset_index(drop=True)
                        new_df = pd.concat([new_df, df_temp], ignore_index=True)
                    # else:
                    #     print(f"File not found: {file_path}")
                new_df.insert(1, "numViolations", length)
            else:
                df_temp = pd.DataFrame({
                    'id': ['None'],
                    'impact': ['None'],
                    'tags': ['None'],
                    'description': ['None'],
                    'help': ['None'],
                    'helpUrl': ['None'],
                    'nodeHtml': ['None'],
                    'nodeImpact': ['None'],
                    'nodeType': ['None'],      
                    'numViolations': [0]
                })
                new_df = pd.concat([new_df, df_temp], ignore_index=True)
        except Exception as e:
            print(f"Error processing violation data: {e}")
            return pd.DataFrame()

        try:
            self.remove_files_starting_with("data*")
            if os.path.exists('num_of_violations.txt'):
                os.remove('num_of_violations.txt')
        except Exception as e:
            print(f"Error cleaning up files: {e}")

        new_df = self.add_severity_score(new_df, 'finalScore', 3)
        return new_df

    def call_corrections_to_violations(self, url):
        print("Violation result after corrections.....")
        df_corrections = pd.DataFrame()
        dom_corrected = self.input_df.iloc[0]['DOMCorrected']

        df_temp = self.correction_to_violations(dom_corrected)
        df_corrections = pd.concat([df_corrections, df_temp])
        df_corrections.to_csv('correctionViolations.csv', index=False)
        return df_corrections



    def analyze_violations_from_URL(self, url, path):
        fetch_and_save_data(url, path)
        total_initial_severity_score, result_df = self.run_agentic_loop(path)

        if result_df.empty or result_df.iloc[0]['id'] == 'None':
            total_final_severity_score = 0
        else:
            total_final_severity_score = self.calculate_severity_score(result_df, 'finalScore')
            
        total_improvement = 0
        if total_initial_severity_score > 0:
            total_improvement = ((1 - (total_final_severity_score / total_initial_severity_score)) * 100)

        corrected_html = None
        corrected_file_path = os.path.join('data', 'corrected.html')
        if os.path.exists(corrected_file_path):
            with open(corrected_file_path, 'r', encoding='utf-8') as f:
                corrected_html = f.read()
                
        csv_file_path = os.path.join('data', 'guideline_details.csv')
        if os.path.exists(csv_file_path):
            csv_data = pd.read_csv(csv_file_path)
            csv_content = csv_data.to_dict(orient='records')
        else:
            csv_content = [] 

        return {
            "total_initial_severity_score": int(total_initial_severity_score) if isinstance(total_initial_severity_score, np.integer) else total_initial_severity_score,
            "total_final_severity_score": int(total_final_severity_score) if isinstance(total_final_severity_score, np.integer) else total_final_severity_score,
            "total_improvement": float(total_improvement) if isinstance(total_improvement, (np.integer, np.floating)) else total_improvement,
            "corrected_html": corrected_html,
            "csv_file_path": csv_content
        }
    
    def analyze_violations_from_code(self, code, path):
        save_code_to_path(code, path)
        total_initial_severity_score, result_df = self.run_agentic_loop(path)

        if result_df.empty or result_df.iloc[0]['id'] == 'None':
            total_final_severity_score = 0
        else:
            total_final_severity_score = self.calculate_severity_score(result_df, 'finalScore')
            
        total_improvement = 0
        if total_initial_severity_score > 0:
            total_improvement = ((1 - (total_final_severity_score / total_initial_severity_score)) * 100)

        corrected_html = None
        corrected_file_path = os.path.join('data', 'corrected.html')
        if os.path.exists(corrected_file_path):
            with open(corrected_file_path, 'r', encoding='utf-8') as f:
                corrected_html = f.read()
                
        csv_file_path = os.path.join('data', 'guideline_details.csv')
        if os.path.exists(csv_file_path):
            csv_data = pd.read_csv(csv_file_path)
            csv_content = csv_data.to_dict(orient='records')
        else:
            csv_content = [] 

        return {
            "total_initial_severity_score": int(total_initial_severity_score) if isinstance(total_initial_severity_score, np.integer) else total_initial_severity_score,
            "total_final_severity_score": int(total_final_severity_score) if isinstance(total_final_severity_score, np.integer) else total_final_severity_score,
            "total_improvement": float(total_improvement) if isinstance(total_improvement, (np.integer, np.floating)) else total_improvement,
            "corrected_html": corrected_html, 
            "csv_file_path": csv_content
        }

    def analyze_violations_from_file(self, content: bytes, filename: str, path: str) -> Dict[str, Any]:
        try:
            if filename.lower().endswith('.pdf'):
                code = self.file_extractor.extract_text_from_pdf(content)
            elif filename.lower().endswith('.docx'):
                code = self.file_extractor.extract_text_from_docx(content)
            elif filename.lower().endswith('.html'):
                code = self.file_extractor.extract_text_from_html(content)
            else:
                raise ValueError("Unsupported file format")

            result = self.analyze_violations_from_code(code, path)
            return result

        except Exception as e:
            print(f"Error processing file: {str(e)}")
            raise ValueError(f"Failed to process file content: {str(e)}") from e



def analyzeURL(url: str):
    model = CleanGPTModels()
    path = 'data/input.html'
    return model.analyze_violations_from_URL(url, path)

def analyzeCode(code: str):
    model = CleanGPTModels()
    path = 'data/input.html'
    return model.analyze_violations_from_code(code, path)

def analyzeCodeFromFile(content: bytes, filename: str) -> Dict[str, Any]:
    try:
        model = CleanGPTModels()
        result = model.analyze_violations_from_file(content, filename, 'data/input.html')
        return result
    except Exception as e:
        raise ValueError(f"Analysis failed: {str(e)}")
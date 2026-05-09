import pandas as pd
import os
import platform
import time
import glob
import subprocess
import openai
from dotenv import load_dotenv
from llm_functions import LLMFunctions
from web_scrapper_and_file_handler import fetch_and_save_data


def run_playwright_test():
    try:
        # Copy the current environment variables
        env = os.environ.copy()
        env['CI'] = '1'  # Set the CI variable

        if platform.system() == 'Windows':
            # Run the Playwright test on Windows
            subprocess.run('npx playwright test', shell=True, check=True, env=env)
        else:
            # Run the Playwright test on Unix-based systems
            subprocess.run('npx playwright test', shell=True, check=True, env=env)
    except subprocess.CalledProcessError as e:
        print(f"Error running Playwright test: {e}")


class CleanGPTModels:
    def __init__(self):
        load_dotenv()
        self.gpt_functions = LLMFunctions(provider='ollama', model='codegemma:latest')
        # openai.api_key = os.getenv('OPENAI_API_KEY')

        if not os.path.exists('violationsWithFixedContent.csv'):
            # Create a file with headers or empty content
            with open('violationsWithFixedContent.csv', 'w') as file:
                file.write('id,impact,tags,description,help,helpUrl,nodeImpact,nodeHtml,nodeTarget,nodeType,message,numViolation\n')

        # Now read the file into a DataFrame
        self.input_df = pd.read_csv('violationsWithFixedContent.csv')

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
        from bs4 import BeautifulSoup
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
                            # Safely inject attributes
                            for attr, val in fix_json["attributes"].items():
                                node[attr] = val
                        elif action == "replace_html" and "html" in fix_json:
                            # Replace structurally
                            new_node = BeautifulSoup(fix_json["html"], 'html.parser')
                            node.replace_with(new_node)
                except Exception as e:
                    print(f"Error applying JSON fix to {target_selector}: {e}")

        corrected_dom = str(soup)
        self.input_df['DOMCorrected'] = corrected_dom
        return corrected_dom, attempted_fixes

    def remove_files_starting_with(self, pattern):
        files_to_remove = glob.glob(pattern)
        for file_path in files_to_remove:
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except OSError as e:
                print(f"Error while removing file '{file_path}': {e}")

    def create_test_script(self, url, path):   
        print("Creating the violation file...........")

        with open(path, 'r', encoding='utf-8') as text_file:
            dom = text_file.read()

        test_script_path = "./tests/before.spec.ts"
        with open(test_script_path, "w", encoding='utf-8') as f:
            f.write(f"""
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
                    const headers = ['id', 'impact', 'tags', 'description', 'help', 'helpUrl', 'nodeImpact', 'nodeHtml', 'nodeTarget', 'nodeType', 'message', 'numViolation'];
                    let csvContent = headers.join(',') + '\\n';               
                    const totalViolations = violations.length; 

                    violations.forEach(violation => {{
                        violation.nodes.forEach(node => {{
                            const nodeImpacts = ['any', 'all', 'none'];
                            nodeImpacts.forEach(impactType => {{
                                if (node[impactType] && node[impactType].length > 0) {{
                                    node[impactType].forEach(check => {{
                                        const row = [
                                            escapeCSV(violation.id),
                                            escapeCSV(violation.impact),
                                            escapeCSV(violation.tags.join('|')),
                                            escapeCSV(violation.description),
                                            escapeCSV(violation.help),
                                            escapeCSV(violation.helpUrl),
                                            escapeCSV(check.impact || ''),
                                            escapeCSV(node.html),
                                            escapeCSV(node.target.join('|')),
                                            escapeCSV(impactType),
                                            escapeCSV(check.message),
                                            escapeCSV(totalViolations)
                                        ];
                                        csvContent += row.join(',') + '\\n';
                                    }});
                                }}
                            }});
                        }});
                    }});
                    
                    return csvContent;
                }}

                test('accessibility issues', async ({{ page }}) => {{
                    await page.setContent(`{dom}`);
                    const accessibilityScanResults = await new AxeBuilder({{ page }}).analyze();
                    const violations = accessibilityScanResults.violations;

                    // Write CSV data to file
                    fileReader.writeFileSync("violationsWithFixedContent.csv", violationsToCSV(violations));
                    // Write the number of violations to a file
                    fileReader.writeFileSync("num_violations.txt", String(violations.length));
                }});
            """)

        # Run the Playwright test script after creation
        run_playwright_test()
        time.sleep(1)


        if os.path.exists('num_violations.txt'):
            try:
                os.remove('num_violations.txt')
            except PermissionError:
                time.sleep(1)
                os.remove('num_violations.txt')        


    def corrections2violations(self, corrected_dom):
        test_script_path = "./tests/after.spec.ts"
        with open(test_script_path, "w", encoding='utf-8') as f:
            f.write(f"""
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
                const headers = ['id', 'impact', 'tags', 'description', 'help', 'helpUrl', 'nodeImpact', 'nodeHtml', 'nodeTarget', 'nodeType', 'message', 'numViolation'];
                let csvContent = headers.join(',') + '\\n';               
                const totalViolations = violations.length; 

                violations.forEach(violation => {{
                    violation.nodes.forEach(node => {{
                        const nodeImpacts = ['any', 'all', 'none'];
                        nodeImpacts.forEach(impactType => {{
                            if (node[impactType] && node[impactType].length > 0) {{
                                node[impactType].forEach(check => {{
                                    const row = [
                                        escapeCSV(violation.id),
                                        escapeCSV(violation.impact),
                                        escapeCSV(violation.tags.join('|')),
                                        escapeCSV(violation.description),
                                        escapeCSV(violation.help),
                                        escapeCSV(violation.helpUrl),
                                        escapeCSV(check.impact || ''),
                                        escapeCSV(node.html),
                                        escapeCSV(node.target.join('|')),
                                        escapeCSV(impactType),
                                        escapeCSV(check.message),
                                        escapeCSV(totalViolations)
                                    ];
                                    csvContent += row.join(',') + '\\n';
                                }});
                            }}
                        }});
                    }});
                }});
                
                return csvContent;
            }}

            test('all violations', async ({{ page }}) => {{
                await page.setContent(`{corrected_dom}`)
                const accessibilityScanResults = await new AxeBuilder({{ page }}).analyze();
                const violations = accessibilityScanResults.violations;

                fileReader.writeFileSync("violationsAfter.csv", violationsToCSV(violations));
                fileReader.writeFileSync("num_violations2.txt", String(violations.length));
            }});
            """            
            )

        run_playwright_test()
        time.sleep(1)

        length = 0
        if os.path.exists('num_violations2.txt'):
            with open('num_violations2.txt', "r") as length_file:
                length = int(length_file.readline().strip())

        if length > 0 and os.path.exists("violationsAfter.csv"):
            new_df = pd.read_csv("violationsAfter.csv")
        else:
            new_df = pd.DataFrame({
                'id': ['None'],
                'impact': ['None'],
                'tags': ['None'],
                'description': ['None'],
                'help': ['None'],
                'helpUrl': ['None'],
                'nodeImpact': ['None'],
                'nodeHtml': ['None'],
                'nodeTarget': ['None'],
                'nodeType': ['None'],
                'message': ['None'],          
                'numViolation': [0]
            })

        if os.path.exists('num_violations2.txt'):
            try:
                os.remove('num_violations2.txt')
            except PermissionError:
                time.sleep(1)
                os.remove('num_violations2.txt')
                
        if os.path.exists('violationsAfter.csv'):
            try:
                os.remove('violationsAfter.csv')
            except PermissionError:
                pass

        new_df = self.add_severity_score(new_df, 'finalScore', 3)
        return new_df

    def run_agentic_loop(self, url, path, max_iterations=3):
        print("\n--- Starting Agentic Feedback Loop ---")
        self.create_test_script(url, path)
        self.input_df = self.add_severity_score(self.input_df, 'initialScore', 5)
        
        total_initial_severity_score = self.calculate_severity_score(self.input_df, 'initialScore')
        print(f"Total Initial Violations: {len(self.input_df)}")
        print(f"Total Initial Severity Score: {total_initial_severity_score}")

        with open(path, 'r', encoding='utf-8') as text_file:
            current_dom = text_file.read()

        failed_fixes = {}
        
        for iteration in range(max_iterations):
            if self.input_df.empty or len(self.input_df) == 0 or self.input_df.iloc[0]['id'] == 'None':
                print(f"All violations resolved!")
                break
                
            print(f"\n[Iteration {iteration+1}/{max_iterations}] Attempting fixes...")
            
            current_dom, attempted_fixes = self.apply_fixes_to_dom(current_dom, failed_fixes)
            
            new_df = self.corrections2violations(current_dom)
            
            # Check what failed to inform the next loop
            failed_fixes = {}
            if not new_df.empty and new_df.iloc[0]['id'] != 'None':
                for index, row in new_df.iterrows():
                    target = str(row['nodeTarget']).split('|')[0] if pd.notna(row['nodeTarget']) else ""
                    if target in attempted_fixes:
                        failed_fixes[target] = attempted_fixes[target]
                        print(f"  Fix failed for {target}")
            
            self.input_df = new_df
            print(f"Remaining Violations after Iteration {iteration+1}: {0 if (new_df.empty or new_df.iloc[0]['id'] == 'None') else len(self.input_df)}")

        # Save final dom
        corrected_path = os.path.join('data', 'corrected.html')
        os.makedirs('data', exist_ok=True)
        with open(corrected_path, 'w', encoding='utf-8') as corrected_file:
            corrected_file.write(current_dom)
            
        return total_initial_severity_score, self.input_df



def main():
    print("The code starts running here....")
    url = 'https://calendar.google.com/'
    path = 'data/input.html'

    fetch_and_save_data(url, path)  # web scrape

    model = CleanGPTModels()
    initial_score, final_df = model.run_agentic_loop(url, path, max_iterations=3)

    if final_df.empty or final_df.iloc[0]['id'] == 'None':
        final_score = 0
    else:
        final_score = model.calculate_severity_score(final_df, 'finalScore')

    print("\n--- Final Results ---")
    print(f"Initial Score: {initial_score}")
    print(f"Final Score: {final_score}")
    if initial_score > 0:
        improvement = ((1 - (final_score / initial_score)) * 100)
        print(f"Total Improvement: {improvement:.2f}%")
    
    final_df.to_csv('correctionViolations.csv', index=False)

if __name__ == "__main__":
    main()
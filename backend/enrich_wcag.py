import requests
from bs4 import BeautifulSoup
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import random
from urllib.parse import urljoin

# Configuration
BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "wcag.json"
OUTPUT_FILE = BASE_DIR / "wcag_enriched.json"

# Global session
session = requests.Session()

def fetch_html(url):
    try:
        # Randomized delay
        time.sleep(random.uniform(2.0, 5.0))
        # Default requests/session behavior works better for W3C than fake headers
        response = session.get(url, timeout=15)
        if response.status_code != 200:
            print(f"Warning: Fetch {url} returned status {response.status_code}")
            return None
        return response.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def extract_examples_from_tech_page(url):
    """Extract code snippets from an individual Technique/Failure page."""
    html = fetch_html(url)
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'html.parser')
    examples = []
    
    # W3C Techniques have sections for Examples
    for section in soup.select('section.example'):
        title_tag = section.find(['h2', 'h3', 'h4'])
        title = title_tag.get_text(strip=True) if title_tag else "Example"
        
        # Prioritize <pre> tags for full code blocks
        code_blocks = section.select('pre')
        if not code_blocks:
            # Fallback to <code> only if no <pre> exists
            code_blocks = section.select('code')
        
        if not code_blocks:
            continue
            
        # Get the largest code block in this section (to avoid inline fragments)
        code_text = max([block.get_text(strip=True) for block in code_blocks], key=len)
        
        # Filter out tiny snippets (less than 10 chars)
        if len(code_text) < 10:
            continue
        
        # Try to find a description
        description = ""
        p_tag = section.find('p')
        if p_tag:
            description = p_tag.get_text(strip=True)
                
        examples.append({
            "title": title,
            "description": description,
            "code": code_text
        })
    return examples

def enrich_criterion(sc):
    """Process a single Success Criterion via its Understanding page."""
    ref_id = sc.get('ref_id')
    
    # Find Understanding URL
    understanding_url = None
    for ref in sc.get('references', []):
        if "Understanding" in ref.get('title', ''):
            understanding_url = ref.get('url')
            break
    
    if not understanding_url:
        return []

    html = fetch_html(understanding_url)
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'html.parser')
    tech_links = []
    
    # Check all links
    for a in soup.find_all('a', href=True):
        href = a['href']
        # W3C uses both /Techniques/ and /techniques/
        if '/Techniques/' in href or '/techniques/' in href:
            full_url = urljoin(understanding_url, href).split('#')[0]
            if full_url not in tech_links:
                tech_links.append(full_url)
    
    if tech_links:
        print(f"SC {ref_id}: Found {len(tech_links)} techniques")
    else:
        # Debugging: Why no links?
        pass

    return tech_links

def main():
    if not INPUT_FILE.exists():
        print(f"Error: {INPUT_FILE} not found.")
        return

    # 1. Load the base WCAG data
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 2. Extract all SCs
    all_sc = []
    for principle in data:
        for guideline in principle.get('guidelines', []):
            for sc in guideline.get('success_criteria', []):
                all_sc.append(sc)

    # 3. Map SCs to Technique URLs (Serial)
    print(f"Scraping Understanding pages for {len(all_sc)} Success Criteria...")
    sc_to_tech_urls = {}
    with ThreadPoolExecutor(max_workers=1) as executor:
        results = list(executor.map(lambda sc: (sc['ref_id'], enrich_criterion(sc)), all_sc))
        sc_to_tech_urls = {ref_id: urls for ref_id, urls in results if urls}

    # 4. Gather unique technique URLs
    all_unique_techs = set()
    for urls in sc_to_tech_urls.values():
        all_unique_techs.update(urls)
    
    print(f"Found {len(all_unique_techs)} unique techniques. Fetching examples...")

    # 5. Fetch technique examples (Serial)
    tech_cache = {}
    if all_unique_techs:
        with ThreadPoolExecutor(max_workers=1) as executor:
            results = list(executor.map(lambda url: (url, extract_examples_from_tech_page(url)), list(all_unique_techs)))
            tech_cache = {url: examples for url, examples in results if examples}

    # 6. Re-map examples back to data
    total_examples = 0
    for sc in all_sc:
        ref_id = sc.get('ref_id')
        tech_urls = sc_to_tech_urls.get(ref_id, [])
        dynamic_examples = []
        for url in tech_urls:
            if url in tech_cache:
                dynamic_examples.extend(tech_cache[url])
        
        # Limit examples per SC to keep file size reasonable (max 10)
        sc['dynamic_examples'] = dynamic_examples[:10]
        total_examples += len(sc['dynamic_examples'])

    # 7. Save enriched data
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Enrichment complete.")
    print(f"Total dynamic examples saved: {total_examples}")
    print(f"Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()

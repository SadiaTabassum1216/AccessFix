import requests
from bs4 import BeautifulSoup
import os

_DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def save_html_to_file(html_content, output_path):
    """Save HTML content to file with BeautifulSoup formatting."""
    soup = BeautifulSoup(html_content, "html.parser")
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(soup.prettify())
    print(f"HTML saved to {output_path}")

def fetch_and_save_html(source, output_path):
    """Fetch HTML from URL or local file and save formatted version.
    
    Args:
        source: URL (https://...) or local file path
        output_path: Destination file path for formatted HTML
    """
    print(f"Processing HTML from {source}...")
    
    # Handle local file paths
    if os.path.exists(source):
        with open(source, 'r', encoding='utf-8') as f:
            html_content = f.read()
        save_html_to_file(html_content, output_path)
        print(f"Local file copied to {output_path}")
        return
    
    # Fetch from URL
    try:
        response = requests.get(source, headers=_DEFAULT_HEADERS, timeout=10)
        response.raise_for_status()
        save_html_to_file(response.text, output_path)
    except requests.RequestException as e:
        print(f"Failed to fetch from {source}: {e}")
        raise

# Backward compatibility aliases
def fetch_and_save_data(url, path):
    """Deprecated: use fetch_and_save_html() instead."""
    return fetch_and_save_html(url, path)

def save_code_to_path(code, path):
    """Deprecated: use save_html_to_file() instead."""
    return save_html_to_file(code, path)

import requests
from bs4 import BeautifulSoup
import os

def fetch_and_save_data(url, path):
    print(f"fetching the code from {url}............")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    # Handle local file paths
    if os.path.exists(url):
        with open(url, 'r', encoding='utf-8') as f:
            content = f.read()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Local file content has been copied to {path}")
        return

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(soup.prettify())
            print(f"HTML content has been saved to {path}")
        else:
            print(f"Failed to retrieve the webpage. Status code: {response.status_code}")
    except Exception as e:
        print(f"Request failed: {e}")


def save_code_to_path(code, path):
    print("Processing the HTML code...")
    soup = BeautifulSoup(code, "html.parser")
    
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(soup.prettify())
    
    print(f"HTML content has been saved to {path}")

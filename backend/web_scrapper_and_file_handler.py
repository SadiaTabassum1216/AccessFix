import requests
from bs4 import BeautifulSoup
import os

def fetch_and_save_data(url, path):
    print("fetching the code............")
    response = requests.get(url)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        
        print(f"HTML content has been saved to {path}")
    else:
        print(f"Failed to retrieve the webpage. Status code: {response.status_code}")


def save_code_to_path(code, path):
    print("Processing the HTML code...")
    soup = BeautifulSoup(code, "html.parser")
    
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(soup.prettify())
    
    print(f"HTML content has been saved to {path}")

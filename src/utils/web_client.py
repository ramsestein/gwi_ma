"""
Web Client for DeepSeek Agent
Provides basic web search and page reading capabilities.

Usage:
  python -m src.utils.web_client search "query string"
  python -m src.utils.web_client read "url"
"""
import sys
import requests
import re
import urllib.parse

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

def clean_text(text):
    # Remove extra whitespace
    return re.sub(r'\s+', ' ', text).strip()

def search_web(query):
    print(f"[Web] Searching for: {query}")
    # Using DuckDuckGo HTML (no API key needed, strictly for research)
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) VitalParser/1.0'}
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        
        if HAS_BS4:
            soup = BeautifulSoup(res.text, 'html.parser')
            results = []
            for i, result in enumerate(soup.find_all('div', class_='result'), 1):
                if i > 5: break
                title_tag = result.find('a', class_='result__a')
                snippet_tag = result.find('a', class_='result__snippet')
                
                if title_tag and snippet_tag:
                    title = clean_text(title_tag.text)
                    link = title_tag['href']
                    snippet = clean_text(snippet_tag.text)
                    results.append(f"{i}. [{title}]({link})\n   {snippet}")
            return "\n\n".join(results) if results else "No results found."
        else:
            # Fallback regex parsing if BS4 missing
            return "BeautifulSoup not installed. Please install bs4 for better results."
            
    except Exception as e:
        return f"Search Error: {e}"

def read_page(url):
    print(f"[Web] Reading: {url}")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) VitalParser/1.0'}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        
        if HAS_BS4:
            soup = BeautifulSoup(res.text, 'html.parser')
            # Kill script and style elements
            for script in soup(["script", "style", "nav", "footer"]):
                script.extract()
            text = soup.get_text()
            clean = clean_text(text)
            return clean[:5000] + ("\n...[Truncated]" if len(clean) > 5000 else "")
        else:
            return clean_text(res.text)[:5000]
            
    except Exception as e:
        return f"Read Error: {e}"

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m src.utils.web_client <search|read> <query|url>")
        sys.exit(1)
        
    cmd = sys.argv[1]
    arg = sys.argv[2]
    
    if cmd == 'search':
        print(search_web(arg))
    elif cmd == 'read':
        print(read_page(arg))
    else:
        print("Unknown command")

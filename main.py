import os
import requests
from bs4 import BeautifulSoup
import json
import time
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import random

# Nastavení cookies pro připojení
cookies = {
    "dCMP": "mafra=1111,all=1,reklama=1,part=0,cpex=1,google=1,gemius=1,id5=1,next=0000,onlajny=0000,jenzeny=0000,"
            "databazeknih=0000,autojournal=0000,skodahome=0000,skodaklasik=0000,groupm=1,piano=1,seznam=1,geozo=0,"
            "czaid=1,click=1,verze=2,"
}

# Nastavení loggeru pro sledování stavu
logging.basicConfig(level=logging.INFO)


# Funkce pro extrakci informací z článku
def extract_article_data(url):
    try:
        response = requests.get(url, cookies=cookies, timeout=5)  # Timeout pro zamezení zacyklení
        response.raise_for_status()  # Pokud není odpověď 200, vyvolá chybu

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extrakce pouze klíčových informací
        title = soup.find('h1')
        category = soup.find('a', class_='category')
        comments_count = soup.find('span', class_='comments-count')
        images = soup.find_all('img')
        date_created = soup.find('time')

        article_data = {
            "url": url,
            "title": title.text.strip() if title else 'N/A',
            "category": category.text.strip() if category else 'N/A',
            "comments_count": int(comments_count.text.strip()) if comments_count else 0,
            "images_count": len(images),
            "date_created": date_created['datetime'] if date_created else datetime.now().isoformat()
        }

        return article_data
    except Exception as e:
        logging.error(f"Chyba při zpracování URL {url}: {e}")
        return None


# Funkce pro crawlování jednoho URL
def crawl(url, visited_urls, to_visit_urls, articles_data):
    if url in visited_urls:
        return

    visited_urls.add(url)

    logging.info(f"Navštěvuji URL: {url}")

    article_data = extract_article_data(url)
    if article_data:
        articles_data.append(article_data)
        logging.info(f"Data pro URL {url} uložena")

    # Přidání odkazů na další články do fronty
    try:
        response = requests.get(url, cookies=cookies, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')

        for a_tag in soup.find_all('a', href=True):
            next_url = a_tag['href']
            if next_url.startswith('https://www.idnes.cz'):
                if next_url not in visited_urls and next_url not in to_visit_urls:
                    to_visit_urls.append(next_url)
    except Exception as e:
        logging.error(f"Chyba při získávání dalších odkazů z {url}: {e}")


# Funkce pro průběžné ukládání dat a správu souborů
def save_data_in_chunks(articles_data, file_prefix='articles_data', chunk_size=100, max_size=2*1024*1024*1024):
    chunk = []
    file_count = 1
    file_path = f'{file_prefix}_{file_count}.json'

    for article in articles_data:
        chunk.append(article)
        
        # Pokud je velikost souboru větší než 2 GB, vytvoříme nový soubor
        if os.path.exists(file_path) and os.path.getsize(file_path) > max_size:
            file_count += 1
            file_path = f'{file_prefix}_{file_count}.json'
            chunk = []  # Resetujeme chunk

        if len(chunk) >= chunk_size:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(chunk, f, ensure_ascii=False, indent=4)
            chunk = []  # Resetujeme chunk

    # Uložit poslední část, pokud nějaká zůstala
    if chunk:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(chunk, f, ensure_ascii=False, indent=4)


# Hlavní funkce pro spuštění paralelního crawlování
def start_crawl(start_urls):
    visited_urls = set()  # Sada pro navštívené URL
    to_visit_urls = start_urls.copy()  # Seznam pro URL k navštívení
    articles_data = []  # Uložená data

    # Nastavení maximálního počtu vláken
    max_threads = 20
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        while to_visit_urls:
            # Vytvoření tasků pro paralelní zpracování URL
            futures = [executor.submit(crawl, url, visited_urls, to_visit_urls, articles_data) for url in
                       to_visit_urls[:max_threads]]

            # Čekání na dokončení tasků
            for future in futures:
                future.result()  # Čeká, až každý task skončí

            # Po zpracování pár URL, odstraníme je ze seznamu 'to_visit_urls'
            to_visit_urls = to_visit_urls[max_threads:]
            save_data_in_chunks(articles_data)

            # Pauza mezi požadavky, aby se snížilo zatížení serveru
            time.sleep(random.uniform(1, 3))  # Náhodná pauza mezi 1 a 3 sekundy


# Spuštění crawleru s počátečními URL
start_urls = ['https://www.idnes.cz']
start_crawl(start_urls)
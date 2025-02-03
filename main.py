import os
import json
import re
import asyncio
import aiohttp
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil import parser as date_parser
import logging
from concurrent.futures import ThreadPoolExecutor

MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024 
OUTPUT_FILE = "multi_site_articles.json" 
CONCURRENT_REQUESTS = 100
REQUEST_DELAY = 0.5
START_URLS = [
    "https://www.idnes.cz",
    "https://www.novinky.cz",
    "https://cs.wikipedia.org"
]

SITE_CONFIG = {
    "idnes.cz": {
        "cookies": {
            "dCMP": "mafra=1111,all=1,reklama=1,part=0,cpex=1,google=1,gemius=1,id5=1,next=0000,onlajny=0000,jenzeny=0000,"
                    "databazeknih=0000,autojournal=0000,skodahome=0000,skodaklasik=0000,groupm=1,piano=1,seznam=1,geozo=0,"
                    "czaid=1,click=1,verze=2,"
        },
        "selectors": {
            "title": "h1.art-title",
            "content": "div.art-text",
            "category": ".breadcrumb a:last-child",
            "date": "time[itemprop='datePublished']",
            "comments": ".comment-count",
            "images": ".art-gallery"
        },
        "article_patterns": [
            r"/zpravy/",
            r"/domaci/",
            r"/ekonomika/"
        ]
    },
    "novinky.cz": {
        "selectors": {
            "title": "h1.title",
            "content": "div.articleBody",
            "category": "ul.breadcrumb li:last-child a",
            "date": "time.date",
            "comments": ".commentsCount",
            "images": ".gallery img"
        },
        "article_patterns": [
            r"/clanek/",
            r"/zpravy/"
        ]
    },
    "wikipedia.org": {
        "selectors": {
            "title": "h1#firstHeading",
            "content": "div#mw-content-text",
            "category": "#p-navigation li a",
            "date": "li#footer-info-lastmod",
            "comments": "",
            "images": "div.thumbinner"
        },
        "article_patterns": [
            r"/wiki/"
        ]
    }
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MultiSiteCrawler:
    def __init__(self):
        self.visited_urls = set()
        self.queue = asyncio.Queue()
        self.lock = asyncio.Lock()
        self.session = None
        self.file_size = 0
        self.article_count = 0
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.articles = [] 

    async def initialize(self):
        self.session = aiohttp.ClientSession(
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )

    async def close(self):
        await self.session.close()
        self.executor.shutdown()
        self.save_to_json()  

    def get_site_config(self, domain):
        for site in SITE_CONFIG:
            if site in domain:
                return SITE_CONFIG[site]
        return {}

    def is_article_url(self, url):
        parsed = urlparse(url)
        config = self.get_site_config(parsed.netloc)
        return any(re.search(p, parsed.path) for p in config.get("article_patterns", []))

    @staticmethod
    def clean_text(text):
        return re.sub(r'\s+', ' ', text).strip()

    def save_to_json(self):
        """Uloží články do JSON souboru bez přepisování již existujících dat."""
        if not self.articles:
            return

        existing_data = []
        
        # Pokud soubor existuje, načteme jeho obsah
        if os.path.exists(OUTPUT_FILE):
            try:
                with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                logging.warning("Soubor je poškozen nebo prázdný. Vytvářím nový.")

        # Přidáme nové články k existujícím
        existing_data.extend(self.articles)

        try:
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(existing_data, f, indent=4, ensure_ascii=False)
            self.file_size = os.path.getsize(OUTPUT_FILE)
            logging.info(f"Uloženo {len(existing_data)} článků do {OUTPUT_FILE}")
        except Exception as e:
            logging.error(f"Chyba při ukládání do JSON: {str(e)}")

        # Vyprázdnění paměti
        self.articles = []

    async def save_article(self, data):
        """Přidá článek do seznamu a pravidelně ukládá do souboru."""
        async with self.lock:
            self.articles.append(data)
            self.article_count += 1

            if len(self.articles) % 100 == 0:
                self.save_to_json()
                self.articles = []  

            if self.file_size >= MAX_FILE_SIZE:
                logging.info("Dosaženo maximální velikosti souboru.")
                return False

        return True

    def parse_date(date_str):
        if not date_str:
            return ""

        match = re.search(r"(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{4})\s?v\s?(\d{1,2}):(\d{2})", date_str)
        if match:
            day, month, year, hour, minute = match.groups()
            date_cleaned = f"{year}-{month}-{day} {hour}:{minute}"
            try:
                dt = datetime.strptime(date_cleaned, "%Y-%m-%d %H:%M")
                return dt.isoformat()
            except ValueError:
                logging.warning(f"Chyba parsování data: {date_str}")
                return ""

        logging.warning(f"Neznámý formát data: {date_str}")
        return ""

    async def parse_article(self, url):
        try:
            parsed = urlparse(url)
            config = self.get_site_config(parsed.netloc)
            
            async with self.session.get(url, cookies=config.get("cookies", {})) as response:
                if response.status != 200:
                    return None
                
                html = await response.text()
                loop = asyncio.get_event_loop()
                soup = await loop.run_in_executor(
                    self.executor,
                    lambda: BeautifulSoup(html, "lxml")
                )

                selectors = config.get("selectors", {})
                
                article_data = {
                    "url": url,
                    "source": parsed.netloc,
                    "title": self.clean_text(soup.select_one(selectors["title"]).text) if soup.select_one(selectors["title"]) else "",
                    "content": self.clean_text(" ".join([p.text for p in soup.select(selectors["content"] + " p")])) if soup.select_one(selectors["content"]) else "",
                    "category": soup.select_one(selectors["category"]).text.strip() if soup.select_one(selectors["category"]) else "",
                    "comments": int(soup.select_one(selectors["comments"]).text.strip()) if selectors["comments"] and soup.select_one(selectors["comments"]) else 0,
                    "images": len(soup.select(selectors["images"])) if selectors.get("images") else 0,
                    "date": ""
                }

                date_element = soup.select_one(selectors["date"])
                if date_element:
                    date_str = date_element.get("datetime") or date_element.text
                    try:
                        dt = date_parser.parse(date_str)
                        article_data["date"] = parse_date(date_element.text) if date_element else ""
                    except Exception as e:
                        logging.warning(f"Chyba parsování data: {e}")

                return article_data
        except Exception as e:
            logging.error(f"Chyba při zpracování {url}: {str(e)}")
            return None


    async def process_url(self, url):
        if url in self.visited_urls:
            return
        
        async with self.lock:
            self.visited_urls.add(url)

        if self.is_article_url(url):
            article_data = await self.parse_article(url)
            if article_data:
                await self.save_article(article_data)
                logging.info(f"Článků uloženo: {self.article_count} | Velikost: {self.file_size/1024/1024:.2f} MB")
        else:
            try:
                async with self.session.get(url) as response:
                    if response.status == 200:
                        html = await response.text()
                        loop = asyncio.get_event_loop()
                        soup = await loop.run_in_executor(
                            self.executor,
                            lambda: BeautifulSoup(html, "lxml")
                        )
                        
                        for link in soup.find_all("a", href=True):
                            new_url = urljoin(url, link["href"])
                            parsed = urlparse(new_url)
                            if any(site in parsed.netloc for site in SITE_CONFIG) and new_url not in self.visited_urls:
                                await self.queue.put(new_url)
            except Exception as e:
                logging.error(f"Chyba při zpracování {url}: {str(e)}")

    async def worker(self):
        while True:
            url = await self.queue.get()
            try:
                await self.process_url(url)
            finally:
                self.queue.task_done()

    async def run(self):
        await self.initialize()
        
        for url in START_URLS:
            await self.queue.put(url)

        workers = [asyncio.create_task(self.worker()) for _ in range(CONCURRENT_REQUESTS)]
        
        while not self.queue.empty() and self.file_size < MAX_FILE_SIZE:
            await asyncio.sleep(1)

        for worker in workers:
            worker.cancel()
        
        await self.close()
        logging.info(f"Konečná velikost souboru: {self.file_size/1024/1024:.2f} MB")

if __name__ == "__main__":
    crawler = MultiSiteCrawler()
    
    try:
        asyncio.run(crawler.run())
    except KeyboardInterrupt:
        logging.info("Ukončeno uživatelem")
import os
import csv
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor


START_URLS = [
    "https://www.novinky.cz",  
    "https://www.idnes.cz",  
    "https://www.ctk.cz"  
]

MAX_URLS = 5000  
OUTPUT_FILE = "scraped_data.csv"
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  

session = requests.Session()

def collect_article_urls(base_url):
    """Sbírá odkazy na články z dané domény."""
    collected_urls = set()
    to_visit = [base_url]
    visited_urls = set()

    print(f"Starting URL collection from: {base_url}")

    while to_visit and len(collected_urls) < MAX_URLS:
        current_url = to_visit.pop(0)
        if current_url in visited_urls:
            continue
        visited_urls.add(current_url)

        print(f"Visiting URL: {current_url} | Collected so far: {len(collected_urls)}")

        try:
            response = session.get(current_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            for link in soup.find_all('a', href=True):
                url = link['href']
                full_url = url if url.startswith("http") else f"{base_url}{url}"
                if base_url in full_url and full_url not in collected_urls:
                    collected_urls.add(full_url)
                    to_visit.append(full_url)
        except Exception as e:
            print(f"Error collecting URLs from {current_url}: {e}")

    print(f"Finished URL collection from: {base_url} | Total collected: {len(collected_urls)}")
    return list(collected_urls)

def scrape_article(url):
    """Stahuje obsah článku."""
    print(f"Scraping article: {url}")

    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()

        if not response.text.strip():
            print(f"Skipping empty page: {url}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        title = soup.find('h1').get_text(strip=True) if soup.find('h1') else 'No title'

        content = ' '.join([p.get_text(strip=True) for p in soup.find_all('p')])

        images = len(soup.find_all('img'))

        category = soup.find('meta', {'property': 'article:section'})
        category = category['content'] if category else 'No category'

        comments = soup.find('a', {'class': 'comments-link'})
        comments_count = comments.get_text(strip=True) if comments else 'No comments'

        date = soup.find('meta', {'property': 'article:published_time'})
        date = date['content'] if date else 'No date'

        if not content.strip():
            print(f"Skipping empty article content: {url}")
            return None

        return {
            "url": url,
            "title": title,
            "content": content,
            "images": images,
            "category": category,
            "comments_count": comments_count,
            "date": date,
        }
    except requests.exceptions.RequestException as e:
        print(f"Error scraping {url}: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error scraping {url}: {e}")
        return None


def get_file_size_in_gb(filename):
    if os.path.exists(filename):
        return os.path.getsize(filename) / (1024 ** 3)  
    return 0

def scrape_multiple_urls_parallel(urls, batch_size=100):
    results = []
    total_urls = len(urls)
    with ThreadPoolExecutor(max_workers=10) as executor:
        for i in range(0, total_urls, batch_size):
            batch = urls[i:i + batch_size]
            print(f"Scraping batch {i // batch_size + 1} | URLs {i + 1}-{min(i + batch_size, total_urls)}")
            batch_results = list(executor.map(scrape_article, batch))
            batch_results = [res for res in batch_results if res]  

            save_to_csv(batch_results, OUTPUT_FILE)

            current_file_size_gb = get_file_size_in_gb(OUTPUT_FILE)
            print(f"Current collected data size: {current_file_size_gb:.2f} GB")
            if current_file_size_gb >= MAX_FILE_SIZE / (1024 ** 3):
                print(f"Reached file size limit of {MAX_FILE_SIZE / (1024 ** 3):.2f} GB. Stopping scraping.")
                break
    return results

def save_to_csv(data, filename):
    if not data:
        print("No data to save!")
        return

    file_exists = os.path.exists(filename)

    with open(filename, mode='a', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=data[0].keys())
        if not file_exists:
            writer.writeheader()
        writer.writerows(data)
    print(f"Data successfully saved to {filename}. Current size: {get_file_size_in_gb(filename):.2f} GB")

if __name__ == "__main__":
    all_collected_urls = []

    for start_url in START_URLS:
        print(f"Collecting URLs from {start_url}...")
        urls = collect_article_urls(start_url)
        all_collected_urls.extend(urls)
        print(f"Collected {len(urls)} URLs from {start_url}")

    all_collected_urls = list(set(all_collected_urls))
    print(f"Total collected unique URLs: {len(all_collected_urls)}")

    print("Scraping data from articles...")
    scrape_multiple_urls_parallel(all_collected_urls)

    final_file_size_gb = get_file_size_in_gb(OUTPUT_FILE)
    print(f"Scraping completed. Total data collected: {final_file_size_gb:.2f} GB")

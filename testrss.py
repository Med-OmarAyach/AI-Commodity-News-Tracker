import feedparser
import requests
from datetime import datetime, timedelta
import pandas as pd
import time
import random
from bs4 import BeautifulSoup
import re
from playwright.sync_api import sync_playwright

# ============ TEXT CLEANING ============
def clean_html_text(html_content):
    """Remove HTML tags and clean up text"""
    if not html_content or html_content == 'N/A':
        return 'N/A'
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove unwanted elements
    for tag in soup(['script', 'style', 'iframe', 'noscript', 'nav', 'footer', 'header']):
        tag.decompose()
    
    text = soup.get_text(separator=' ', strip=True)
    text = re.sub(r'\s+', ' ', text)
    
    # Remove RSS artifacts
    for artifact in ['Read more...', 'Continue reading...', 'Newsletter Sign Up', 'Subscribe']:
        text = text.replace(artifact, '')
    
    # Fix HTML entities
    entities = {'&nbsp;': ' ', '&amp;': '&', '&lt;': '<', '&gt;': '>', 
                '&quot;': '"', '&#8217;': "'", '&#8216;': "'", '&#8220;': '"', 
                '&#8221;': '"', '&#8211;': '-', '&#8212;': '—'}
    for entity, char in entities.items():
        text = text.replace(entity, char)
    
    return text.strip()

# ============ DATE/COMMODITY HELPERS ============
def parse_date(date_tuple):
    if date_tuple:
        return datetime(*date_tuple[:6])
    return datetime.now()

def extract_commodity_from_url(url):
    keywords = {
        'canola': 'Canola', 'soybean': 'Soybeans', 'sunflower': 'Sunflowers',
        'flax': 'Flax', 'wheat': 'Wheat', 'barley': 'Barley',
        'oat': 'Oats', 'corn': 'Corn', 'potato': 'Potatoes', 'chickpea': 'Chickpeas'
    }
    url_lower = url.lower()
    for kw, commodity in keywords.items():
        if kw in url_lower:
            return commodity
    return 'Unknown'

def extract_sector(commodity):
    sectors = {
        'Canola': 'Oil Seeds', 'Soybeans': 'Oil Seeds', 'Sunflowers': 'Oil Seeds', 'Flax': 'Oil Seeds',
        'Wheat': 'Cereals', 'Barley': 'Cereals', 'Oats': 'Cereals', 'Corn': 'Cereals',
        'Potatoes': 'Field Crops', 'Chickpeas': 'Pulses'
    }
    return sectors.get(commodity, 'Unknown')

# ============ CLOUDFLARE HANDLING ============
def wait_for_cloudflare_bypass(page, max_wait=45):
    """Wait for Cloudflare verification with auto-checkbox handling"""
    for i in range(max_wait):
        content = page.content()
        
        if "Just a moment" not in content and "cloudflare" not in content.lower():
            if page.query_selector("h1.entry-title") or page.query_selector("div.archive-articles-list"):
                return True
        
        # Try multiple checkbox selectors
        for selector in ["input[type='checkbox']", "#challenge-stage input", ".cf-turnstile-wrapper input", "button[type='button']"]:
            try:
                checkbox = page.query_selector(selector)
                if checkbox:
                    box = checkbox.bounding_box()
                    if box:
                        page.mouse.move(box['x'] + box['width']/2, box['y'] + box['height']/2, steps=15)
                        time.sleep(random.uniform(0.5, 1.2))
                        checkbox.click()
                        time.sleep(3)
                    break
            except:
                pass
        
        time.sleep(1)
    return False

def human_delay(min_s=2, max_s=5):
    time.sleep(random.uniform(min_s, max_s))

# ============ SCRAPING FUNCTIONS ============
def scrape_article_content(page, url):
    """Scrape full article content using Playwright (for older articles)"""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        human_delay(2, 4)
        
        if not wait_for_cloudflare_bypass(page, max_wait=30):
            # Wait for manual intervention if needed
            print("    Waiting 30s for manual Cloudflare verification...")
            time.sleep(30)
        
        page.wait_for_selector("h1.entry-title", timeout=10000)
        human_delay(1, 2)
        
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        
        row = {}
        row["Title"] = soup.select_one("h1.entry-title")
        row["Title"] = row["Title"].get_text(strip=True) if row["Title"] else "N/A"
        
        author = soup.select_one("a.tw\\:align-top.tw\\:text-lg")
        row["author"] = author.get_text(strip=True) if author else "N/A"
        
        date_elem = soup.find("p", class_="entry-details-date tw:text-sm tw:mb-0")
        if date_elem:
            try:
                row["date"] = str(parse_date_from_text(date_elem.get_text()))
            except:
                row["date"] = date_elem.get_text(strip=True)
        else:
            row["date"] = "N/A"
        
        body_elem = soup.find("div", class_="body-text")
        if body_elem:
            body_str = body_elem.get_text(separator=" ", strip=True)
            pos = body_str.find("Newsletter Sign Up")
            row["body"] = clean_html_text(body_str[:pos] if pos != -1 else body_str)
        else:
            row["body"] = "N/A"
        
        summary = soup.find("h2", class_="deck")
        row["summary"] = summary.get_text(strip=True) if summary else "N/A"
        
        tags = soup.select_one("p.entry-details-categories.tw\\:text-sm")
        row["tag"] = tags.get_text(strip=True) if tags else "N/A"
        
        return row
    except Exception as e:
        print(f"    Error scraping article: {e}")
        return None

def parse_date_from_text(text):
    """Parse date from visible text like 'January 15, 2024'"""
    months = {"January":1,"February":2,"March":3,"April":4,"May":5,"June":6,
              "July":7,"August":8,"September":9,"October":10,"November":11,"December":12,
              "Jan":1,"Feb":2,"Mar":3,"Apr":4,"Jun":6,"Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
    
    parts = text.replace(',', '').split()
    for i, part in enumerate(parts):
        if part in months and i+2 < len(parts) and parts[i+1].isdigit():
            try:
                return datetime(int(parts[i+2]), months[part], int(parts[i+1]))
            except:
                pass
    return datetime.now()

def get_paginated_article_urls(base_url, commodity, max_pages=10):
    """Get article URLs from paginated archive pages"""
    urls = set()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        
        for page_num in range(1, max_pages + 1):
            if page_num == 1:
                url = f"{base_url}/{commodity.lower()}".strip()
            else:
                url = f"{base_url}/{commodity.lower()}/page/{page_num}".strip()
            
            print(f"  Fetching page {page_num}: {url}")
            
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                human_delay(2, 4)
                
                if not wait_for_cloudflare_bypass(page, max_wait=30):
                    print("  Cloudflare blocking pagination - stopping")
                    break
                
                page.wait_for_selector("div.archive-articles-list", timeout=10000)
                html = page.content()
                soup = BeautifulSoup(html, "html.parser")
                
                articles = soup.find("div", class_="archive-articles-list")
                if not articles:
                    print(f"  No more articles found at page {page_num}")
                    break
                
                for article in articles.find_all("article"):
                    time_elem = article.find("time", class_="updated dtstamp")
                    if time_elem:
                        try:
                            article_date = datetime.fromisoformat(time_elem.get("datetime", "").split('+')[0])
                            if article_date.date() < datetime(2024, 1, 1).date():
                                continue  # Stop if we're past our cutoff
                        except:
                            pass
                    
                    h2 = article.find("h2", class_="entry-title")
                    if h2:
                        link = h2.find("a")
                        if link and link.get("href"):
                            urls.add(link.get("href"))
                
                # Check if there's a next page
                next_btn = soup.find("a", class_="next") or soup.find("a", string="Next")
                if not next_btn:
                    print(f"  No more pages after {page_num}")
                    break
                
                human_delay(3, 6)
                
            except Exception as e:
                print(f"  Error on page {page_num}: {e}")
                break
        
        browser.close()
    
    return list(urls)

# ============ MAIN EXECUTION ============
BASE_URL = "https://www.producer.com"
CUT_OFF = datetime(2022, 1, 1)
RSS_CUTOFF = datetime(2025, 11, 1)  # RSS only has articles after this date

RSS_FEEDS = {
    'Canola': 'https://www.producer.com/commodity/canola/feed/',
    'Soybeans': 'https://www.producer.com/commodity/soybeans/feed/',
    'Sunflowers': 'https://www.producer.com/commodity/sunflowers/feed/',
    'Flax': 'https://www.producer.com/commodity/flax/feed/',
    'Wheat': 'https://www.producer.com/commodity/wheat/feed/',
    'Barley': 'https://www.producer.com/commodity/barley/feed/',
    'Oats': 'https://www.producer.com/commodity/oats/feed/',
    'Corn': 'https://www.producer.com/commodity/corn/feed/',
    'Potatoes': 'https://www.producer.com/commodity/potatoes/feed/',
    'Chickpeas': 'https://www.producer.com/commodity/chickpeas/feed/',
}

all_data = []
all_urls = set()

print("="*70)
print("HYBRID SCRAPER: RSS (recent) + Pagination (historical)")
print("="*70)

# STEP 1: Get recent articles from RSS (fast, no Cloudflare)
print("\n[STEP 1] Fetching recent articles from RSS feeds...")
for commodity, rss_url in RSS_FEEDS.items():
    print(f"\n  {commodity}: {rss_url}")
    
    feed = feedparser.parse(rss_url)
    for entry in feed.entries:
        pub_date = parse_date(entry.get('published_parsed'))
        url = entry.get('link')
        
        if url and url not in all_urls:
            all_urls.add(url)
            
            # RSS has full content for recent articles
            if pub_date >= RSS_CUTOFF:
                row = {
                    "scraped_at": datetime.now().isoformat(),
                    "Title": entry.get('title', 'N/A'),
                    "url": url,
                    "date": pub_date.strftime("%Y-%m-%d"),
                    "author": entry.get('author', 'N/A'),
                    "summary": clean_html_text(entry.get('summary', 'N/A')),
                    "body": clean_html_text(entry.get('content', [{}])[0].get('value', 'N/A') if entry.get('content') else entry.get('summary', 'N/A')),
                    "tag": ", ".join([tag.term for tag in entry.get('tags', [])]) if entry.get('tags') else 'N/A',
                    "sector": extract_sector(commodity),
                    "commodity": commodity,
                    "source": "RSS"
                }
                all_data.append(row)
                print(f"    ✓ RSS: {pub_date.strftime('%Y-%m-%d')} - {row['Title'][:40]}...")
            
            time.sleep(random.uniform(0.2, 0.5))

print(f"\n  RSS phase complete: {len(all_data)} recent articles collected")

# STEP 2: Get older articles via pagination (slower, needs Cloudflare handling)
print(f"\n[STEP 2] Fetching historical articles (before {RSS_CUTOFF.strftime('%Y-%m-%d')}) via pagination...")

# Only scrape full content for URLs we haven't processed yet
urls_to_scrape = [url for url in all_urls if url not in [d['url'] for d in all_data]]

if urls_to_scrape:
    print(f"  Found {len(urls_to_scrape)} older articles to scrape...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage", "--no-sandbox"]
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        # Apply stealth if available
        try:
            from playwright_stealth import stealth
            stealth(page)
        except:
            pass
        
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
        """)
        
        for idx, url in enumerate(urls_to_scrape[:20]):  # Limit to 20 for testing
            commodity = extract_commodity_from_url(url)
            print(f"\n  [{idx+1}/{min(20, len(urls_to_scrape))}] Scraping: {url[:70]}...")
            
            row = scrape_article_content(page, url)
            if row and row.get("Title") != "N/A":
                row["scraped_at"] = datetime.now().isoformat()
                row["url"] = url
                row["sector"] = extract_sector(commodity)
                row["commodity"] = commodity
                row["source"] = "Pagination"
                all_data.append(row)
                print(f"    ✓ Success: {row['Title'][:40]}...")
            
            human_delay(5, 10)  # Important: delay between articles
        
        browser.close()
else:
    print("  No older articles need scraping (RSS covered everything)")

# SAVE RESULTS
if all:
    df = pd.DataFrame(all_data)
    df = df.drop_duplicates(subset=['url'], keep='first')
    
    filename = f"producer_hybrid_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    
    print(f"\n{'='*70}")
    print(f"COMPLETE! Saved {len(df)} articles to {filename}")
    print(f"  - RSS source: {len([d for d in all_data if d.get('source')=='RSS'])} articles")
    print(f"  - Pagination source: {len([d for d in all_data if d.get('source')=='Pagination'])} articles")
    print(f"{'='*70}")
else:
    print("\nNo articles were successfully scraped")
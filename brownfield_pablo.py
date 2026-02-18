#!/usr/bin/env python3
"""
Brownfield scraper worker - outputs fragment CSV (with full body) + per-article TXT files
Usage: python brownfield_worker.py --start-page 1 --end-page 155 --worker-id 1
"""
import argparse
import sys
import time
import random
from pathlib import Path
from datetime import datetime
import re
import csv
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

def sanitize_filename(name, max_len=40):
    name = re.sub(r'[<>:"/\\|?*]', '', str(name))
    return re.sub(r'\s+', '_', name.strip())[:max_len] or 'untitled'

def parse_date(s):
    month_map = {
        "January": "01", "Jan": "01", "February": "02", "Feb": "02", "March": "03", "Mar": "03",
        "April": "04", "Apr": "04", "May": "05", "June": "06", "Jun": "06", "July": "07", "Jul": "07",
        "August": "08", "Aug": "08", "September": "09", "Sep": "09", "Sept": "09", "October": "10", "Oct": "10",
        "November": "11", "Nov": "11", "December": "12", "Dec": "12"
    }
    try:
        parts = s.replace(",", "").split()
        if len(parts) < 3:
            return None
        year = parts[2]
        month = month_map.get(parts[0], "01")
        day = parts[1].zfill(2)
        return datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d").date()
    except Exception as e:
        print(f"  ⚠️ Date parse error for '{s}': {e}")
        return None

def safe_goto(page, url, retries=5):
    """Navigate with Cloudflare challenge handling"""
    for attempt in range(retries):
        try:
            if attempt > 0:
                delay = 2 ** attempt + random.uniform(0, 1)
                print(f"  ⏳ Retry {attempt+1}/{retries} after {delay:.1f}s...")
                time.sleep(delay)
            
            page.goto(url, wait_until="networkidle", timeout=90000)
            
            # Check for Cloudflare challenge
            if page.query_selector("div.cf-browser-verification") or page.query_selector("div#challenge-running"):
                print(f"  🛡️ Cloudflare challenge detected - waiting 15s...")
                page.wait_for_timeout(15000)
                if page.query_selector("div.cf-browser-verification") or page.query_selector("div#challenge-running"):
                    print(f"  ❌ Still blocked after waiting")
                    continue
            
            # Verify content loaded
            if page.query_selector("div.entry-content.cat-container") or page.query_selector("p.post_title"):
                print(f"  ✅ Page loaded successfully")
                page.wait_for_timeout(2000)
                return True
            else:
                print(f"  ⚠️ Page loaded but no content found")
                continue
                
        except PlaywrightTimeoutError:
            print(f"  ⏱️ Timeout on attempt {attempt+1}/{retries}")
            continue
        except Exception as e:
            print(f"  ❌ Navigation error (attempt {attempt+1}): {type(e).__name__}: {str(e)[:80]}")
            continue
    
    print(f"  ❌ All {retries} navigation attempts failed")
    return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start-page', type=int, required=True, help='Starting page number')
    parser.add_argument('--end-page', type=int, required=True, help='Ending page number')
    parser.add_argument('--worker-id', type=int, required=True, help='Worker ID (1-4)')
    parser.add_argument('--output-dir', type=str, default='brownfield_output', help='Output directory')
    args = parser.parse_args()

    OUTPUT_DIR = Path(args.output_dir)
    ARTICLES_DIR = OUTPUT_DIR / 'articles'
    FRAGMENTS_DIR = OUTPUT_DIR / 'csv_fragments'
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    FRAGMENTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Track already-scraped URLs from existing TXT files
    existing_urls = set()
    for txt_file in ARTICLES_DIR.glob('*.txt'):
        try:
            # Extract URL from first few lines of TXT file
            with open(txt_file, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if line.startswith('URL: '):
                        existing_urls.add(line[5:].strip())
                        break
                    if i > 10:  # Don't read entire file
                        break
        except:
            pass

    print(f"\n{'='*70}")
    print(f"[Worker {args.worker_id}] STARTING")
    print(f"{'='*70}")
    print(f"Pages: {args.start_page}-{args.end_page} ({args.end_page - args.start_page + 1} pages)")
    print(f"Output: {OUTPUT_DIR.absolute()}")
    print(f"Already scraped: {len(existing_urls)} articles")
    print(f"{'='*70}\n")

    # Stagger worker start
    stagger_delay = args.worker_id * 15
    print(f"[Worker {args.worker_id}] ⏳ Staggering start by {stagger_delay}s...")
    time.sleep(stagger_delay)

    # Launch hardened browser
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox', '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-gpu', '--disable-dev-shm-usage',
                '--no-first-run', '--no-default-browser-check',
                '--window-size=1920,1080',
            ]
        )
        
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0"
        ]
        
        context = browser.new_context(
            user_agent=user_agents[args.worker_id % len(user_agents)],
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='America/Chicago',
            java_script_enabled=True,
            bypass_csp=True,
            ignore_https_errors=True,
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.google.com/",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
                "DNT": "1",
            }
        )
        
        # Hide automation fingerprints
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(window, 'navigator', {
                value: new Proxy(navigator, {
                    has: (target, key) => key !== 'webdriver' && key in target,
                    get: (target, key) => key === 'webdriver' ? undefined : target[key]
                })
            });
        """)
        
        page = context.new_page()
        BASE_URL = "https://www.brownfieldagnews.com/crops-markets/"  # CRITICAL: NO TRAILING SPACES!
        fragment_rows = []
        total_scraped = 0
        total_articles_found = 0

        try:
            for page_num in range(args.start_page, args.end_page + 1):
                print(f"\n[Worker {args.worker_id}] 📄 Page {page_num}/{args.end_page}")
                url = BASE_URL if page_num == 1 else f"{BASE_URL}page/{page_num}/"
                print(f"  URL: {url}")
                
                if not safe_goto(page, url):
                    print(f"  ❌ Skipping page {page_num}")
                    time.sleep(10 + random.uniform(0, 5))
                    continue
                
                soup = BeautifulSoup(page.content(), 'html.parser')
                articles_on_page = []
                
                for div in soup.find_all('div', class_='entry-content cat-container'):
                    try:
                        a_tag = div.find('h2').find('a') if div.find('h2') else None
                        if a_tag and a_tag.get('href'):
                            href = a_tag['href'].strip()
                            if href.startswith('/'):
                                href = 'https://www.brownfieldagnews.com' + href
                            elif not href.startswith('http'):
                                href = BASE_URL + href.lstrip('/')
                            articles_on_page.append(href)
                    except:
                        continue
                
                print(f"  ➕ Found {len(articles_on_page)} articles")
                total_articles_found += len(articles_on_page)
                
                for article_url in articles_on_page:
                    if article_url in existing_urls:
                        print(f"  ➤ Skipping (already scraped): {article_url[:50]}...")
                        continue
                    
                    print(f"  📰 Processing: {article_url[:60]}...")
                    
                    if not safe_goto(page, article_url):
                        print(f"  ❌ Failed to load article")
                        continue
                    
                    try:
                        soup = BeautifulSoup(page.content(), 'html.parser')
                        meta = {
                            'url': article_url,
                            'scraped_at': datetime.now().isoformat(),
                            'article_date': None,
                            'title': 'Untitled',
                            'author': 'Unknown',
                            'categories': '',
                            'tags': '',
                            'source': 'Brownfield',
                            'body': ''
                        }
                        
                        # Extract metadata
                        if time_tag := soup.find('time'):
                            meta['article_date'] = parse_date(time_tag.get_text().strip())
                        
                        if title_tag := soup.find('p', class_='post_title'):
                            meta['title'] = title_tag.get_text(strip=True)
                        
                        if author_tag := soup.find('span', class_='entry-author-name'):
                            meta['author'] = author_tag.get_text(strip=True)
                        
                        if cat_span := soup.find('span', class_='entry-categories'):
                            cats = [a.get_text(strip=True) for a in cat_span.find_all('a')]
                            meta['categories'] = '|'.join(cats)
                        
                        if tag_divs := soup.find_all('div', class_='pull-right'):
                            if tag_divs:
                                tags = [a.get_text(strip=True) for a in tag_divs[-1].find_all('a')[1:]]
                                meta['tags'] = '|'.join(tags)
                        
                        # Extract body
                        body_text = ""
                        if body_div := soup.find('div', class_='singleimg'):
                            parts = []
                            current = body_div.next_sibling
                            while current and current.name != 'div':
                                if current.name == 'p' and not current.get('class'):
                                    parts.append(current.get_text(strip=True))
                                current = current.next_sibling
                            body_text = '\n\n'.join(parts)
                        elif content_div := soup.find('div', class_='entry-content'):
                            body_text = content_div.get_text(strip=True)
                        
                        meta['body'] = body_text.strip()
                        
                        # Generate article ID
                        date_prefix = meta['article_date'].strftime('%Y%m%d') if meta['article_date'] else 'nodate'
                        article_id = f"{date_prefix}_{args.worker_id}_{total_scraped:06d}"
                        safe_title = sanitize_filename(meta['title'], 30)
                        
                        # ===== SAVE TXT FILE (metadata + body) =====
                        txt_filename = f"{article_id}_{safe_title}.txt"
                        txt_path = ARTICLES_DIR / txt_filename
                        
                        metadata_block = f"""URL: {meta['url']}
Date: {meta['article_date'] if meta['article_date'] else 'N/A'}
Title: {meta['title']}
Author: {meta['author']}
Categories: {meta['categories']}
Tags: {meta['tags']}
Source: {meta['source']}
Scraped at: {meta['scraped_at']}
Body character count: {len(meta['body']):,}
{'='*70}

"""
                        
                        with open(txt_path, 'w', encoding='utf-8') as f:
                            f.write(metadata_block)
                            f.write(meta['body'])
                        
                        # ===== PREPARE CSV ROW (with full body text) =====
                        fragment_rows.append({
                            'article_id': article_id,
                            'date': meta['article_date'].isoformat() if meta['article_date'] else 'N/A',
                            'title': meta['title'],
                            'author': meta['author'],
                            'categories': meta['categories'],
                            'tags': meta['tags'],
                            'url': meta['url'],
                            'scraped_at': meta['scraped_at'],
                            'source': meta['source'],
                            'body_char_count': len(meta['body']),
                            'body': meta['body']  # FULL TEXT IN CSV COLUMN
                        })
                        
                        total_scraped += 1
                        existing_urls.add(article_url)
                        
                        print(f"  ✅ Saved [{total_scraped}] {meta['title'][:40]} ({len(meta['body']):,} chars)")
                        
                        # Human-like delay
                        delay = 2.5 + random.uniform(0, 2.0) + (args.worker_id * 0.4)
                        time.sleep(delay)
                        
                    except Exception as e:
                        print(f"  ❌ Error processing article: {type(e).__name__}: {str(e)[:100]}")
                        import traceback
                        traceback.print_exc()
                        continue
                
                # Delay between pages
                page_delay = 4.0 + random.uniform(0, 3.0) + (args.worker_id * 0.6)
                print(f"  ⏳ Waiting {page_delay:.1f}s before next page...")
                time.sleep(page_delay)
        
        finally:
            browser.close()
    
    # ===== WRITE FRAGMENT CSV (with full body text) =====
    if fragment_rows:
        fragment_csv = FRAGMENTS_DIR / f"fragment_worker_{args.worker_id}_{args.start_page}_{args.end_page}.csv"
        
        # Define column order (body LAST to avoid truncation issues in Excel previews)
        columns = [
            'article_id', 'date', 'title', 'author', 'categories', 'tags', 
            'url', 'scraped_at', 'source', 'body_char_count', 'body'
        ]
        
        with open(fragment_csv, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(fragment_rows)
        
        print(f"\n✅ Worker {args.worker_id} fragment saved: {fragment_csv.name}")
        print(f"   Articles scraped: {len(fragment_rows)}")
    
    print(f"\n{'='*70}")
    print(f"[Worker {args.worker_id}] FINISHED")
    print(f"{'='*70}")
    print(f"Pages processed : {args.end_page - args.start_page + 1}")
    print(f"Articles found  : {total_articles_found}")
    print(f"Articles saved  : {total_scraped}")
    print(f"Fragment CSV    : {fragment_csv if fragment_rows else 'None'}")
    print(f"TXT files       : {ARTICLES_DIR.relative_to(OUTPUT_DIR)}/")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    main()
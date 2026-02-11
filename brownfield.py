from bs4 import BeautifulSoup
import requests
import pandas as pd
from datetime import datetime
import time
import re

from playwright.sync_api import sync_playwright

BASE_URL = "https://www.brownfieldagnews.com/crops-markets/"
article_limit = 5
def safe_goto(page, url, retries=3):
    for i in range(retries):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)
            return True
        except Exception as e:
            print(f"⚠️ Retry {i+1}/{retries} failed for {url}: {e}")
            time.sleep(5)
    return False
def parse_date(s):
    month = {
        "January": "01", "Jan": "01",
        "February": "02", "Feb": "02", 
        "March": "03", "Mar": "03",
        "April": "04", "Apr": "04",
        "May": "05",
        "June": "06", "Jun": "06",
        "July": "07", "Jul": "07",
        "August": "08", "Aug": "08",
        "September": "09", "Sep": "09", "Sept": "09",
        "October": "10", "Oct": "10",
        "November": "11", "Nov": "11",
        "December": "12", "Dec": "12"
    }
    l = s.split(sep=' ')
    year = l[2]
    m = month[l[0]]
    day = l[1].replace(",", "")
    if int(day) < 10:
        day = '0' + day
    date = year + "-" + m + "-" + day
    format_str = "%Y-%m-%d"
    datetime_object = datetime.strptime(date, format_str).date()
    return datetime_object

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=50)

    context = browser.new_context(
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    viewport={"width": 1280, "height": 800},
    locale="en-US",
    timezone_id="America/Chicago",
    ignore_https_errors=True
)


    page = context.new_page()
    
    print("Navigating to:", BASE_URL)
    
    try:
        # Increase timeout to 60 seconds and use 'domcontentloaded' instead of 'load'
        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
        print("Page loaded successfully!")
        
        # Wait a bit for any additional content
        page.wait_for_timeout(3000)
        
        # Get article links
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        urls = []
        
        for div in soup.find_all("div", class_="entry-content cat-container"):
            try:
                href = div.find("h2").find("a").get("href")
                urls.append(href)
                print(f"Found URL: {href}")
            except:
                print("No URL found in a div")
        
        print(f"\nTotal URLs found: {len(urls)}")
        print(urls)
        # AFTER extracting urls list - ADD THIS:
        urls = [u.strip() for u in urls if u.strip()]  # CRITICAL: Remove trailing spaces

        data = []
        for url in urls[:article_limit]:  # Use article_limit properly
            print(f"\n➡️ Processing: {url}")
            if not safe_goto(page, url):
                print(f"❌ Navigation failed for {url}")
                continue
                
            try:
                soup = BeautifulSoup(page.content(), "html.parser")
                row = {
                    "url": url,
                    "scraped_at": datetime.now().strftime('%Y%m%d_%H%M%S'),
                    "article_date": None,
                    "title": None,
                    "author": None,
                    "categories": "",
                    "tags": "",
                    "body": "",
                    "len": 0
                }
                
                # --- Date (with validation) ---
                if (time_tag := soup.find("time")):
                    try:
                        row["article_date"] = parse_date(time_tag.get_text().strip())
                    except Exception as e:
                        print(f"⚠️ Date parse error: {e}")
                
                # --- Title ---
                if (title_tag := soup.find("p", class_="post_title")):
                    row["title"] = title_tag.get_text(strip=True)
                
                # --- Author ---
                if (author_tag := soup.find("span", class_="entry-author-name")):
                    row["author"] = author_tag.get_text(strip=True)
                
                # --- Categories ---
                if (cat_span := soup.find("span", class_="entry-categories")):
                    cats = [a.get_text(strip=True) for a in cat_span.find_all("a")]
                    row["categories"] = "|".join(cats)
                
                # --- TAGS FIX: Use find_all + last element ---
                tag_divs = soup.find_all("div", class_="pull-right")
                if tag_divs:
                    tag_container = tag_divs[-1]  # Get LAST matching div
                    tags = [a.get_text(strip=True) for a in tag_container.find_all("a")[1:]]  # Skip "Tags:" label
                    row["tags"] = "|".join(tags)
                
                # --- CORRECT BODY EXTRACTION FOR CLASSLESS <p> TAGS ---
                body_div = soup.find("div", class_="singleimg")  # FIXED: single underscore
                if body_div:
                    body_parts = []
                    current = body_div
                    
                    # Traverse ALL following siblings until next div
                    while True:
                        current = current.next_sibling
                        if current is None or current.name == "div":
                            break
                            
                        # ONLY collect classless <p> tags
                        if current.name == "p" and not current.has_attr("class"):
                            body_parts.append(current.get_text(strip=True))
                    
                    row["body"] = "\n\n".join(body_parts)
                    row["len"] = len(row["body"])
                else:
                    # Fallback: try main content container
                    content_div = soup.find("div", class_="entry-content")
                    if content_div:
                        row["body"] = content_div.get_text(strip=True)
                        row["len"] = len(row["body"])
                    else:
                        row["body"] = ""
                        row["len"] = 0
                
                data.append(row)
                print(f"✅ Parsed: {row['title'][:50]}...")
                
            except Exception as e:
                print(f"❌ PARSE ERROR for {url}: {type(e).__name__}: {str(e)[:100]}")
                import traceback
                traceback.print_exc()
                continue  # Skip to next article



        
        
    except Exception as e:
        print(f"Error loading page: {e}")
    
    finally:
        browser.close()
        print("Browser closed")
    if data:
        df = pd.DataFrame(data)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"brownfield_articles_{timestamp}.csv"
        df.to_csv(filename, index=False, encoding='utf-8')
        print(f"\n✓ Scraped {len(data)} articles successfully!")
        print(df[["scraped_at", "title", "len"]].head())
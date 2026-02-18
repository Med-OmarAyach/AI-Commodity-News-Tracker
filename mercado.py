import pandas as pd  # Added missing import
from bs4 import BeautifulSoup
from datetime import datetime
from playwright.sync_api import sync_playwright
import time

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
    l = s.split()  
    year = l[2]                   
    m = month[l[0]]               
    day = l[1].rstrip(',')     
    
    if int(day) < 10:
        day = '0' + day
    
    date_str = f"{year}-{m}-{day}"
    return datetime.strptime(date_str, "%Y-%m-%d").date()

# Configuration
BASE_URL = "https://mecardo.com.au/category/grains-oilseeds".strip()  # Fixed trailing spaces
CUT_OFF = datetime(2016, 1, 1).date()
MAX_PAGES = 40  # Safety limit
TIMEOUT = 10000  # 10 seconds

def find_next_button(page):
    """Robust next-button detection with multiple fallback selectors"""
    selectors = [
        'a.next.page-numbers',          # WordPress standard
        'a.pagination-next',            # Common class
        '.elementor-pagination-next a', # Elementor-specific
        'li.next a',                    # List-based pagination
        'a:has-text("Next")',           # Text-based fallback
        'a:has-text("›")'               # Arrow symbol fallback
    ]
    
    for selector in selectors:
        try:
            btn = page.locator(selector).first
            if btn.is_visible() and btn.is_enabled():
                return btn
        except:
            continue
    return None

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    try:
        page.goto(BASE_URL, wait_until="domcontentloaded")
        page.wait_for_selector("article", timeout=TIMEOUT)
    except Exception as e:
        print(f"Initial page load failed: {e}")
        browser.close()
        exit(1)
    
    article_links = []
    current_page = 1
    stop_scraping = False
    
    while current_page <= MAX_PAGES and not stop_scraping:
        print(f"Processing page {current_page}...")
        
        try:
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            articles = soup.find_all("article")
            
            if not articles:
                print("No articles found on page - stopping")
                break
            
            # Process articles on current page
            for article in articles:
                try:
                    # Extract link
                    a_tag = article.find("a", href=True)
                    if not a_tag:
                        continue
                    href = a_tag["href"]
                    
                    # Extract and parse date
                    date_span = article.find("span", class_="elementor-post-date")
                    if not date_span:
                        continue
                    date_str = date_span.get_text(strip=True)
                    article_date = parse_date(date_str)
                    
                    # Check cutoff
                    if article_date < CUT_OFF:
                        print(f"Reached cutoff date ({article_date}) - stopping pagination")
                        stop_scraping = True
                        break
                    
                    article_links.append(href)
                    print(f"  Added: {href} (Date: {article_date})")
                    
                except Exception as e:
                    # Skip problematic articles but continue processing
                    continue
            
            if stop_scraping:
                break
            
            # Find and click next button
            next_btn = find_next_button(page)
            if not next_btn:
                print("No next page button found - stopping")
                break
            
            # Click with safety checks
            next_btn.scroll_into_view_if_needed()
            next_btn.click(timeout=5000)
            
            # Wait for navigation and new content
            page.wait_for_load_state("networkidle", timeout=TIMEOUT)
            page.wait_for_selector("article", timeout=TIMEOUT)
            
            # Small buffer to avoid rate limiting
            time.sleep(1.5)
            current_page += 1
            
        except Exception as e:
            print(f"Error on page {current_page}: {e}")
            break
    
    data=[]
    for i, url in enumerate(article_links):
        try:
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            row={}
            row["scraped_at"]=datetime.now().isoformat()
            
            # DEFENSIVE CHECKS ADDED BELOW (only changes)
            date_elem = soup.find("span",class_="elementor-icon-list-text elementor-post-info__item elementor-post-info__item--type-date")
            if not date_elem:
                print(f"{url} skipped: date element not found")
                continue
            date_str = date_elem.get_text().strip()
            row["date"]=parse_date(date_str)
            
            title_elem = soup.find("h1",class_="elementor-heading-title elementor-size-default")
            if not title_elem:
                print(f"{url} skipped: title element not found")
                continue
            title = title_elem.get_text().strip()
            row["title"]=title
            
            author_elem = soup.find("span",class_="elementor-icon-list-text elementor-post-info__item elementor-post-info__item--type-author")
            row["author"] = author_elem.get_text().split(sep="By")[-1].strip() if author_elem else "Unknown"
            
            sector = soup.find_all("a",class_="elementor-post-info__terms-list-item")[0]
            row["sector"] = sector.get_text().strip() if sector else "Unknown"
            tag_elem = soup.find_all("a",class_="elementor-post-info__terms-list-item")[1]
            row["tag"] = tag_elem.get_text().strip() if tag_elem else "Unknown"
            
    
            body_elem = soup.find("div",class_="elementor-column elementor-col-66 elementor-inner-column elementor-element elementor-element-6aa3776")
            if not body_elem:
                print(f"{url} skipped: body element not found")
                continue
            body = body_elem.get_text().strip()
            l = body.split(sep="What does it mean?")
            row["body"] = l[0]
            row["explanation"] = l[1] if len(l) > 1 else ""
            
            kpoints_elem = soup.find("div",class_="elementor-element elementor-element-8714261 elementor-widget elementor-widget-text-editor")
            row["key points"] = kpoints_elem.get_text().strip() if kpoints_elem else ""
            
            row["URL"] = url
            data.append(row)
            print(f"treated url number {i}: {url}")
        except Exception as e:
            print(f"{url} page load failed: {e}")
            continue  # Continue to next article instead of exiting
    
    browser.close()

# Results
print(f"\n✅ Collected {len(article_links)} article links newer than {CUT_OFF}")
print(f"✅ Successfully scraped {len(data)} articles")
print("\nSample links:")
for link in article_links[:5]:
    print(f"  - {link}")
if len(article_links) > 5:
    print(f"  ... and {len(article_links) - 5} more")
df=pd.DataFrame(data)
filename = f"mercadoF1.csv"
df.to_csv(filename, index=False, encoding='utf-8-sig')
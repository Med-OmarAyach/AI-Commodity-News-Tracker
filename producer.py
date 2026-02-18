from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time
import random
from playwright.sync_api import sync_playwright

try:
    from playwright_stealth import stealth
    USE_STEALTH = True
except ImportError:
    USE_STEALTH = False
def handle_cloudflare_checkbox(page, max_wait=45):
    """Specifically handle Cloudflare verification checkbox"""
    print("  Checking for Cloudflare verification...")
    
    for i in range(max_wait):
        content = page.content()
        
        # Check if verification completed
        if "Just a moment" not in content and "Verification successful" not in content:
            if page.query_selector("h1.entry-title") or page.query_selector("div.archive-articles-list"):
                print(f"  Content loaded at {i+1}s")
                return True
        
        # Try MULTIPLE checkbox selectors (Cloudflare uses different ones)
        checkbox_selectors = [
            "input[type='checkbox']",
            "#challenge-stage input",
            ".cf-turnstile-wrapper input",
            "iframe[src*='challenges.cloudflare.com']",
            "[data-testid='challenge-checkbox']",
            ".h-12.w-12",  # Cloudflare's checkbox button
            "button[type='button']",  # Sometimes it's a button
        ]
        
        for selector in checkbox_selectors:
            try:
                checkbox = page.query_selector(selector)
                if checkbox:
                    print(f"  Found verification element at {i+1}s, attempting click...")
                    
                    # Human-like: Move mouse to checkbox first
                    box = checkbox.bounding_box()
                    if box:
                        # Move mouse in arc to checkbox (human-like)
                        page.mouse.move(box['x'] + box['width']/2, box['y'] + box['height']/2, steps=20)
                        time.sleep(random.uniform(0.5, 1.5))
                        
                        # Click with human-like timing
                        checkbox.click()
                        print("  Checkbox clicked!")
                    
                    # Wait for verification to complete
                    for j in range(30):
                        time.sleep(1)
                        new_content = page.content()
                        if "Just a moment" not in new_content and "Verification successful" not in new_content:
                            if page.query_selector("h1.entry-title"):
                                print("  Verification complete!")
                                return True
                    break
            except Exception as e:
                pass
        
        time.sleep(1)
    
    print(f"  No checkbox found or verification timed out after {max_wait}s")
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
    l = s.split()  
    year = l[2]                   
    m = month[l[0]]               
    day = l[1].rstrip(',')     
    
    if int(day) < 10:
        day = '0' + day
    
    date_str = f"{year}-{m}-{day}"
    return datetime.strptime(date_str, "%Y-%m-%d").date()

def human_delay(min_sec=2, max_sec=5):
    """Random delay like a human thinking"""
    time.sleep(random.uniform(min_sec, max_sec))

def human_scroll(page):
    """Scroll like a human reading the page"""
    try:
        # Scroll down in increments
        for i in range(random.randint(3, 7)):
            page.mouse.wheel(0, random.randint(100, 300))
            time.sleep(random.uniform(0.3, 0.8))
        
        # Scroll back up a bit
        page.mouse.wheel(0, -random.randint(50, 150))
        time.sleep(random.uniform(0.2, 0.5))
        
        # Scroll to bottom
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(random.uniform(0.5, 1.5))
        
        # Scroll back to top
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(random.uniform(0.3, 0.7))
    except:
        pass

def human_mouse_movement(page):
    """Move mouse in human-like patterns"""
    try:
        # Random mouse movements
        for i in range(random.randint(2, 5)):
            x = random.randint(100, 1800)
            y = random.randint(100, 900)
            page.mouse.move(x, y, steps=random.randint(10, 30))
            time.sleep(random.uniform(0.2, 0.6))
    except:
        pass

def wait_for_cloudflare_bypass(page, max_wait=45):
    """Wait for Cloudflare with human-like patience"""
    print(f"  Waiting for security verification...")
    
    for i in range(max_wait):
        content = page.content()
        
        # Check if Cloudflare page is gone
        if "Just a moment" not in content and "cloudflare" not in content.lower():
            # Verify actual content loaded
            if page.query_selector("h1.entry-title") or page.query_selector("div.archive-articles-list"):
                print(f"  Verification complete at {i+1}s")
                human_delay(1, 2)  # Human pause after page loads
                return True
        
        # Try clicking checkbox if it appears (with human timing)
        try:
            checkbox = page.query_selector("input[type='checkbox']")
            if checkbox:
                print(f"  Clicking verification checkbox...")
                human_delay(0.5, 1.5)  # Human thinks before clicking
                checkbox.click()
                human_delay(2, 4)  # Wait for verification
        except:
            pass
        
        # Random small delays between checks (humans don't check constantly)
        if i % 3 == 0:
            time.sleep(random.uniform(0.8, 1.5))
        else:
            time.sleep(1)
    
    print(f"  Timeout after {max_wait}s")
    return False
    
BASE_URL = "https://www.producer.com/commodity"
sectors = {"Oil Seeds": ["Canola", "Soybeans", "Sunflowers", "Flax"], 
           "Cereals": ["Wheat", "Barley", "Oats", "Corn"], 
           "Field Crops": ["Potatoes"], 
           "Pulses": ["Chickpeas"]}
CUT_OFF = datetime(2023, 1, 1).date()

all_data = []

with sync_playwright() as p:
    for sector in sectors:
        for commodity in sectors[sector]:
            Current_url = f"{BASE_URL}/{commodity.lower()}".strip()
            print(f"\n{'='*60}")
            print(f"Processing {commodity}: {Current_url}")
            print(f"{'='*60}")
            
            # MUST be headless=False for human-like behavior
            browser = p.chromium.launch(
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-web-security",
                    "--window-size=1920,1080",
                ]
            )
            
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="en-US",
                timezone_id="America/Chicago",
            )
            
            page = context.new_page()
            
            # Apply stealth
            if USE_STEALTH:
                try:
                    stealth(page)
                except:
                    pass
            
            # Advanced anti-detection scripts
            page.add_init_script("""
                // Hide webdriver
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Fake plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                // Fake languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                
                // Fake hardware
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => 8
                });
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => 8
                });
                
                // Remove automation flags
                delete navigator.__proto__.webdriver;
            """)
            
            try:
                # Navigate to page
                page.goto(Current_url, wait_until="domcontentloaded", timeout=60000)
                
                # Human-like delay before any interaction
                time.sleep(random.uniform(2, 4))
                
                # Handle Cloudflare checkbox specifically
                handle_cloudflare_checkbox(page, max_wait=45)
                
                # Additional wait for content to fully load after verification
                time.sleep(random.uniform(3, 6))
                
                # Human-like scrolling
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)
                page.evaluate("window.scrollTo(0, 0)")
                time.sleep(1)
                
                # Wait for articles container
                try:
                    page.wait_for_selector("div.archive-articles-list", timeout=10000)
                except:
                    print(f"Could not find articles container for {commodity}")
                    browser.close()
                    continue

                html = page.content()
                
                # Final check - if still blocked, wait for manual intervention
                if "Just a moment" in html or "Verification successful" in html:
                    print("Still on Cloudflare page - waiting 60s for manual verification...")
                    print("PLEASE CLICK THE CHECKBOX IF IT APPEARS")
                    time.sleep(60)
                    
                    # Check again after manual intervention
                    html = page.content()
                    if "Just a moment" in html:
                        print("Still blocked, skipping...")
                        browser.close()
                        continue
                
                soup = BeautifulSoup(html, "html.parser")
                article_links = set()
                articles = soup.find("div", class_="archive-articles-list")
                
                if articles is None:
                    browser.close()
                    continue
                
                for article in articles.find_all("article"):
                    time_elem = article.find("time", class_="updated dtstamp")
                    if time_elem:
                        datetime_str = time_elem.get("datetime", "")
                        try:
                            article_date = datetime.fromisoformat(datetime_str)
                            if article_date.date() < CUT_OFF:
                                continue
                        except:
                            continue
                    
                    h2 = article.find("h2", class_="entry-title")
                    if h2:
                        link_tag = h2.find("a")
                        if link_tag:
                            href = link_tag.get("href")
                            if href:
                                article_links.add(href)

                article_links = list(article_links)
                print(f"{commodity}: {len(article_links)} articles found")
                
                # Scrape article content
                for idx, url in enumerate(article_links):
                    print(f"Scraping {idx+1}/{min(5, len(article_links))}...")
                    
                    try:
                        # Human-like: Random delay before opening article
                        human_delay(2, 5)
                        
                        # Navigate to article
                        page.goto(url, wait_until="domcontentloaded", timeout=60000)
                        
                        # Human-like: Wait for page to "load"
                        human_delay(2, 4)
                        
                        # Human mouse movement
                        human_mouse_movement(page)
                        
                        # Wait for Cloudflare on article page
                        wait_for_cloudflare_bypass(page, max_wait=30)
                        
                        # Human-like scrolling
                        human_scroll(page)
                        
                        article_html = page.content()
                        
                        if "Just a moment" in article_html:
                            print("Blocked on article page, waiting for manual verify...")
                            time.sleep(30)
                            article_html = page.content()
                            
                            if "Just a moment" in article_html:
                                print("Still blocked, skipping...")
                                continue
                        
                        # Wait for article content to render
                        try:
                            page.wait_for_selector("h1.entry-title", timeout=10000)
                        except:
                            print("Article content didn't load...")
                            continue
                        
                        # Human-like: Wait before scraping (like reading)
                        human_delay(1, 3)
                        
                        soup = BeautifulSoup(article_html, "html.parser")
                        
                        row = {}
                        row["scraped_at"] = datetime.now().isoformat()
                        row["url"] = url
                        row["sector"] = sector
                        row["commodity"] = commodity
                        
                        title_elem = soup.select_one("h1.entry-title")
                        row["Title"] = title_elem.get_text(strip=True) if title_elem else "N/A"
                        
                        author_elem = soup.select_one("a.tw\\:align-top.tw\\:text-lg")
                        row["author"] = author_elem.get_text(strip=True) if author_elem else "N/A"
                        
                        date_elem = soup.find("p", class_="entry-details-date tw:text-sm tw:mb-0")
                        if date_elem:
                            try:
                                row["date"] = str(parse_date(date_elem.get_text()))
                            except:
                                row["date"] = date_elem.get_text(strip=True)
                        else:
                            row["date"] = "N/A"
                        
                        body_elem = soup.find("div", class_="body-text")
                        if body_elem:
                            body_str = body_elem.get_text(separator=" ", strip=True)
                            pos = body_str.find("Newsletter Sign Up")
                            row["body"] = body_str[:pos] if pos != -1 else body_str
                        else:
                            row["body"] = "N/A"
                        
                        summary_elem = soup.find("h2", class_="deck")
                        row["summary"] = summary_elem.get_text(strip=True) if summary_elem else "N/A"
                        
                        tag_elem = soup.select_one("p.entry-details-categories.tw\\:text-sm")
                        row["tag"] = tag_elem.get_text(strip=True) if tag_elem else "N/A"
                        
                        all_data.append(row)
                        print(f"Success: {row['Title'][:40]}...")
                        
                        # Human-like: Delay between articles
                        human_delay(3, 7)
                        
                    except Exception as e:
                        print(f"Error: {e}")
                        continue
                
                # Human-like: Delay between commodities
                human_delay(5, 10)
                
            except Exception as e:
                print(f"Error processing {commodity}: {e}")
            finally:
                browser.close()
                time.sleep(3)

# Save all data
if all:
    df = pd.DataFrame(all_data)
    filename = f"producer_scraped_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f"\nSaved {len(all_data)} articles to {filename}")
else:
    print("\nNo articles were successfully scraped")
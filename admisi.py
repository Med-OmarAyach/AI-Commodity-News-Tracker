from bs4 import BeautifulSoup
from datetime import datetime
from playwright.sync_api import sync_playwright
import urllib.parse
import time

# ======================
# 🔑 CONFIGURATION (MODIFY THESE FOR TESTING/PRODUCTION)
# ======================
BASE_URL = "https://www.admisi.com/market-information/grains/"  # Grain-filtered source
CUTOFF = datetime(2026, 1, 1)  # Stop when encountering first article OLDER than this

# TESTING SAFEGUARDS (set to None for full production run)
MAX_CANDIDATE_URLS = 10      # Max URLs to collect from listing page (Phase 1)
MAX_ARTICLES_TO_PROCESS = 5  # Max article pages to OPEN/VALIDATE (Phase 2)
MAX_LOADS = 5                # Max "Load More" clicks during candidate collection

# ARTICLE VALIDATION HEURISTICS (adjust based on site inspection)
DATE_SELECTORS = [
    "time", 
    "span.date", 
    ".article-date", 
    "div.meta time",
    "[itemprop='datePublished']"
]
DATE_FORMATS = [
    "%B %d, %Y",    # "January 15, 2026"
    "%m/%d/%Y",     # "01/15/2026"
    "%Y-%m-%d",     # "2026-01-15"
    "%d %B %Y"      # "15 January 2026"
]
CONTENT_SELECTOR = ".article-content, .content, div[itemprop='articleBody']"  # Main text container
MIN_TEXT_LENGTH = 300  # Skip if article text < this (filters video-only)
VIDEO_SELECTORS = "video, iframe[src*='youtube'], iframe[src*='vimeo'], .video-player"

# ======================
# 🚀 SCRAPER EXECUTION
# ======================
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=100)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 900},
        locale="en-US",
        timezone_id="America/Chicago"
    )
    page = context.new_page()
    
    print(f"🚀 Navigating to grains page: {BASE_URL}")
    try:
        # ===== PHASE 0: INITIAL PAGE LOAD & SETUP =====
        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
        print("✓ Grains page loaded")
        
        # Handle cookie banner
        try:
            cookie_selectors = [
                "button:has-text('Accept')",
                "#onetrust-accept-btn-handler",
                "[data-testid='accept-cookies']"
            ]
            for selector in cookie_selectors:
                if page.locator(selector).is_visible(timeout=2000):
                    page.click(selector)
                    print("✓ Cookies accepted")
                    page.wait_for_timeout(800)
                    break
        except Exception as e:
            print(f"ℹ Cookie handling: {str(e)[:70]}")
        
        # CRITICAL: Click written_commentary tab to load grain commentary
        print("\n🖱️ Clicking #written_commentary tab...")
        try:
            page.wait_for_selector("#written_commentary", state="visible", timeout=10000)
            page.click("#written_commentary")
            # Wait for content reload (networkidle + visible articles)
            page.wait_for_load_state("networkidle", timeout=15000)
            page.wait_for_selector("div.col-sm-6", state="visible", timeout=10000)
            print("✓ Commentary section loaded successfully!")
        except Exception as e:
            print(f"⚠️ WARNING: Tab click failed - proceeding anyway: {str(e)[:100]}")
            # Continue anyway - might be auto-loaded
        
        # ===== PHASE 1: COLLECT CANDIDATE URLS (from listing page) =====
        print("\n" + "="*60)
        print(f"🔍 PHASE 1: Collecting candidate URLs (max: {MAX_CANDIDATE_URLS or '∞'})")
        print("="*60)
        
        candidate_urls = []
        load_count = 0
        stop_loading = False
        
        while not stop_loading and load_count < MAX_LOADS:
            if MAX_CANDIDATE_URLS and len(candidate_urls) >= MAX_CANDIDATE_URLS:
                print(f"ℹ Reached MAX_CANDIDATE_URLS ({MAX_CANDIDATE_URLS})")
                break
                
            soup = BeautifulSoup(page.content(), "html.parser")
            article_divs = soup.find_all("div", class_="col-sm-6")
            new_urls = 0
            
            print(f"\n📦 Batch #{load_count + 1}: Found {len(article_divs)} article containers")
            
            for div in article_divs:
                try:
                    a_tag = div.find("a", href=True)
                    if not a_tag or not a_tag["href"].strip():
                        continue
                    
                    full_url = urllib.parse.urljoin(BASE_URL, a_tag["href"].strip())
                    if full_url in candidate_urls:
                        continue
                    
                    candidate_urls.append(full_url)
                    new_urls += 1
                    
                    if MAX_CANDIDATE_URLS and len(candidate_urls) >= MAX_CANDIDATE_URLS:
                        break
                except Exception as e:
                    continue
            
            print(f"   → Added {new_urls} new URLs (Total: {len(candidate_urls)})")
            
            # Check for Load More button
            if MAX_CANDIDATE_URLS and len(candidate_urls) >= MAX_CANDIDATE_URLS:
                break
                
            load_more_found = False
            load_more_selectors = [
                "button:has-text('Load More')",
                "a:has-text('Load More')",
                ".load-more-button"
            ]
            
            for selector in load_more_selectors:
                try:
                    btn = page.locator(selector)
                    if btn.is_visible(timeout=2000):
                        print(f"\n🖱️ Clicking 'Load More' (Batch #{load_count + 2})...")
                        btn.click()
                        page.wait_for_load_state("networkidle", timeout=10000)
                        page.wait_for_timeout(1200)
                        load_count += 1
                        load_more_found = True
                        break
                except:
                    continue
            
            if not load_more_found:
                print("ℹ No 'Load More' button found - all content loaded")
                break
        
        if not candidate_urls:
            print("\n❌ NO CANDIDATE URLS COLLECTED! Check page structure.")
            browser.close()
            exit(1)
        
        print(f"\n✅ Phase 1 Complete: {len(candidate_urls)} candidate URLs collected")
        print(f"   First URL sample: {candidate_urls[0][:70]}...")
        
        # ===== PHASE 2: VALIDATE ARTICLES (open pages, check date + content) =====
        print("\n" + "="*60)
        print(f"🔍 PHASE 2: Validating articles (max to process: {MAX_ARTICLES_TO_PROCESS or '∞'})")
        print(f"   CUTOFF DATE: {CUTOFF.strftime('%Y-%m-%d')} | MIN TEXT: {MIN_TEXT_LENGTH} chars")
        print("="*60)
        
        final_urls = []
        skipped_videos = 0
        processed_count = 0
        cutoff_reached = False
        
        for idx, url in enumerate(candidate_urls, 1):
            # Enforce processing limit
            if MAX_ARTICLES_TO_PROCESS and processed_count >= MAX_ARTICLES_TO_PROCESS:
                print(f"\n🛑 STOPPED: Reached MAX_ARTICLES_TO_PROCESS ({MAX_ARTICLES_TO_PROCESS})")
                break
            
            if cutoff_reached:
                break
                
            print(f"\n[{idx}/{len(candidate_urls)}] Opening: {url[:65]}...")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(800)  # Visual stability
                
                # ===== EXTRACT DATE FROM ARTICLE PAGE =====
                article_date = None
                date_text = None
                for selector in DATE_SELECTORS:
                    try:
                        elem = page.locator(selector).first
                        if elem and elem.is_visible(timeout=2000):
                            date_text = elem.inner_text().strip()
                            # Try all date formats
                            for fmt in DATE_FORMATS:
                                try:
                                    article_date = datetime.strptime(date_text, fmt)
                                    break
                                except ValueError:
                                    continue
                            if article_date:
                                break
                    except:
                        continue
                
                if not article_date:
                    print(f"   ⚠️ Date extraction failed (text: '{date_text[:30] if date_text else 'N/A'}')")
                    continue
                
                # ===== CUTOFF CHECK (STOP IMMEDIATELY IF OLDER) =====
                if article_date < CUTOFF:
                    print(f"   🛑 CUTOFF REACHED: {article_date.strftime('%Y-%m-%d')} < {CUTOFF.strftime('%Y-%m-%d')}")
                    cutoff_reached = True
                    break
                
                # ===== VALIDATE SUBSTANTIAL CONTENT (skip video-only) =====
                has_video = any(page.locator(sel).count() > 0 for sel in VIDEO_SELECTORS.split(", "))
                
                text_length = 0
                for sel in CONTENT_SELECTOR.split(", "):
                    try:
                        elem = page.locator(sel).first
                        if elem and elem.is_visible(timeout=1500):
                            text = elem.inner_text()
                            text_length = len(text.strip())
                            break
                    except:
                        continue
                
                is_video_only = has_video and (text_length < MIN_TEXT_LENGTH)
                
                if is_video_only:
                    skipped_videos += 1
                    print(f"   ⏭️ SKIPPED (video-only): {article_date.strftime('%Y-%m-%d')} | Text: {text_length} chars")
                    continue
                
                # ===== VALID ARTICLE =====
                final_urls.append({
                    "url": url,
                    "date": article_date,
                    "text_length": text_length,
                    "has_video": has_video
                })
                processed_count += 1
                status = "✅ VIDEO+TEXT" if has_video else "✅ TEXT"
                print(f"   {status}: {article_date.strftime('%Y-%m-%d')} | Text: {text_length} chars | {url[:50]}")
                
            except Exception as e:
                print(f"   ❌ Error processing: {str(e)[:100]}")
                continue
        
        # ===== RESULTS SUMMARY =====
        print("\n" + "="*60)
        print("📊 SCRAPE RESULTS")
        print("="*60)
        print(f"Phase 1 Candidates Collected: {len(candidate_urls)}")
        print(f"Phase 2 Articles Processed : {processed_count}")
        print(f"Valid Articles Saved      : {len(final_urls)}")
        print(f"Skipped (Video-Only)      : {skipped_videos}")
        if cutoff_reached:
            print(f"🛑 Stopped at cutoff date: {CUTOFF.strftime('%Y-%m-%d')}")
        if MAX_ARTICLES_TO_PROCESS and processed_count >= MAX_ARTICLES_TO_PROCESS:
            print(f"🛑 Stopped at test limit: {MAX_ARTICLES_TO_PROCESS} articles")
        
        if final_urls:
            print("\n✅ VALID ARTICLES (Newest First):")
            print("-"*60)
            for i, art in enumerate(final_urls, 1):
                marker = "🎬" if art["has_video"] else "📝"
                print(f"{i}. {marker} {art['date'].strftime('%Y-%m-%d')} | {art['url']}")
        else:
            print("\n⚠️ NO VALID ARTICLES FOUND! Check:")
            print("   - Date selectors/formats in configuration")
            print("   - Content selector for text extraction")
            print("   - Whether articles actually contain text content")
        
        # Optional: Save to file
        if final_urls:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"admisi_grain_articles_{timestamp}.txt"
            with open(filename, "w") as f:
                f.write(f"Scraped on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Cutoff date: {CUTOFF.strftime('%Y-%m-%d')}\n")
                f.write(f"Valid articles: {len(final_urls)}\n\n")
                for art in final_urls:
                    f.write(f"{art['date'].strftime('%Y-%m-%d')} | {art['url']}\n")
            print(f"\n💾 Saved results to: {filename}")
    
    except Exception as e:
        print(f"\n🔥 CRITICAL ERROR: {type(e).__name__}: {str(e)[:150]}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            browser.close()
            print("\n✓ Browser closed successfully")
        except:
            pass
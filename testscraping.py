from bs4 import BeautifulSoup
import requests
import pandas as pd
import datetime
import time
from urllib.parse import urljoin

# Define headers for requests
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

def extract_article_links_from_search(search_url):
    """Extract all article URLs from the search results page"""
    try:
        print(f"Fetching search page: {search_url}")
        response = requests.get(search_url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        urls = []
        
        # Find all article cards
        cards = soup.find_all('div', class_="c-card")
        print(f"Found {len(cards)} article cards")
        
        for card in cards:
            a_tag = card.find('a')
            if a_tag and 'href' in a_tag.attrs:
                url = a_tag['href']
                # Make sure URL is absolute (not relative)
                if not url.startswith('http'):
                    url = urljoin(search_url, url)
                urls.append(url)
                print(f"  Found article: {url}")
        
        return urls
        
    except Exception as e:
        print(f"Error extracting article links: {e}")
        return []

def scrape_article(url):
    """Scrape an individual article page"""
    try:
        print(f"Scraping article: {url}")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        raw_article = {}
        
        # Extract headline
        headline_elem = soup.find('h1', class_="page-title")
        if headline_elem:
            raw_article['headline'] = headline_elem.get_text(strip=True)
        else:
            raw_article['headline'] = "No headline found"
        
        # Extract article body
        article_content = soup.find('div', class_="l-page-section--content")
        if article_content:
            # Get all paragraph text
            paragraphs = article_content.find_all('p')
            article_text = ' '.join([p.get_text(strip=True) for p in paragraphs])
            raw_article['article_body'] = article_text
        else:
            raw_article['article_body'] = "No content found"
        
        # Extract date (adjust selector based on actual page structure)
        date_elem = soup.find('time') or soup.find('span', class_="date")
        if date_elem:
            date_text = date_elem.get_text(strip=True)
            # Try to parse date - you might need to adjust format
            try:
                # Common formats to try
                for fmt in ["%B %d, %Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]:
                    try:
                        parsed_date = datetime.datetime.strptime(date_text, fmt)
                        raw_article['date'] = parsed_date.strftime("%Y-%m-%d")
                        break
                    except ValueError:
                        continue
                else:
                    raw_article['date'] = date_text
            except:
                raw_article['date'] = date_text
        else:
            raw_article['date'] = "No date found"
        
        # Add URL for reference
        raw_article['url'] = url
        
        # Add timestamp of scraping
        raw_article['scraped_at'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"  Successfully scraped: {raw_article['headline'][:50]}...")
        return raw_article
        
    except Exception as e:
        print(f"Error scraping article {url}: {e}")
        return None

def main():
    """Main function to run the scraper"""
    # Start with the search URL
    search_url = "https://www.fas.usda.gov/newsroom/search?news%5B0%5D=news_type%3A10106"
    
    print("=" * 50)
    print("Starting FAS USDA News Scraper")
    print("=" * 50)
    
    # Step 1: Extract article URLs from search page
    article_urls = extract_article_links_from_search(search_url)
    
    if not article_urls:
        print("No articles found! Exiting.")
        return
    
    print(f"\nFound {len(article_urls)} articles to scrape")
    
    # Step 2: Scrape each article
    all_articles = []
    
    for i, url in enumerate(article_urls, 1):
        print(f"\n[{i}/{len(article_urls)}] ", end="")
        article_data = scrape_article(url)
        
        if article_data:
            all_articles.append(article_data)
        
        # Add a small delay to be polite to the server
        time.sleep(1)
    
    # Step 3: Save to DataFrame and CSV
    if all_articles:
        df = pd.DataFrame(all_articles)
        
        # Reorder columns for better readability
        column_order = ['headline', 'date', 'article_body', 'url', 'scraped_at']
        df = df[column_order]
        
        # Save to CSV with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"fas_usda_news_{timestamp}.csv"
        df.to_csv(filename, index=False, encoding='utf-8')
        
        print(f"\n" + "=" * 50)
        print(f"Successfully scraped {len(all_articles)} articles")
        print(f"Saved to: {filename}")
        print(f"Columns: {', '.join(df.columns)}")
        print("\nFirst few rows:")
        print(df[['headline', 'date']].head())
        
        return df
    else:
        print("No articles were successfully scraped.")
        return None

if __name__ == "__main__":
    # Run the scraper
    result_df = main()
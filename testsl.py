from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import pandas as pd
import re
from datetime import datetime
from collections import defaultdict

def setup_driver():
    """Setup Selenium driver"""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    return webdriver.Chrome(options=options)

def extract_articles_from_page(soup):
    """Extract all article cards from the current page"""
    articles = []
    
    # Find all article cards - looking for c-card elements
    article_cards = soup.find_all('div', class_='c-card')
    
    for card in article_cards:
        try:
            article_data = extract_article_data(card)
            if article_data:
                articles.append(article_data)
        except Exception as e:
            print(f"Error extracting article: {e}")
            continue
    
    return articles

def extract_article_data(card):
    """Extract structured data from a single article card"""
    
    # Extract title and link
    title_tag = card.find('h3', class_='c-card__title')
    title = title_tag.text.strip() if title_tag else "No title"
    
    link_tag = card.find('a', class_='c-card__url')
    url = link_tag['href'] if link_tag and 'href' in link_tag.attrs else ""
    if url and not url.startswith('http'):
        url = 'https://www.fas.usda.gov' + url
    
    # Extract date
    date_tag = card.find('time')
    date_str = date_tag.text.strip() if date_tag else "No date"
    
    # Extract announcement type (from tags)
    tags_div = card.find('div', class_='c-card__tags')
    announcement_type = ""
    if tags_div:
        type_tag = tags_div.find('span')
        announcement_type = type_tag.text.strip() if type_tag else "Export Sales Announcement"
    
    # Extract content
    content_div = card.find('div', class_='c-card__content')
    content = content_div.text.strip() if content_div else ""
    
    # Parse the content for structured data
    structured_data = parse_article_content(content)
    
    # Combine all data
    article_data = {
        'headline': title,
        'date': date_str,
        'announcement_type': announcement_type,
        'url': url,
        'content': content,
        **structured_data
    }
    
    return article_data

def parse_article_content(content):
    """Parse the article content to extract structured information"""
    result = {
        'commodities': [],
        'destinations': [],
        'volumes': [],
        'total_volume_mt': 0,
        'marketing_year': '',
        'delivery_info': ''
    }
    
    # Extract marketing year
    my_match = re.search(r'MY\s+(\d{4}/\d{4})|marketing\s+year\s+(\d{4}/\d{4})', content, re.IGNORECASE)
    if my_match:
        result['marketing_year'] = my_match.group(1) or my_match.group(2)
    
    # Extract volumes in metric tons
    volume_patterns = [
        r'(\d{1,3}(?:,\d{3})*)\s*MT\s+of',  # 264,000 MT of
        r'(\d{1,3}(?:,\d{3})*)\s*metric\s+tons\s+of',  # metric tons of
        r'(\d{1,3}(?:,\d{3})*)\s*MT',  # just MT
    ]
    
    all_volumes = []
    for pattern in volume_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        for match in matches:
            volume = int(match.replace(',', ''))
            all_volumes.append(volume)
    
    result['volumes'] = all_volumes
    result['total_volume_mt'] = sum(all_volumes)
    
    # Extract commodities
    commodity_keywords = {
        'soybeans': ['soybeans', 'soybean'],
        'corn': ['corn'],
        'wheat': ['wheat'],
        'sorghum': ['sorghum'],
        'soybean meal': ['soybean meal', 'soybean cake and meal'],
        'soybean oil': ['soybean oil'],
        'coarse grains': ['coarse grains']
    }
    
    found_commodities = []
    for commodity, keywords in commodity_keywords.items():
        for keyword in keywords:
            if re.search(rf'\b{re.escape(keyword)}\b', content, re.IGNORECASE):
                found_commodities.append(commodity)
                break
    
    result['commodities'] = list(set(found_commodities))
    
    # Extract destinations
    destination_keywords = {
        'China': ['China'],
        'Japan': ['Japan'],
        'Mexico': ['Mexico'],
        'South Korea': ['South Korea'],
        'Philippines': ['Philippines'],
        'Colombia': ['Colombia'],
        'Unknown': ['unknown destinations', 'unknown'],
        'Egypt': ['Egypt'],
        'Iraq': ['Iraq'],
        'Morocco': ['Morocco'],
        'India': ['India'],
        'Pakistan': ['Pakistan']
    }
    
    found_destinations = []
    for destination, keywords in destination_keywords.items():
        for keyword in keywords:
            if re.search(rf'\b{re.escape(keyword)}\b', content, re.IGNORECASE):
                found_destinations.append(destination)
                break
    
    result['destinations'] = list(set(found_destinations))
    
    # Check if it's a correction
    if 'CORRECTION:' in content or 'correction' in content.lower():
        result['is_correction'] = True
    else:
        result['is_correction'] = False
    
    return result

def scrape_multiple_pages(driver, base_url, max_pages=5):
    """Scrape multiple pages of articles"""
    all_articles = []
    
    for page_num in range(max_pages):
        print(f"\nScraping page {page_num + 1}...")
        
        if page_num == 0:
            url = base_url
        else:
            url = f"{base_url}&page={page_num}"
        
        try:
            driver.get(url)
            time.sleep(3)
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            articles = extract_articles_from_page(soup)
            
            if not articles:
                print(f"No articles found on page {page_num + 1}")
                break
            
            all_articles.extend(articles)
            print(f"Found {len(articles)} articles on page {page_num + 1}")
            
            # Check if there's a next page
            next_button = soup.find('a', class_='c-pager__link--next')
            if not next_button and page_num > 0:
                print("No more pages available")
                break
            
            time.sleep(2)  # Be nice to the server
            
        except Exception as e:
            print(f"Error scraping page {page_num + 1}: {e}")
            break
    
    return all_articles

def save_to_csv(articles, filename_prefix="usda_export_sales"):
    """Save extracted articles to CSV files"""
    if not articles:
        print("No articles to save")
        return
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Create main DataFrame
    main_data = []
    for article in articles:
        main_data.append({
            'Headline': article.get('headline', ''),
            'Date': article.get('date', ''),
            'Announcement Type': article.get('announcement_type', ''),
            'Is Correction': article.get('is_correction', False),
            'Marketing Year': article.get('marketing_year', ''),
            'Commodities': ', '.join(article.get('commodities', [])),
            'Destinations': ', '.join(article.get('destinations', [])),
            'Volumes (MT)': ', '.join([str(v) for v in article.get('volumes', [])]),
            'Total Volume (MT)': article.get('total_volume_mt', 0),
            'URL': article.get('url', ''),
            'Content Preview': article.get('content', '')[:200] + '...' if len(article.get('content', '')) > 200 else article.get('content', '')
        })
    
    df_main = pd.DataFrame(main_data)
    
    # Create summary statistics
    summary_data = calculate_summary_statistics(articles)
    
    # Save to CSV files
    main_filename = f"{filename_prefix}_{timestamp}.csv"
    summary_filename = f"{filename_prefix}_summary_{timestamp}.csv"
    
    df_main.to_csv(main_filename, index=False, encoding='utf-8')
    pd.DataFrame([summary_data]).to_csv(summary_filename, index=False, encoding='utf-8')
    
    print(f"\n{'='*60}")
    print(f"SAVED TO CSV FILES:")
    print(f"1. {main_filename} - {len(articles)} articles")
    print(f"2. {summary_filename} - Summary statistics")
    print("="*60)
    
    return df_main, summary_data

def calculate_summary_statistics(articles):
    """Calculate summary statistics from articles"""
    summary = defaultdict(int)
    commodity_counts = defaultdict(int)
    destination_counts = defaultdict(int)
    
    total_volume = 0
    total_articles = len(articles)
    
    for article in articles:
        # Count commodities
        for commodity in article.get('commodities', []):
            commodity_counts[commodity] += 1
        
        # Count destinations
        for destination in article.get('destinations', []):
            destination_counts[destination] += 1
        
        # Sum volumes
        total_volume += article.get('total_volume_mt', 0)
        
        # Count corrections
        if article.get('is_correction', False):
            summary['corrections_count'] += 1
    
    # Get top commodities and destinations
    top_commodities = sorted(commodity_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_destinations = sorted(destination_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Prepare summary dict
    summary.update({
        'total_articles': total_articles,
        'total_volume_mt': total_volume,
        'avg_volume_per_article': total_volume / total_articles if total_articles > 0 else 0,
        'top_commodity_1': f"{top_commodities[0][0]} ({top_commodities[0][1]})" if top_commodities else "None",
        'top_commodity_2': f"{top_commodities[1][0]} ({top_commodities[1][1]})" if len(top_commodities) > 1 else "None",
        'top_destination_1': f"{top_destinations[0][0]} ({top_destinations[0][1]})" if top_destinations else "None",
        'top_destination_2': f"{top_destinations[1][0]} ({top_destinations[1][1]})" if len(top_destinations) > 1 else "None",
        'scrape_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    
    return summary

def display_summary(articles, summary_data):
    """Display a summary of the extracted data"""
    print(f"\n{'='*60}")
    print("EXTRACTION SUMMARY")
    print("="*60)
    print(f"Total Articles Extracted: {summary_data['total_articles']}")
    print(f"Total Volume Reported: {summary_data['total_volume_mt']:,} MT")
    print(f"Average Volume per Article: {summary_data['avg_volume_per_article']:,.0f} MT")
    print(f"Correction Notices: {summary_data.get('corrections_count', 0)}")
    
    # Display sample articles
    print(f"\n{'='*60}")
    print("SAMPLE ARTICLES (First 5):")
    print("="*60)
    
    for i, article in enumerate(articles[:5]):
        print(f"\n{i+1}. {article['headline']}")
        print(f"   Date: {article['date']}")
        print(f"   Commodities: {', '.join(article['commodities'])}")
        print(f"   Destinations: {', '.join(article['destinations'])}")
        print(f"   Volume: {article['total_volume_mt']:,} MT")
        if article['volumes']:
            print(f"   Individual Shipments: {', '.join([f'{v:,} MT' for v in article['volumes']])}")
        print(f"   Marketing Year: {article['marketing_year']}")

def main():
    """Main function to run the scraper"""
    print("USDA Foreign Agricultural Service - Export Sales Scraper")
    print("="*60)
    
    # Setup driver
    driver = setup_driver()
    
    try:
        # URL to scrape (Export Sales Announcements)
        base_url = "https://www.fas.usda.gov/newsroom/search?news%5B0%5D=news_type%3A10106"
        
        print("\nStarting scraping process...")
        print(f"Base URL: {base_url}")
        
        # Scrape multiple pages
        articles = scrape_multiple_pages(driver, base_url, max_pages=3)  # Adjust max_pages as needed
        
        if articles:
            # Display summary
            summary_data = calculate_summary_statistics(articles)
            display_summary(articles, summary_data)
            
            # Save to CSV
            df_main, summary = save_to_csv(articles)
            
            # Show additional statistics
            print(f"\n{'='*60}")
            print("ADDITIONAL STATISTICS:")
            print("="*60)
            
            # Commodity distribution
            print("\nCommodity Distribution:")
            commodity_counts = defaultdict(int)
            for article in articles:
                for commodity in article.get('commodities', []):
                    commodity_counts[commodity] += 1
            
            for commodity, count in sorted(commodity_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"  {commodity}: {count} articles")
            
            # Destination distribution
            print("\nDestination Distribution:")
            dest_counts = defaultdict(int)
            for article in articles:
                for dest in article.get('destinations', []):
                    dest_counts[dest] += 1
            
            for dest, count in sorted(dest_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"  {dest}: {count} articles")
            
            # Date range
            dates = [article.get('date', '') for article in articles if article.get('date')]
            if dates:
                print(f"\nDate Range: {min(dates)} to {max(dates)}")
            
        else:
            print("\nNo articles were found. The page structure might have changed.")
        
    except Exception as e:
        print(f"\nError during scraping: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up
        driver.quit()
        print(f"\n{'='*60}")
        print("Scraping complete. Browser closed.")
        print("="*60)

if __name__ == "__main__":
    main()
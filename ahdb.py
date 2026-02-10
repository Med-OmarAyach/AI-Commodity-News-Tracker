from bs4 import BeautifulSoup
import requests
import pandas as pd
from datetime import datetime
import time
import re

from playwright.sync_api import sync_playwright
def clean_ahdb_report_text(text):
    """
    Specialized cleaning for AHDB agriculture reports.
    """
    if not text:
        return ""
    
    # First pass: basic cleaning
    text = re.sub(r'\n\s*\n+', '\n\n', text)  # Keep paragraph breaks
    text = re.sub(r'[ \t]+', ' ', text)  # Collapse multiple spaces
    
    # Remove non-breaking spaces
    text = text.replace('\xa0', ' ')
    
    # Fix common patterns in AHDB reports
    patterns_to_fix = [
        # Fix price patterns
        (r'£\s*([0-9,]+(?:\.[0-9]{2})?)', r'£\1'),  # £ 168.50 → £168.50
        (r'€\s*([0-9,]+(?:\.[0-9]{2})?)', r'€\1'),  # € 193.00 → €193.00
        (r'\$\s*([0-9,]+(?:\.[0-9]{2})?)', r'$\1'),  # $ 200.60 → $200.60
        
        # Fix date patterns
        (r'([A-Za-z]{3})\s*-\s*([0-9]{2})', r'\1-\2'),  # Feb -26 → Feb-26
        
        # Fix percentage patterns
        (r'([0-9]+)\s*%', r'\1%'),  # 32 % → 32%
        
        # Fix table column separators
        (r'\s*\|\s*', ' | '),
        
        # Fix plus/minus signs
        (r'([+-])\s*([£€$\d])', r'\1\2'),  # + £1.05 → +£1.05
    ]
    
    for pattern, replacement in patterns_to_fix:
        text = re.sub(pattern, replacement, text)
    
    # Remove excessive section headers (multiple "Grains" etc.)
    lines = text.split('\n')
    cleaned_lines = []
    last_line = ""
    
    for line in lines:
        line_stripped = line.strip()
        if line_stripped:
            # Skip duplicate consecutive section headers
            if (line_stripped.lower() in ['grains', 'rapeseed', 'extra information'] and 
                line_stripped.lower() == last_line.lower()):
                continue
            cleaned_lines.append(line_stripped)
            last_line = line_stripped
    
    # Reconstruct with proper paragraph spacing
    return '\n\n'.join(cleaned_lines)
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
    l=s.split(sep=' ')
    year=l[3]
    m=month[l[2]]
    if int(l[1])<10:
        day='0'+l[1]
    else:
        day=l[1]
    date=year+"-"+m+"-"+day
    format_str = "%Y-%m-%d"
    datetime_object = datetime.strptime(date, format_str).date()
    return datetime_object
    

BASE_URL = "https://ahdb.org.uk/news"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(BASE_URL)
    page.wait_for_timeout(3000)

    # Get article links
    html = page.content()
    soup = BeautifulSoup(html, "html.parser")

    article_links = []
    for div in soup.find_all(class_="list-item-title"):
        if "Arable Market Report" in div.find(class_='restrict-title').get_text():
            href = div.find("a").get("href")
            if href and "/news/" in href:
                article_links.append("https://ahdb.org.uk" + href)

    article_links = list(set(article_links))
    print(f"Found {len(article_links)} articles")
    print(article_links)
    data=[]
    # Visit each article
    for url in article_links[:5]:  # limit for test
        page.goto(url)
        page.wait_for_timeout(2000)
        article_html = page.content()
        soup = BeautifulSoup(article_html, "html.parser")
        row={}
        title = soup.find("h1")
        date_str=soup.find(class_="news-date").get_text()
        row["title"]=title.text.strip() if title else "N/A"
        row["date"]=parse_date(date_str.strip())
        row["URL"]=url
        body=""
        article=soup.find("div",class_="orchard-layouts-root")
        article_over=False
        i=0
        while not article_over:
            div=article.find_all("div",class_="row")[i]
            body+=div.get_text()
            i+=1
            if "Northern Ireland" in div.get_text().strip():
                article_over=True
        pos1=body.find("Grains")
        pos2=body.find("Rapeseed")
        pos3=body.find("Extra information")
        pos4=body.find("Northern Ireland")
        data.append(row | {"Commodity":"Grains","Body":clean_ahdb_report_text(body[pos1:pos2])})
        data.append(row | {"Commodity":"Rapeseed","Body":clean_ahdb_report_text(body[pos2:pos3])})
        data.append(row | {"Commodity":"Extra information","Body":clean_ahdb_report_text(body[pos3:pos4])})
            
        print("URL:", url)
        print("-" * 40)

    browser.close()
# Save to CSV with timestamp
df=pd.DataFrame(data)
filename = f"ahdb_0.csv"
df.to_csv(filename, index=False, encoding='utf-8')


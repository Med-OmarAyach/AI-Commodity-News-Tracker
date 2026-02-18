import pandas as pd
import io
import requests
from datetime import datetime, timedelta
import re

# ===== CONFIGURATION =====
start_date = "01/01/1971"          # Start date (MM/DD/YYYY)
end_date = datetime.today().strftime("%m/%d/%Y")  # End date (today)
CHUNK_YEARS = 5                    # Safe chunk size (5 years ≈ 1,825 days)

date_chunks = []
current_start = datetime.strptime(start_date, "%m/%d/%Y")
end_dt = datetime.strptime(end_date, "%m/%d/%Y")

while current_start <= end_dt:
    chunk_end = min(datetime(current_start.year + CHUNK_YEARS, 12, 31), end_dt)
    date_chunks.append((
        current_start.strftime("%m/%d/%Y"),
        chunk_end.strftime("%m/%d/%Y")
    ))
    current_start = chunk_end + timedelta(days=1)

dfs = []
for chunk_start, chunk_end in date_chunks:
    url = f"https://www.federalreserve.gov/datadownload/Output.aspx?rel=H10&series=60f32914ab61dfab590e0e470153e3ae&lastobs=&from={chunk_start}&to={chunk_end}&filetype=csv&label=include&layout=seriesrow"
    print(f"Downloading {chunk_start} to {chunk_end}...")
    df_chunk = pd.read_csv(io.StringIO(requests.get(url).text), header=0)
    dfs.append(df_chunk)

df = dfs[0].copy()
for df_chunk in dfs[1:]:
    date_cols = [col for col in df_chunk.columns if re.match(r'\d{4}-\d{2}-\d{2}', col)]
    cols_to_keep = [df_chunk.columns[0]] + date_cols
    df_chunk_trimmed = df_chunk[cols_to_keep]
    
    df = pd.merge(df, df_chunk_trimmed, on=df.columns[0], how='outer')

date_columns = [col for col in df.columns if re.match(r'\d{4}-\d{2}-\d{2}', col)] 
mask_usd = df['Currency:'] == 'USD'

for date_column in date_columns:
    df.loc[mask_usd, date_column] = 1 / df.loc[mask_usd, date_column]

df.loc[mask_usd, 'Unit:'], df.loc[mask_usd, 'Currency:'] = df.loc[mask_usd, 'Currency:'], df.loc[mask_usd, 'Unit:']

id_vars = ['Descriptions:', 'Unit:', 'Multiplier:', 'Currency:', 'Unique Identifier:', 'Series Name:']
df_melted = pd.melt(df, id_vars=id_vars, var_name='Date', value_name='Value')

df_melted['Date'] = pd.to_datetime(df_melted['Date']).dt.strftime('%Y-%m-%d')  

df_melted['Currency:'] = df_melted['Currency:'].str.replace('Currency:_Per_', '', regex=False)
df_melted['Unit:'] = df_melted['Unit:'].str.replace('Currency:_Per_', '', regex=False)
df_melted['Multiplier']=1

html_url = "https://www.federalreserve.gov/datadownload/Choose.aspx?rel=H10"
html = requests.get(html_url).text
pub_date_match = re.search(r'last released\s+(?:[A-Za-z]+,\s+)?([A-Za-z]+\s+\d{1,2},\s+\d{4})', html)
pub_date_str = pub_date_match.group(1) if pub_date_match else datetime.today().strftime("%B %d, %Y")
publication_date = datetime.strptime(pub_date_str, "%B %d, %Y").strftime("%Y-%m-%d")
df_melted['Publication date'] = publication_date

df_melted.to_csv('frb_h10_daily_extracted.csv', index=False)


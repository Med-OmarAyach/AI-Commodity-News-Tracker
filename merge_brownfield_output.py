#!/usr/bin/env python3
"""
Merge fragment CSVs into one unified CSV with all articles + full bodies
"""
import pandas as pd
from pathlib import Path
import glob

OUTPUT_DIR = Path('brownfield_output')
FRAGMENTS_DIR = OUTPUT_DIR / 'csv_fragments'
UNIFIED_CSV = OUTPUT_DIR / 'brownfield_complete_with_bodies.csv'

print(f"📁 Merging fragments from: {FRAGMENTS_DIR.absolute()}")
print(f"💾 Output: {UNIFIED_CSV.absolute()}\n")

# Find all fragment CSVs
fragment_files = sorted(glob.glob(str(FRAGMENTS_DIR / 'fragment_worker_*.csv')))

if not fragment_files:
    print("❌ No fragment files found!")
    print("👉 Run workers first:")
    print("   python brownfield_worker.py --start-page 1 --end-page 155 --worker-id 1")
    print("   python brownfield_worker.py --start-page 156 --end-page 310 --worker-id 2")
    print("   ...etc")
    exit(1)

print(f"Found {len(fragment_files)} fragment files:")
for f in fragment_files:
    print(f"  • {Path(f).name}")

# Load and concatenate all fragments
dfs = []
for file in fragment_files:
    try:
        df = pd.read_csv(file, encoding='utf-8-sig')
        dfs.append(df)
        print(f"✅ Loaded {len(df):,} articles from {Path(file).name}")
    except Exception as e:
        print(f"❌ Error loading {file}: {e}")

if not dfs:
    print("❌ No valid fragments to merge")
    exit(1)

# Concatenate and sort by date/scraped time
unified_df = pd.concat(dfs, ignore_index=True)
unified_df = unified_df.sort_values(['date', 'scraped_at'], ascending=[False, False]).reset_index(drop=True)

# Ensure consistent column order
columns = [
    'article_id', 'date', 'title', 'author', 'categories', 'tags',
    'url', 'scraped_at', 'source', 'body_char_count', 'body'
]
unified_df = unified_df[[col for col in columns if col in unified_df.columns]]

# Save unified CSV
unified_df.to_csv(UNIFIED_CSV, index=False, encoding='utf-8-sig')

print(f"\n{'='*70}")
print("✅ MERGE COMPLETE")
print(f"{'='*70}")
print(f"Total articles: {len(unified_df):,}")
print(f"Total characters in all bodies: {unified_df['body_char_count'].sum():,}")
print(f"Output file: {UNIFIED_CSV.name}")
print(f"\nSample columns:")
print(unified_df[['article_id', 'date', 'title', 'body_char_count']].head(5).to_string(index=False))
print(f"\n💡 Usage:")
print(f'   df = pd.read_csv("{UNIFIED_CSV.name}", encoding="utf-8-sig")')
print(f'   print(df["body"].iloc[0][:200])  # First 200 chars of first article body')
print(f"{'='*70}")
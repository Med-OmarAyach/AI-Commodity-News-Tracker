from bs4 import BeautifulSoup
import requests
import pandas as pd
import zipfile
import io
import os
import pandasdmx as sdmx
import xml.etree.ElementTree as ET

url="https://www.federalreserve.gov/datadownload/Choose.aspx?rel=H10"
response = requests.get(url)
soup = BeautifulSoup(response.content, 'html.parser')
link=soup.find(id="AllData").get('href')
link="https://www.federalreserve.gov/datadownload/"+link
response = requests.get(link)
z = zipfile.ZipFile(io.BytesIO(response.content))

print("ZIP :")
for name in z.namelist():
    print(" -", name)

output_dir="h10_data"
os.makedirs(output_dir, exist_ok=True)
z.extractall(output_dir)

print(f"Extracted to folder: {output_dir}")

xml_file=None
for f in os.listdir(output_dir):
    if f.lower().endswith(".xml"):
        xml_file = os.path.join(output_dir, f)
        break

if not xml_file:
    raise FileNotFoundError("No XML file found in ZIP.")
###
tree = ET.parse(xml_file)
root = tree.getroot()

ns = {
    "frb": "http://www.federalreserve.gov/structure/compact/common",
    "kf": "http://www.federalreserve.gov/structure/compact/H10_H10",
}

rows = []

for series in root.findall(".//kf:Series", ns):
    series_attrs = series.attrib

    for obs in series.findall("frb:Obs", ns):
        row = {
            **series_attrs,
            "TIME_PERIOD": obs.attrib.get("TIME_PERIOD"),
            "OBS_VALUE": obs.attrib.get("OBS_VALUE"),
            "OBS_STATUS": obs.attrib.get("OBS_STATUS"),
        }
        rows.append(row)

df=pd.DataFrame(rows)
#msg = sdmx.read_sdmx(xml_file)
#df = msg.to_pandas()
###
csv_path = os.path.join(output_dir, "h10_data.csv")
df.to_csv(csv_path, index=False)

print("\nSaved CSV to:", csv_path)
print("\nPreview:")
print(df.head())
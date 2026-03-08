import os
import requests
import pandas as pd
from bs4 import BeautifulSoup

def scrape_to_csv(id, user, pw, is_lecturer=False):
    session = requests.Session()
    session.auth = (user, pw)
    type_char = 'N' if is_lecturer else 'G'
    url = f"https://planzajec.uek.krakow.pl/index.php?typ={type_char}&id={id}&okres=2"
    
    response = session.get(url)
    response.encoding = 'utf-8' 
    soup = BeautifulSoup(response.text, 'html.parser')
    
    data = []
    rows = soup.find_all('tr')
    for row in rows[1:]:
        cols = row.find_all('td')
        if len(cols) >= 5:
            # Basic parsing logic
            res = {
                "Date": cols[0].text.strip(),
                "Time": cols[1].text.strip().split('(')[0].strip(),
                "Subject": cols[2].text.strip(),
                "Type": cols[3].text.strip(),
                "Location": cols[5].text.strip() if not is_lecturer and len(cols) >= 6 else cols[4].text.strip()
            }
            data.append(res)
    
    if data:
        df = pd.DataFrame(data)
        # utf-8-sig is the "magic" encoding that makes Excel open Polish letters correctly
        df.to_csv("live_schedule.csv", index=False, encoding='utf-8-sig')
        print("Schedule updated successfully.")

if __name__ == "__main__":
    # Get secrets from GitHub environment
    LOGIN = os.getenv("UEK_LOGIN")
    PASSWORD = os.getenv("UEK_PASSWORD")
    MY_ID = "252671" # <--- Put your UEK ID here
    
    scrape_to_csv(MY_ID, LOGIN, PASSWORD)
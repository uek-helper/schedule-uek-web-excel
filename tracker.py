import os
import json
import requests
import pandas as pd
from bs4 import BeautifulSoup

def scrape_data(id, username, password, is_lecturer=False):
    session = requests.Session()
    session.auth = (username, password)
    type_char = 'N' if is_lecturer else 'G'
    url = f"https://planzajec.uek.krakow.pl/index.php?typ={type_char}&id={id}&okres=2"
    
    response = session.get(url)
    if response.status_code == 401:
        return None
    
    response.encoding = 'utf-8' 
    soup = BeautifulSoup(response.text, 'html.parser')
    
    excel_data = []
    table_rows = soup.find_all('tr')
    
    for row in table_rows[1:]:
        columns = row.find_all('td')
        
        if len(columns) >= 5: 
            date_str = columns[0].text.strip()
            if not date_str: continue 
            
            # --- NEW LOGIC: CHECK FOR MOVED CLASS NOTES ---
            # Search for text like "Zajęcia przeniesione na godz. 18:30"
            raw_time_cell = columns[1].text.strip()
            moved_note = columns[2].find('font', color='#008000') # Green text in Subject cell
            
            start = ""
            end = ""
            day_of_week = ""

            # Check if there is a 'moved to' note in the subject area
            if moved_note and "godz." in moved_note.text:
                import re
                time_match = re.search(r'(\d{1,2}:\d{2})', moved_note.text)
                if time_match:
                start = time_match.group(1)

            # If no 'moved' time was found, use the standard column time
            if not start:
                clean_time = raw_time_cell.split('(')[0].strip() 
                if " " in clean_time:
                    day_of_week, time_range = clean_time.split(' ', 1)
                else:
                    time_range = clean_time
                    
                if "-" in time_range:
                    start, end = time_range.split('-', 1)
                else:
                    start = time_range

            # Determine Location and Teacher/Group
            teacher = ""
            group = ""
            location = ""
            
            if not is_lecturer and len(columns) >= 6:
                teacher = columns[4].text.strip()
                location = columns[5].text.strip()
            elif is_lecturer and len(columns) >= 6:
                location = columns[4].text.strip()
                group = columns[5].text.strip()
            elif is_lecturer and len(columns) == 5:
                location = columns[4].text.strip()

            entry = {
                "Date": date_str,
                "Day": day_of_week,
                "Starting": start.strip(),
                "Ending": end.strip(),
                "Subject": columns[2].text.strip().split('\n')[0], # Clean subject from notes
                "Type": columns[3].text.strip(),
                "Location": location
            }
            
            if is_lecturer:
                entry["Group"] = group
            else:
                entry["Teacher"] = teacher
                
            excel_data.append(entry)
            
    return excel_data

if __name__ == "__main__":
    # Get credentials from GitHub Secrets
    LOGIN = os.getenv("UEK_LOGIN")
    PASSWORD = os.getenv("UEK_PASSWORD")
    
    # Configuration
    TARGET_ID = "252671"  # Change this to your student ID
    IS_LECTURER = False   # Set to True if you are tracking a lecturer's plan
    
    new_schedule = scrape_data(TARGET_ID, LOGIN, PASSWORD, IS_LECTURER)
    
    if new_schedule:
        # 1. Save CSV for Live Excel Link (UTF-8-SIG for Polish characters)
        df = pd.DataFrame(new_schedule)
        df.to_csv("live_schedule.csv", index=False, encoding='utf-8-sig')
        
        # 2. Change Detection (Optional - Pings you if schedule updates)
        cache_file = "last_known_state.json"
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                old_schedule = json.load(f)
                if old_schedule != new_schedule:
                    print("Schedule changed! (Insert Telegram/Discord alert here if desired)")
        
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(new_schedule, f, ensure_ascii=False, indent=4)
        
        print("Live CSV updated.")

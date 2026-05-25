import os
import json
import requests
import pandas as pd
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
from datetime import datetime, timedelta
import pytz

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

def save_as_icalendar(excel_data, filename="university_schedule.ics"):
    # Create the calendar container
    cal = Calendar()
    cal.add('prodid', '-//UEK Schedule Helper//EN')
    cal.add('version', '2.0')
    
    # Set the timezone for Krakow
    local_tz = pytz.timezone('Europe/Warsaw')
    
    for entry in excel_data:
        try:
            # Parse the date and time strings from your scraped data
            # Expected date format: "2026-03-19"
            date_str = entry["Date"]
            start_time = entry["Starting"]
            end_time = entry["Ending"]
            
            # Combine date and time strings into datetime objects
            start_dt = datetime.strptime(f"{date_str} {start_time}", "%Y-%m-%d %H:%M")
            end_dt = datetime.strptime(f"{date_str} {end_time}", "%Y-%m-%d %H:%M")
            
            # Localize to Poland's timezone so daylight savings doesn't shift your classes
            start_dt = local_tz.localize(start_dt)
            end_dt = local_tz.localize(end_dt)
            
            # Create a calendar event
            event = Event()
            
            # Title format: "Information Systems (ćwiczenia)"
            event.add('summary', f"{entry['Subject']} ({entry['Type']})")
            event.add('dtstart', start_dt)
            event.add('dtend', end_dt)
            event.add('location', entry['Location'])
            
            # Add the teacher's name to the description field
            if "Teacher" in entry:
                event.add('description', f"Teacher: {entry['Teacher']}")
            elif "Group" in entry:
                event.add('description', f"Group: {entry['Group']}")
                
            # Generate a unique ID for the event using the date and start time
            uid = f"{date_str}_{start_time.replace(':', '')}@uek_helper"
            event.add('uid', uid)
            
            # Append the event to the calendar
            cal.add_component(event)
            
        except Exception as e:
            print(f"Skipping event due to error: {e}")
            continue

    # Write the calendar data to a file
    with open(filename, 'wb') as f:
        f.write(cal.to_ical())
        
    print(f"Successfully saved calendar to {filename}")

if __name__ == "__main__":
    # Get credentials from GitHub Secrets
    LOGIN = os.getenv("UEK_LOGIN")
    PASSWORD = os.getenv("UEK_PASSWORD")
    # Configuration
    TARGET_ID = "252681"  # Change this to your student ID
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
                    print("Schedule changed!")
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(new_schedule, f, ensure_ascii=False, indent=4)
        print("Live CSV updated.")
        save_as_icalendar(new_schedule)
    

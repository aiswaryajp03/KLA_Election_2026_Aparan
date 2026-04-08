from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import pandas as pd
import time
import re

options = Options()
options.add_argument("--disable-extensions")
driver = webdriver.Chrome(options=options)

driver.get("https://opendatakerala.org/KLA2026/")
time.sleep(6)

# Dismiss disclaimer modal
driver.execute_script("let btn = document.getElementById('disc-dismiss'); if(btn) btn.click();")
time.sleep(2)

# Labels that are UI badges, not actual candidate data — skip these
SKIP_LABELS = {"Affidavit (PDF)", "Sitting MLA"}

all_rows = []

for i in range(140):
    try:
        # Click constituency card
        cards = driver.find_elements(By.CSS_SELECTOR, "div[role='button']")
        driver.execute_script("arguments[0].click()", cards[i])
        time.sleep(3)

        # Get header info
        try:
            header = driver.find_element(By.CSS_SELECTOR, ".modal-header")
            header_text = header.text.strip().split("\n")
            # Format: "Close \n District · Constituency #N \n Name"
            district_line = header_text[1] if len(header_text) > 1 else ""
            const_name    = header_text[2] if len(header_text) > 2 else ""
            district      = district_line.split("·")[0].strip() if "·" in district_line else ""
            const_no      = re.search(r"#(\d+)", district_line)
            const_no      = const_no.group(1) if const_no else str(i + 1)
        except:
            district, const_name, const_no = "", "", str(i + 1)

        # Get polling booths and voters
        try:
            modal_text = driver.find_element(By.CSS_SELECTOR, ".modal").text
            booths = re.search(r"POLLING BOOTHS\s*\n(\S+)", modal_text)
            voters = re.search(r"VOTERS\s*\n([\d,]+)", modal_text)
            female = re.search(r"♀\s*([\d,]+)", modal_text)
            male   = re.search(r"♂\s*([\d,]+)", modal_text)
            booths = booths.group(1) if booths else ""
            voters = voters.group(1) if voters else ""
            female = female.group(1) if female else ""
            male   = male.group(1) if male else ""
        except:
            booths = voters = female = male = ""

        # ── BUG FIX 1: track seen candidates to avoid DOM duplicates ──────────
        seen_in_constituency = set()

        # Get all candidates
        candidate_divs = driver.find_elements(By.CSS_SELECTOR, ".candidate-details")
        for div in candidate_divs:

            # ── BUG FIX 2: strip UI badge labels ("Sitting MLA", etc.) ────────
            lines = [
                l.strip()
                for l in div.text.strip().split("\n")
                if l.strip() and l.strip() not in SKIP_LABELS
            ]

            if len(lines) >= 3:
                alliance  = lines[0]
                cand_name = lines[1]
                party     = lines[2]
            elif len(lines) == 2:
                alliance  = lines[0]
                cand_name = lines[1]
                party     = ""
            else:
                continue

            # Skip if this (alliance, name, party) combo was already captured
            key = (alliance, cand_name, party)
            if key in seen_in_constituency:
                continue
            seen_in_constituency.add(key)

            all_rows.append({
                "constituency_no": const_no,
                "constituency":    const_name,
                "district":        district,
                "polling_booths":  booths,
                "total_voters":    voters,
                "female_voters":   female,
                "male_voters":     male,
                "alliance":        alliance,
                "candidate_name":  cand_name,
                "party":           party,
            })

        unique_count = len(seen_in_constituency)
        print(f"[{i+1}/140] ✅ {const_name} — {unique_count} candidates")

        # Close modal with Escape
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        time.sleep(1)

    except Exception as e:
        print(f"[{i+1}/140] ❌ Error: {e}")
        try:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            time.sleep(1)
        except:
            pass

driver.quit()

df = pd.DataFrame(all_rows)
print(f"\n✅ Total candidates scraped: {len(df)}")
print(f"✅ Constituencies covered: {df['constituency_no'].nunique()}")
print(df.head(10).to_string())

df.to_csv("kla2026_all_candidates.csv", index=False, encoding="utf-8-sig")
print("\n✅ Saved to kla2026_all_candidates.csv")
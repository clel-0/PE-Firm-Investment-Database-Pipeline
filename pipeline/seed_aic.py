from playwright.sync_api import sync_playwright
from pathlib import Path
from datetime import datetime
import json
import pandas as pd

# used to create unique jsonl filename for data logging
date_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

OUTPUT_DIR = Path(f"logs/aic_responses_{date_time}.jsonl")
OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)




"""Handles HTTP responses to filter and log specific JSON data from AIC member pages, and saves it in a structured JSONL format."""
def response_handler(r):
    # Only process XHR and fetch requests
    if r.request.resource_type != "xhr" or r.request.resource_type !="fetch":
        return

    #only process json responses
    try:
        data = r.json()
    except Exception:
        return
    
    #check for specific structure in the json data to match AIC member data
    if isinstance(data,dict):
        if "Items" in data:
            if "$values" in data["Items"]:
               if "Website" in data["Items"]["$values"][0]:

                    # Prepare jsonl formatted string for logging, and append to file
                    responseData = {"datetime": date_time, 
                                   "url" : r.url, 
                                   "status" : r.status, 
                                   "headers" : dict(r.headers), 
                                   "JSON" : data
                    }
                    jString = json.dumps(responseData, ensure_ascii=False, separators=(",", ":")) + "\n"
                    print("Logging AIC member data from: " + r.url)
                    with open(OUTPUT_DIR, "a", encoding="utf-8") as f:
                        f.write(jString)
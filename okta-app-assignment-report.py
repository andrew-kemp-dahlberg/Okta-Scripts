#!/usr/bin/env python3
import csv
from pathlib import Path
import requests
import json
import time
import collections
import os
from dotenv import load_dotenv


load_dotenv()

OKTA_ORG_URL = os.getenv('OKTA_ORG_URL')
OKTA_API_KEY = os.getenv('OKTA_API_KEY')

if not OKTA_ORG_URL or not OKTA_API_KEY:
    raise ValueError("Missing required environment variables. Please check your .env file.")

csv_location = os.path.expanduser("~/Documents/Applications_report.csv")
valid_user_types = ["Full Time", "Contractor", "Intern", "Contractor-1099"]

def get_paginated_data(url):
    items = []
    headers = {
        'Accept': 'application/json',
        'Authorization': f'SSWS {OKTA_API_KEY}',
    }
    while url:
        print(f"Fetching: {url}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        rate_limit_remaining = int(response.headers.get('x-rate-limit-remaining', 1))
        if rate_limit_remaining <= 1:
            current_time = int(time.time())
            reset_time = int(response.headers.get('x-rate-limit-reset', current_time + 60))
            sleep_duration = reset_time - current_time + 1
            sleep_duration = max(sleep_duration, 0)
            print(f"Rate limit approaching. Sleeping {sleep_duration} seconds")
            time.sleep(sleep_duration)

        items.extend(json.loads(response.text))

        link_header = response.headers.get('link', '')
        next_url = None
        for link in link_header.split(','):
            if 'rel="next"' in link:
                next_url = link.split(';')[0].strip(' <>')
        url = next_url
    
    return items

users = get_paginated_data(f"{OKTA_ORG_URL}/api/v1/users?limit=200&search=status eq \"ACTIVE\"")

apps = get_paginated_data(f"{OKTA_ORG_URL}/api/v1/apps?filter=status eq \"ACTIVE\"")

apps_dict = {app["id"]: app["label"] for app in apps}
apps_dict = collections.OrderedDict(
    sorted(apps_dict.items(), key=lambda item: item[1])
)

user_records = {}

for user in users:
    profile = user.get("profile", {})
    user_type = profile.get("userType", "N/A")
    
    if user_type not in valid_user_types:
        continue
    
    user_record = {
        "First Name": profile.get("firstName", "N/A"),
        "Last Name": profile.get("lastName", "N/A"),
        "Email": profile.get("email", "N/A"),
        "User Type": user_type,
        "Title": profile.get("title", "N/A"),
        "Department": profile.get("department", "N/A"),
        "Manager": profile.get("manager", "N/A"),
        "Organization": profile.get("organization", "N/A")
    }
    
    for app_name in apps_dict.values():
        user_record[app_name] = ""
    
    user_records[user["id"]] = user_record

for app_id, app_name in apps_dict.items():
    app_users = get_paginated_data(f"{OKTA_ORG_URL}/api/v1/apps/{app_id}/users")
    
    for app_user in app_users:
        user_id = app_user.get("id")
        if user_id not in user_records:
            continue       
        user_records[user_id][app_name] = "assigned"

with open(csv_location, 'w', newline='') as csvfile:
    fieldnames = list(next(iter(user_records.values())).keys())
    
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    for record in user_records.values():
        writer.writerow(record)
print(f"Report generated at {csv_location}")
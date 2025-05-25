####### Requires further testing to confirm

#!/usr/bin/env python3
import csv
from pathlib import Path
import requests
import json
import time
import collections
import os
from dotenv import load_dotenv



def okta_api(endpoint):
    items = []
    headers = {
        'Accept': 'application/json',
        'Authorization': f'SSWS {OKTA_API_KEY}',
    }
    url  = OKTA_ORG_URL+endpoint
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

def delete_users():
    profile = "profile"
    department = "department"
    id = "id"
    login = "login"



    users = okta_api("/api/v1/users?limit=200")
    for user in users :
        user_profile = user[profile]
        dept = user_profile.get(department, "N/A")
        if dept != "IT" :
            print(user[profile][login])
            
            headers = {
                'Accept': 'application/json',
                'Authorization': f'SSWS {OKTA_API_KEY}',
            }
            payload = {}
            url = f"{OKTA_ORG_URL}/api/v1/users/{user[id]}?sendEmail=false"
            print(url)
            response = requests.request("DELETE", url, headers=headers, data=payload)
            print(response.text)
            response = requests.request("DELETE", url, headers=headers, data=payload)


if __name__ == "__main__":
    load_dotenv()
    
    OKTA_ORG_URL = os.getenv('OKTA_ORG_URL')
    OKTA_API_KEY = os.getenv('OKTA_API_KEY')
    
    if not OKTA_ORG_URL or not OKTA_API_KEY:
        raise ValueError("Missing required environment variables. Please check your .env file.")
    delete_users()

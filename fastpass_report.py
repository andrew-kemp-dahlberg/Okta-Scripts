#!/usr/bin/env python3
import csv
from pathlib import Path
import requests
import json
import time
import collections
import sys
import os
from dotenv import load_dotenv


def get_paginated_data(url, token):
    """Fetches paginated data from Okta API with rate limit handling."""
    items = []
    headers = {'Accept': 'application/json', 'Authorization': f'SSWS {token}'}
    while url:
        print(f"Fetching: {url}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        rate_limit_remaining = int(response.headers.get('x-rate-limit-remaining', 1))
        if rate_limit_remaining <= 1:
            reset_time = int(response.headers.get('x-rate-limit-reset', time.time() + 60))
            sleep_duration = max(reset_time - time.time() + 1, 0)
            print(f"Rate limit approaching. Sleeping {sleep_duration} seconds")
            time.sleep(sleep_duration)

        items.extend(response.json())

        link_header = response.headers.get('link', '')
        next_url = None
        for link in link_header.split(','):
            if 'rel="next"' in link:
                next_url = link.split(';')[0].strip(' <>')
        url = next_url
    return items

def get_user_report(url, token) :
    users = get_paginated_data(f"{url}/api/v1/users", token)
    return_list = []
    for user in users:
        print(user)
        if user.get("profile", {}).get("userType", "") in ["Full Time", "Contractor - 1099", "Contractor", "Intern"]:
            profile= {}
            profile["login"] = user["profile"]["login"]
            profile["user type"] = user["profile"]["userType"]
            factors = get_paginated_data(f"{url}/api/v1/users/{user["id"]}/factors", token)

            fastpass = {}
            fastpass["desktop"] = []
            fastpass["mobile"] = []

            for factor in factors : 
                if factor["factorType"] == "signed_nonce" :
                    if factor["profile"]["platform"] in ["WINDOWS", "MACOS"] :
                        print("\n\ndesktop\n")
                        print(factor["profile"]["platform"])
                        print(factor)
                        fastpass["desktop"].append(factor["profile"]["name"])
                    if factor["profile"]["platform"] in ["IOS", "ANDROID"]:
                        print("\n\nmobile\n")
                        print(factor["profile"]["platform"])
                        print(factor)
                        fastpass["mobile"].append(factor["profile"]["name"])

            profile["mobile enrollments"] = ", ".join(fastpass["mobile"])
            profile["desktop enrollments"] = ", ".join(fastpass["desktop"])

            return_list.append(profile)
    return return_list

def write_csv(data, output_path):
    """Write list of dictionaries to CSV file."""
    if not data:
        print("No data to export!")
        return

    # Create directory if it doesn't exist
    output_dir = os.path.dirname(output_path)
    os.makedirs(output_dir, exist_ok=True)

    fieldnames = list(data[0].keys())
    
    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for record in data:
                writer.writerow(record)
        print(f"Successfully exported to {output_path}")
    except PermissionError:
        print(f"Error: No permission to write to {output_path}")
        raise
    except Exception as e:
        print(f"Error writing CSV: {str(e)}")
        raise



def main():
    """Main function to execute the script."""
    # Load environment variables from .env file
    load_dotenv()

    # Get environment variables
    OKTA_ORG_URL = os.getenv('OKTA_ORG_URL')
    OKTA_API_KEY = os.getenv('OKTA_API_KEY')

    # Validate environment variables
    if not OKTA_ORG_URL or not OKTA_API_KEY:
        print("Error: OKTA_ORG_URL and OKTA_API_KEY must be set as environment variables.")
        raise ValueError("Missing required environment variables. Please check your .env file.")
        sys.exit(1)
    
    created_file_name = input("Created file name: ")
    report = get_user_report(OKTA_ORG_URL, OKTA_API_KEY)

    # Get the user's Documents directory
    documents_dir = os.path.expanduser("~/Documents")
    output_path = os.path.join(documents_dir, f"{created_file_name}.csv")
    write_csv(report, output_path)
    

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
import requests
import csv
import json
import os
import time
from copy import deepcopy

OKTA_DOMAIN = ""  
DEFAULT_OUTPUT_DIR = os.path.expanduser("~/Documents")
token = ""

def get_users(import_file):
    """Read CSV file and return list of dictionaries."""
    with open(import_file, 'r', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def export_to_csv(data, output_path):
    """Write list of dictionaries to CSV file."""
    if not data:
        print("No data to export!")
        return

    # Get fieldnames from the first record
    fieldnames = list(data[0].keys())
    
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for record in data:
            writer.writerow(record)
    print(f"Successfully exported to {output_path}")

def get_all_okta_users(token):
    """Fetch all Okta users with pagination and rate limiting."""
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': f'SSWS {token}'
    }
    
    users = []
    url = f"{OKTA_DOMAIN}/api/v1/users?limit=200"
    
    while url:
        print(f"Fetching: {url}")
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Handle rate limiting
            rate_limit_remaining = int(response.headers.get('x-rate-limit-remaining', 1))
            if rate_limit_remaining <= 1:
                reset_time = int(response.headers.get('x-rate-limit-reset', 60))
                print(f"Rate limit approaching. Sleeping {reset_time} seconds")
                time.sleep(reset_time)
            
            users.extend(response.json())
            
            # Check for next page
            link_header = response.headers.get('link', '')
            url = None
            for link in link_header.split(','):
                if 'rel="next"' in link:
                    url = link.split(';')[0].strip(' <>')
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching users: {e}")
            break
            
    return users

def get_okta_info(user_list, all_okta_users):
    """Match local users with Okta users by email."""
    email_map = {user['profile']['email'].lower(): user for user in all_okta_users if 'email' in user['profile']}
    
    enriched_users = []
    for user in user_list:
        email = user.get('Email', '').lower()
        okta_user = email_map.get(email)
        
        if okta_user:
            enriched = process_okta_user(okta_user, user, "Email")
        else:
            enriched = {
                **user,
                'Department': 'N/A',
                'Okta Status': 'Not found',
                'Match Type': 'No match found',
                'Okta Email': 'N/A'
            }
        
        enriched_users.append(enriched)
    return enriched_users

def search_by_name(user_list, all_okta_users):
    """Search for unmatched users by first/last name in local data."""
    name_map = {}
    for okta_user in all_okta_users:
        profile = okta_user.get('profile', {})
        key = (profile.get('firstName', '').lower(), 
               profile.get('lastName', '').lower())
        if key[0] and key[1]:
            name_map.setdefault(key, []).append(okta_user)
    
    results = []
    for user in user_list:
        if user['Match Type'] != 'No match found':
            results.append(user)
            continue

        first = user.get('First', '').lower()
        last = user.get('Last', '').lower()
        matches = name_map.get((first, last), [])
        
        if len(matches) == 1:
            processed = process_okta_user(matches[0], user, "First and Last")
            results.append(processed)
        elif len(matches) > 1:
            for match in matches:
                processed = process_okta_user(match, deepcopy(user), "Multiple Matches")
                results.append(processed)
        else:
            results.append(user)
    return results

def process_okta_user(okta_user, local_user, match_type):
    """Process Okta user data and update local user record."""
    profile = okta_user.get('profile', {})
    return {
        **local_user,
        'Department': profile.get('department', 'N/A'),
        'Okta Status': okta_user.get('status', 'Unknown'),
        'Match Type': match_type,
        'Okta Email': profile.get('email', 'N/A')
    }

def main():
    """Main execution flow."""
    try:
        print("Fetching all Okta users...")
        all_okta_users = get_all_okta_users(token)
        if not all_okta_users:
            print("Failed to fetch Okta users")
            return
    except Exception as e:
        print(f"Error fetching Okta users: {e}")
        return
    
    input_path = input("Drag input file here: ").strip().replace('\\ ', ' ')
    input_path = os.path.abspath(input_path)
    
    if not os.path.exists(input_path):
        print("Error: Input file does not exist!")
        return

    output_name = input("Output file name (without extension): ").strip()
    output_path = os.path.join(DEFAULT_OUTPUT_DIR, f"{output_name}.csv")

    try:
        users = get_users(input_path)
        email_matched = get_okta_info(users, all_okta_users)
        final_results = search_by_name(email_matched, all_okta_users)
        export_to_csv(final_results, output_path)
    except Exception as e:
        print(f"Error occurred: {str(e)}")

if __name__ == "__main__":
    main()

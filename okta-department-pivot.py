#!/usr/bin/env python3
import requests
import csv
import json
import os
import time
import sys
from pathlib import Path
from dotenv import load_dotenv

def get_users(import_file):
    """Reads a CSV file and returns a list of dictionaries."""
    with open(import_file, mode='r', encoding='utf-8-sig') as file:
        return list(csv.DictReader(file))

def pivot(user_list):
    """Creates a pivot table based on the user list."""
    pivot_data = {}
    for user in user_list:
        department = user["Department"].lower()  # Normalize department name to lowercase
        if department not in pivot_data:
            pivot_data[department] = {
                "Department": department,
                "Total Count": 0,
                "Active Count": 0,
                "Inactive Count": 0,
            }
        dept_data = pivot_data[department]
        dept_data["Total Count"] += 1
        if user["Okta Status"] == "ACTIVE":
            dept_data["Active Count"] += 1
        else:
            dept_data["Inactive Count"] += 1
    return pivot_data

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

def okta_group_count(group_id, org_url, token):
    """Fetches the user count for a specific Okta group."""
    url = f"{org_url}/api/v1/groups/{group_id}/users"
    return len(get_paginated_data(url, token))

def okta_group_search(pivot_data, org_url, token, prefix):
    """Searches for Okta groups and updates the pivot data with user counts."""
    return_list = []
    for department in pivot_data.values():
        department_name = department["Department"]
        try:
            groups = get_paginated_data(f"{org_url}/api/v1/groups?q={department_name}", token)
            for group in groups:
                group_name = group.get("profile", {}).get("name", "")
                if group_name.lower().startswith(prefix.lower()):
                    department["Okta Count"] = okta_group_count(group["id"], org_url, token)
                    break
            else:
                department["Okta Count"] = "N/A"
        except requests.exceptions.HTTPError:
            department["Okta Count"] = "N/A"
        return_list.append(department)
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

    # Get input from user
    input_file = input("Drag input file here (Columns email and department required): ")
    input_file = os.path.abspath(input_file.replace(r'\ ', ' ').replace(r'\,', ',').strip())
    created_file_name = input("Created file name: ")
    prefix = input("Enter the department prefix (e.g., 'dept.' or 'dept-'): ")

    # Get the user's Documents directory
    documents_dir = os.path.expanduser("~/Documents")
    
    # Create output path
    output_path = os.path.join(documents_dir, f"{created_file_name}_pivot.csv")

    try:
        # Process the data
        user_list = get_users(input_file)
        pivot_data = pivot(user_list)
        pivot_data = okta_group_search(pivot_data, OKTA_ORG_URL, OKTA_API_KEY, prefix)
        write_csv(pivot_data, output_path)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
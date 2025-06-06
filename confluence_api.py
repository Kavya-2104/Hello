import os
import re
import requests
import spacy
from dotenv import load_dotenv

load_dotenv()

EMAIL = os.getenv("CONFLUENCE_EMAIL")
TOKEN = os.getenv("CONFLUENCE_TOKEN")
BASE_URL = os.getenv("CONFLUENCE_BASE_URL")

nlp = spacy.load("en_core_web_sm")

def get_all_spaces():
    spaces = []
    start = 0
    limit = 25
    while True:
        url = f"{BASE_URL}/rest/api/space?limit={limit}&start={start}"
        res = requests.get(url, auth=(EMAIL, TOKEN))
        data = res.json()
        for s in data.get("results", []):
            spaces.append({"key": s["key"], "name": s["name"]})
        if "_links" in data and "next" in data["_links"]:
            start += limit
        else:
            break
    return spaces

def get_pages_in_space(space_key):
    pages = []
    start = 0
    limit = 25
    while True:
        url = f"{BASE_URL}/rest/api/content?spaceKey={space_key}&limit={limit}&start={start}&expand=ancestors"
        res = requests.get(url, auth=(EMAIL, TOKEN))
        data = res.json()
        for page in data.get("results", []):
            pages.append({
                "id": page["id"],
                "title": page["title"],
                "parent_id": page["ancestors"][-1]["id"] if page["ancestors"] else None
            })
        if "_links" in data and "next" in data["_links"]:
            start += limit
        else:
            break
    return pages

def extract_update_from_commit(commit_message):
    parts = commit_message.split("] - ", 1)
    description = parts[1] if len(parts) > 1 else commit_message
    doc = nlp(description.lower())

    if " to " in description.lower():
        before_to, after_to = description.lower().split(" to ", 1)

        # Remove common verbs/auxiliary words to get field
        field = before_to
        for remove_word in ["updated", "changed", "is", "content"]:
            field = field.replace(remove_word, "")
        field = field.strip()
        if not field:
            field = "Content"  # fallback if empty

        # Title case for consistency
        field = " ".join([w.capitalize() for w in field.split()])
        value = after_to.strip()
        return field, value

    return None, None

def update_page(page_id, commit_message, title):
    url = f"{BASE_URL}/rest/api/content/{page_id}?expand=body.storage,version"
    res = requests.get(url, auth=(EMAIL, TOKEN))
    data = res.json()

    current_content = data["body"]["storage"]["value"]
    version = data["version"]["number"]

    field, new_value = extract_update_from_commit(commit_message)
    if not field or not new_value:
        print("❌ Could not extract update field or value from commit message.")
        return

    # If field is "Content" replace the entire <body> content inside page (assuming it's HTML)
    if field.lower() == "content":
        # Replace entire body content between <body> tags if present or just replace whole content
        # Simplified approach: replace entire content with new_value wrapped in <p>
        updated_content = f"<p>{new_value}</p>"
    else:
        pattern = re.compile(rf"({re.escape(field)}:\s*)(.+)", re.IGNORECASE)
        if not pattern.search(current_content):
            print(f"⚠️ Field '{field}' not found in page content. Adding new line at end.")
            updated_content = current_content + f"\n<p>{field}: {new_value}</p>"
        else:
            updated_content = pattern.sub(rf"\1{new_value}", current_content)

    payload = {
        "id": str(page_id),
        "type": "page",
        "title": title,
        "body": {
            "storage": {
                "value": updated_content,
                "representation": "storage"
            }
        },
        "version": {
            "number": version + 1
        }
    }

    res = requests.put(url, json=payload, auth=(EMAIL, TOKEN))
    if res.status_code == 200:
        print(f"🔄 Successfully updated page {page_id} with {field}: {new_value}")
    else:
        print(f"❌ Failed to update page {page_id}: {res.status_code} - {res.text}")

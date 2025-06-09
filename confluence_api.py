import os
import re
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from utils import normalize, log

load_dotenv()

EMAIL = os.getenv("CONFLUENCE_EMAIL")
TOKEN = os.getenv("CONFLUENCE_TOKEN")
BASE_URL = os.getenv("CONFLUENCE_BASE_URL")


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
def normalize_text(text):
    # Lowercase and remove spaces, colons, dashes, and "is"
    text = text.lower()
    text = re.sub(r'[:\-\s]+', '', text)  # remove colons, dashes, spaces
    text = text.replace("is", "")
    text = text.strip()
    # Remove any leading/trailing non-alphanumeric chars (like hyphens or colons)
    text = re.sub(r'^[^a-z0-9]+|[^a-z0-9]+$', '', text)
    return text

def update_field_in_body(existing_body, field_name, new_value):
    soup = BeautifulSoup(existing_body, "html.parser")
    paragraphs = soup.find_all("p")
    target_norm = normalize_text(field_name)
    field_found = False

    for i, p in enumerate(paragraphs):
        label_text = p.get_text(separator=" ", strip=True)
        label_norm = normalize_text(label_text.split(':')[0])  # consider only part before colon

        if label_norm == target_norm:
            # Check if value is in same <p> after colon
            parts = label_text.split(':', 1)
            if len(parts) == 2 and parts[1].strip():
                # Value exists in same paragraph, update it
                new_text = f"{parts[0]}: {new_value}"
                p.string = new_text
                log(f"🔄 Updated existing field inline: {field_name} → {new_value}")
            elif i + 1 < len(paragraphs):
                # Value in next <p>, update next paragraph
                paragraphs[i + 1].string = str(new_value)
                log(f"🔄 Updated existing field next line: {field_name} → {new_value}")
            else:
                # No place to update value, append new <p>
                new_value_tag = soup.new_tag("p")
                new_value_tag.string = str(new_value)
                p.insert_after(new_value_tag)
                log(f"➕ Appended new value after label: {field_name} → {new_value}")
            field_found = True
            break

    if not field_found:
        # Append at end if not found
        log(f"➕ Appending new field: {field_name} → {new_value}")
        new_label = soup.new_tag("p")
        new_label.string = f"{field_name}:"
        new_value_tag = soup.new_tag("p")
        new_value_tag.string = str(new_value)
        soup.append(new_label)
        soup.append(new_value_tag)

    return str(soup)

def update_field_in_body(existing_body, field_name, new_value):
    soup = BeautifulSoup(existing_body, "html.parser")
    target_norm = normalize_text(field_name)
    field_found = False

    # Handle <br /> based fields in single <p> tag
    for p in soup.find_all("p"):
        if not p.text.strip():
            continue  # skip empty <p> tags
        # Replace <br> with newline for easier parsing
        content = p.decode_contents().replace("<br/>", "\n").replace("<br />", "\n")
        lines = content.split("\n")
        new_lines = []
        modified = False

        for line in lines:
            if ':' in line:
                key_part, val_part = line.split(':', 1)
                key_norm = normalize_text(key_part)
                if key_norm == target_norm:
                    new_lines.append(f"{key_part.strip()}: {new_value}")
                    field_found = True
                    modified = True
                else:
                    new_lines.append(line.strip())
            else:
                new_lines.append(line.strip())

        if modified:
            p.clear()
            # Rebuild <p> with <br /> tags
            for idx, line in enumerate(new_lines):
                if idx > 0:
                    p.append(soup.new_tag("br"))
                p.append(line)
            log(f"🔄 Updated inline in <br/>: {field_name} → {new_value}")
            break

    # Handle fields in separate <p> tags
    if not field_found:
        paragraphs = soup.find_all("p")
        for i, p in enumerate(paragraphs):
            label_text = p.get_text(separator=" ", strip=True)
            label_norm = normalize_text(label_text.split(':')[0])

            if label_norm == target_norm:
                if ':' in label_text:
                    new_text = f"{label_text.split(':')[0]}: {new_value}"
                    p.string = new_text.strip()
                    log(f"🔄 Updated existing inline field: {field_name} → {new_value}")
                elif i + 1 < len(paragraphs):
                    paragraphs[i + 1].string = str(new_value).strip()
                    log(f"🔄 Updated value in next <p>: {field_name} → {new_value}")
                field_found = True
                break

    # Append if not found
    if not field_found:
        log(f"➕ Appending new field: {field_name} → {new_value}")
        new_p = soup.new_tag("p")
        new_p.string = f"{field_name}: {new_value}"
        soup.append(new_p)

    # Cleanup: remove empty <p> tags
    for tag in soup.find_all("p"):
        if not tag.get_text(strip=True):
            tag.decompose()

    return str(soup)


def update_page(page_id, commit_message):
    url = f"{BASE_URL}/rest/api/content/{page_id}?expand=body.storage,version,title"
    res = requests.get(url, auth=(EMAIL, TOKEN))
    data = res.json()

    html_content = data["body"]["storage"]["value"]
    version = data["version"]["number"]
    title = data["title"]

    updates = extract_updates(commit_message)
    if not updates:
        log("❌ No updates found in commit message.")
        return

    updated_html = html_content
    for field, new_value in updates.items():
        updated_html = update_field_in_body(updated_html, field, new_value)

    if updated_html != html_content:
        payload = {
            "id": page_id,
            "type": "page",
            "title": title,
            "version": {"number": version + 1},
            "body": {
                "storage": {
                    "value": updated_html,
                    "representation": "storage"
                }
            }
        }
        update_url = f"{BASE_URL}/rest/api/content/{page_id}"
        update_res = requests.put(update_url, json=payload, auth=(EMAIL, TOKEN))
        if update_res.status_code == 200:
            log(f"✅ Page '{title}' updated successfully (version {version + 1}).")
        else:
            log(f"❌ Failed to update page '{title}'. Status: {update_res.status_code}")
    else:
        log("ℹ️ No changes to update.")


def extract_updates(commit_message):
    pattern = r"([\w\s\-]+?)\s+(?:is updated to|is changed to|is|was|changed to|updated to|set to)\s+([^\s,;]+)"
    matches = re.findall(pattern, commit_message, re.IGNORECASE)
    cleaned = {}
    for key, val in matches:
        clean_key = key.strip().lstrip("-").strip().title()
        cleaned[clean_key] = val.strip()
    print(matches)
    print(cleaned)
    return cleaned


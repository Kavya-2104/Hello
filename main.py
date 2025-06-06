# main.py
from commit_parser import parse_commit_message
from confluence_api import get_all_spaces, get_pages_in_space, update_page

def match_space_and_page(commit_message, spaces):
    project, module, component = parse_commit_message(commit_message)
    if not all([project, module, component]):
        return None, None, None, None

    for space in spaces:
        if project in space["name"].lower() or project in space["key"].lower():
            pages = get_pages_in_space(space["key"])
            for page in pages:
                title = page["title"].lower()

                # Relaxed match: if either module or component in title
                if module in title or component in title:
                    return space["key"], page["id"], module, component

                # Parent-child match
                parent = next((p for p in pages if p["id"] == page.get("parent_id")), None)
                if parent:
                    parent_title = parent["title"].lower()
                    if (module in title and component in parent_title) or (component in title and module in parent_title):
                        return space["key"], page["id"], module, component
    return None, None, module, component

if __name__ == "__main__":
    commit_message = "[kavyasri][admin][homepage - adm] - content is updated to Hello Hi wonderful and Welcome to the Admin section of the Employee Leave Management System. Here you can manage roles, leave policies, and oversee system configurations."

    spaces = get_all_spaces()
    space_key, page_id, module, component = match_space_and_page(commit_message, spaces)

    print(f"📦 Parsed -> Module: {module}, Component: {component}")

    if space_key and page_id:
        print(f"✅ Found space: {space_key}, page ID: {page_id}")
        update_page(page_id, commit_message, f"{component.capitalize()} Details")
    else:
        print(f"❌ Could not resolve space or page for module: {module} and component: {component}")

from confluence_api import get_all_spaces, get_pages_in_space, update_page
from commit_parser import parse_commit_message
from utils import normalize, log

def match_space_and_page(commit_message, spaces):
    project, module, component = parse_commit_message(commit_message)
    if not all([project, module, component]):
        log("Could not parse commit message into project/module/component", level="error")
        return None, None, None, None

    project_norm = normalize(project)
    module_norm = normalize(module)
    component_norm = normalize(component)

    fallback_candidates = []

    for space in spaces:
        space_name_norm = normalize(space["name"])
        space_key_norm = normalize(space["key"])

        if project_norm in space_name_norm or project_norm in space_key_norm:
            pages = get_pages_in_space(space["key"])
            page_by_id = {p["id"]: p for p in pages}
            candidates = []

            for page in pages:
                title_norm = normalize(page["title"])
                if component_norm == title_norm:
                    candidates.append((3, page))
                elif component_norm in title_norm:
                    candidates.append((2, page))
                elif module_norm in title_norm:
                    candidates.append((1, page))

            fallback_candidates.extend([(score, page, space["key"]) for score, page in candidates])

            if not candidates:
                continue

            candidates.sort(key=lambda x: x[0], reverse=True)

            for score, page in candidates:
                parent_id = page.get("parent_id")
                if parent_id and parent_id in page_by_id:
                    parent_page = page_by_id[parent_id]
                    parent_title_norm = normalize(parent_page["title"])
                    if module_norm in parent_title_norm or component_norm in parent_title_norm:
                        return space["key"], page["id"], module, component

            return space["key"], candidates[0][1]["id"], module, component

    if fallback_candidates:
        fallback_candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, best_page, best_space = fallback_candidates[0]
        return best_space, best_page["id"], module, component

    return None, None, module, component

if __name__ == "__main__":
    commit_message = "[kavyasri sureddy][admin][Homepage - Emp]  content is changed to nono"

    spaces = get_all_spaces()
    space_key, page_id, module, component = match_space_and_page(commit_message, spaces)

    log(f"📦 Parsed -> Module: {module}, Component: {component}")

    if space_key and page_id:
        log(f"✅ Found space: {space_key}, page ID: {page_id}")
        update_page(page_id, commit_message)
    else:
        log(f"❌ Could not resolve space or page for module: {module} and component: {component}", level="error")


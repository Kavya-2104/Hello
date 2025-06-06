import re

def parse_commit_message(message):
    # Fix pattern to accept spaces inside brackets and optional trailing bracket fix
    pattern = r"\[(.*?)\]"
    matches = re.findall(pattern, message)
    if len(matches) < 3:
        return None, None, None
    # Return first three parts, lowercased and stripped
    return [matches[0].strip().lower(), matches[1].strip().lower(), matches[2].strip().lower()]

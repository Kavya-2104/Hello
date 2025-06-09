import re
import logging

logging.basicConfig(level=logging.INFO)

def normalize(text):
    return re.sub(r"[\s\-_]", "", text.lower().strip())

def log(message, level="info"):
    if level == "info":
        logging.info(message)
    elif level == "error":
        logging.error(message)
    elif level == "warning":
        logging.warning(message)
    else:
        logging.debug(message)
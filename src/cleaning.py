import re


def clean_page_text(text: str):
    clean_text = re.sub("\u200b|\n\u200b", " ", text)
    return clean_text
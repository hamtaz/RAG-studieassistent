import pdfplumber as pd
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from src.cleaning import clean_page_text

import hashlib

def get_file_hash(file_path: Path) -> str:
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    return hashlib.sha256(file_bytes).hexdigest()[:12] 

@dataclass
class SourceDocument:
    source_name: str
    source_type: str
    raw_text: str
    document_hash: str
    page_number: Optional[int] = None


def pdf_to_txt(file_path: str):
    output = []
    with pd.open(file_path) as pdf:
        for index, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                output.append(dict(page_number=index + 1, text=clean_page_text(text)))
        return output


def load_pdf_document(file_path: str):
    documents = []
    hash = get_file_hash(file_path)
    for page in pdf_to_txt(file_path):
        document = SourceDocument(
            source_name=file_path.name,
            source_type="pdf",
            page_number=page["page_number"],
            raw_text=page["text"],
            document_hash = hash
        )
        documents.append(document)
    return documents
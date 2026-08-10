import pdfplumber as pd
from pathlib import Path
from dataclasses import dataclass
import re
from typing import Optional
current_dir = Path(__file__).parent
file_path = current_dir / "data" / "cs-concepts.pdf"

@dataclass
class SourceDocument:
    source_name: str
    source_type: str
    raw_text: str
    page_number: Optional[int] = None

@dataclass
class Chunk:
    id: int
    chunk_text: str
    source_name: str
    wordcount: int
    page_number: Optional[int] = None



def clean_page_text(text: str):
    clean_text = re.sub("\u200b|\n\u200b", " ", text)
    return clean_text

def pdf_to_txt(file_path: str):
    output = []
    with pd.open(file_path) as pdf:

        for index, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                output.append(dict(page_number=index+1, text=clean_page_text(text)))
        return output

def load_pdf_document(file_path: str):
    documents = []
    for page in pdf_to_txt(file_path):
        document = SourceDocument(source_name = file_path.name , source_type = "pdf", page_number = page["page_number"], raw_text = page["text"])
        documents.append(document)
    return documents

def split_sentence(text: str):
    sentences = re.split(r'[\?!.] (?=[A-Z])', text)
    return sentences

def chunk_text(text: str, source_name: str, page_number: int, min_word: int, max_word: int, overlap_sentences: int):
    sentences = split_sentence(text) 
    current_sentences = []
    current_word_count = 0
    id = 0
    chunk_sentences = []
    for sentence in sentences:
        if current_word_count+len(sentence.split()) >= max_word and current_word_count+len(sentence.split()) >= min_word:
            joined_sentences = " ".join(current_sentences)
            chunk = Chunk(id=id, chunk_text = joined_sentences, source_name = source_name, wordcount = current_word_count, page_number = page_number)
            id += 1
            chunk_sentences.append(chunk)
            current_sentences = current_sentences[-overlap_sentences:]
            current_word_count = sum([len(curr_sentence.split()) for curr_sentence in current_sentences])

        current_sentences.append(sentence)   
        current_word_count = current_word_count + len(sentence.split())

    joined_sentences= " ".join(current_sentences)
    chunk = Chunk(id=id, chunk_text = joined_sentences, source_name = source_name, wordcount = current_word_count, page_number = page_number)
    chunk_sentences.append(chunk)
    return chunk_sentences
   



    print("Hello")
    
document = load_pdf_document(file_path)
#print(split_sentence("Dette er setning én. Er dette setning to? Ja! Absolutt."))
#print(document[0])

# Enkel test
all_chunks = []

for doc in document:
    chunks = chunk_text(doc.raw_text, doc.source_name, doc.page_number, 200, 350, 2)
    all_chunks.extend(chunks)



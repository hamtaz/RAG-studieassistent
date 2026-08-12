import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class Chunk:
    id: int
    chunk_text: str
    source_name: str
    wordcount: int
    page_number: Optional[int] = None


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
        if current_word_count + len(sentence.split()) >= max_word and current_word_count + len(sentence.split()) >= min_word:
            joined_sentences = " ".join(current_sentences)
            chunk = Chunk(id=id, chunk_text=joined_sentences, source_name=source_name, wordcount=current_word_count, page_number=page_number)
            id += 1
            chunk_sentences.append(chunk)
            current_sentences = current_sentences[-overlap_sentences:]
            current_word_count = sum([len(curr_sentence.split()) for curr_sentence in current_sentences])

        current_sentences.append(sentence)
        current_word_count = current_word_count + len(sentence.split())

    joined_sentences = " ".join(current_sentences)
    chunk = Chunk(id=id, chunk_text=joined_sentences, source_name=source_name, wordcount=current_word_count, page_number=page_number)
    chunk_sentences.append(chunk)
    return chunk_sentences
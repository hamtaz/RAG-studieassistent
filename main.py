# main.py
from pathlib import Path

from src.extraction import load_pdf_document
from src.chunking import chunk_text

current_dir = Path(__file__).parent
file_path = current_dir / "data" / "cs-concepts.pdf"


def main():
    documents = load_pdf_document(file_path)

    all_chunks = []
    for doc in documents:
        chunks = chunk_text(
            doc.raw_text,
            doc.source_name,
            doc.page_number,
            doc.document_hash,
            min_word=300,
            max_word=500,
            overlap_sentences=2,
        )
        all_chunks.extend(chunks)

    print(f"Document count (pages): {len(documents)}")
    print(f"Chunks count: {len(all_chunks)}")
    print(all_chunks[0])

    return all_chunks


if __name__ == "__main__":
    main()
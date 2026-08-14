# main.py
from pathlib import Path

from src.extraction import load_pdf_document
from src.chunking import chunk_document
from src.embeddings import embed_and_store
from src.cosmos_client import get_container

current_dir = Path(__file__).parent
file_path = current_dir / "data" / "cs-concepts.pdf"


def main():
    documents = load_pdf_document(file_path)
    if not documents:
        print(f"No extractable text in {file_path.name}.")
        return []

    # Chunk across the whole document rather than page by page, so sentences
    # spanning a page break stay whole and only one undersized tail can occur.
    all_chunks = chunk_document(
        [(doc.page_number, doc.raw_text) for doc in documents],
        source_name=documents[0].source_name,
        document_hash=documents[0].document_hash,
        min_word=200,
        max_word=350,
        overlap_sentences=2,
    )

    container = get_container()
    embed_and_store(all_chunks, container)

    print(f"Document count (pages): {len(documents)}")
    print(f"Chunks count: {len(all_chunks)}")
    print(all_chunks[0])

    return all_chunks


if __name__ == "__main__":
    main()

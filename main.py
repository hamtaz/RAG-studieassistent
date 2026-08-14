# main.py
import logging
import sys
from pathlib import Path

from src.chunking import Chunk, chunk_document
from src.cosmos_client import get_container
from src.embeddings import embed_and_store
from src.extraction import load_pdf_document

logger = logging.getLogger(__name__)

current_dir = Path(__file__).parent
file_path = current_dir / "data" / "cs-concepts.pdf"


def main() -> list[Chunk]:
    documents = load_pdf_document(file_path)
    if not documents:
        logger.warning("No extractable text in %s.", file_path.name)
        return []

    # Chunk across the whole document rather than page by page, so sentences
    # spanning a page break stay whole and only one undersized tail can occur.
    # page_number is Optional[int] on SourceDocument in general, but
    # load_pdf_document always sets it (index + 1); the filter narrows the
    # type for chunk_document without changing behavior on real PDF input.
    all_chunks = chunk_document(
        [(doc.page_number, doc.raw_text) for doc in documents if doc.page_number is not None],
        source_name=documents[0].source_name,
        document_hash=documents[0].document_hash,
        min_word=200,
        max_word=350,
        overlap_sentences=2,
    )

    container = get_container()
    failed_chunks = embed_and_store(all_chunks, container)

    logger.info("Document count (pages): %d", len(documents))
    logger.info("Chunks count: %d", len(all_chunks))
    logger.debug("First chunk: %s", all_chunks[0])

    if failed_chunks:
        # Nothing else imports main() (verified), so it's safe for it to own
        # exit-code responsibility directly rather than needing a wrapper.
        sys.exit(1)

    return all_chunks


if __name__ == "__main__":
    # Root stays at WARNING so third-party SDK loggers (azure.cosmos does
    # full HTTP request/response tracing at INFO, including headers) don't
    # get pulled up to INFO along with our own progress logging - only this
    # app's own loggers ("src.*", "__main__") are raised.
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("src").setLevel(logging.INFO)
    logging.getLogger("__main__").setLevel(logging.INFO)
    main()

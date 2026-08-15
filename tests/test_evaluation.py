from src.evaluation import EvalQuestion, evaluate, hit_at_k, is_relevant, reciprocal_rank


def make_result(source_name: str, page_number: int, page_end: int | None = None) -> dict:
    return {
        "chunk_text": "irrelevant text",
        "source_name": source_name,
        "page_number": page_number,
        "page_end": page_end if page_end is not None else page_number,
        "similarity_score": 0.1,
    }


def test_is_relevant_exact_page_match():
    result = make_result("a.pdf", page_number=5)
    assert is_relevant(result, "a.pdf", {5}) is True


def test_is_relevant_multi_page_chunk_overlaps_expected_page():
    # Chunk spans pages 4-6; question expects page 5 - the chunk should still
    # count, since a stored chunk commonly covers more than one page.
    result = make_result("a.pdf", page_number=4, page_end=6)
    assert is_relevant(result, "a.pdf", {5}) is True


def test_is_relevant_wrong_document_is_never_relevant():
    # Same page number, different source document - must not count as a hit
    # even though the page overlaps, since the container can hold chunks
    # from more than one ingested PDF.
    result = make_result("other.pdf", page_number=5)
    assert is_relevant(result, "a.pdf", {5}) is False


def test_is_relevant_page_outside_expected_range():
    result = make_result("a.pdf", page_number=10)
    assert is_relevant(result, "a.pdf", {5}) is False


def test_is_relevant_missing_page_number_is_not_relevant():
    result = {"source_name": "a.pdf", "page_number": None, "page_end": None}
    assert is_relevant(result, "a.pdf", {5}) is False


def test_reciprocal_rank_first_result_relevant():
    results = [make_result("a.pdf", 5), make_result("a.pdf", 1)]
    assert reciprocal_rank(results, "a.pdf", {5}) == 1.0


def test_reciprocal_rank_second_result_relevant():
    results = [make_result("a.pdf", 1), make_result("a.pdf", 5)]
    assert reciprocal_rank(results, "a.pdf", {5}) == 0.5


def test_reciprocal_rank_no_relevant_result():
    results = [make_result("a.pdf", 1), make_result("a.pdf", 2)]
    assert reciprocal_rank(results, "a.pdf", {5}) == 0.0


def test_hit_at_k_true_within_cutoff():
    results = [make_result("a.pdf", 1), make_result("a.pdf", 5), make_result("a.pdf", 2)]
    assert hit_at_k(results, "a.pdf", {5}, k=2) is True


def test_hit_at_k_false_outside_cutoff():
    results = [make_result("a.pdf", 1), make_result("a.pdf", 2), make_result("a.pdf", 5)]
    assert hit_at_k(results, "a.pdf", {5}, k=2) is False


def test_evaluate_aggregates_recall_and_mrr_across_questions():
    q1 = EvalQuestion(question="q1", expected_pages={5})
    q2 = EvalQuestion(question="q2", expected_pages={9})

    # q1: relevant result at rank 1 -> hit@1, hit@3, RR=1.0
    q1_results = [make_result("a.pdf", 5), make_result("a.pdf", 1)]
    # q2: relevant result at rank 3 -> miss@1, hit@3, RR=1/3
    q2_results = [make_result("a.pdf", 1), make_result("a.pdf", 2), make_result("a.pdf", 9)]

    summary = evaluate("a.pdf", [(q1, q1_results), (q2, q2_results)], k_values=[1, 3])

    assert summary.num_questions == 2
    assert summary.recall_at_k[1] == 0.5  # only q1 hits within top 1
    assert summary.recall_at_k[3] == 1.0  # both hit within top 3
    assert summary.mrr == (1.0 + 1 / 3) / 2


def test_evaluate_empty_question_list():
    summary = evaluate("a.pdf", [], k_values=[1, 5])
    assert summary.num_questions == 0
    assert summary.recall_at_k == {1: 0.0, 5: 0.0}
    assert summary.mrr == 0.0

from src.safety import is_flagged


def test_is_flagged_empty_categories():
    assert is_flagged([]) is False


def test_is_flagged_all_below_threshold():
    categories = [{"category": "Hate", "severity": 0}, {"category": "Violence", "severity": 0}]
    assert is_flagged(categories) is False


def test_is_flagged_one_at_threshold():
    categories = [{"category": "Hate", "severity": 0}, {"category": "SelfHarm", "severity": 2}]
    assert is_flagged(categories) is True


def test_is_flagged_one_above_threshold():
    categories = [{"category": "Sexual", "severity": 6}]
    assert is_flagged(categories) is True

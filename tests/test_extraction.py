from src.extraction import get_file_hash


def write(tmp_path, name, content: bytes):
    path = tmp_path / name
    path.write_bytes(content)
    return path


def test_hash_is_twelve_hex_characters(tmp_path):
    digest = get_file_hash(write(tmp_path, "a.pdf", b"content"))
    assert len(digest) == 12
    assert all(character in "0123456789abcdef" for character in digest)


def test_hash_is_stable_across_calls(tmp_path):
    path = write(tmp_path, "a.pdf", b"content")
    assert get_file_hash(path) == get_file_hash(path)


def test_hash_depends_on_content_not_filename(tmp_path):
    first = write(tmp_path, "first.pdf", b"identical")
    second = write(tmp_path, "second.pdf", b"identical")
    assert get_file_hash(first) == get_file_hash(second)


def test_hash_changes_when_content_changes(tmp_path):
    original = get_file_hash(write(tmp_path, "a.pdf", b"before"))
    edited = get_file_hash(write(tmp_path, "a.pdf", b"after"))
    assert original != edited

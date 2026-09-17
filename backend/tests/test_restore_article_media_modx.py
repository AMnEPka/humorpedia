from pathlib import Path

import pytest

from scripts.restore_article_media_modx import legacy_url, mojibake_source, target_path


def test_target_path_stays_inside_imported_images(tmp_path):
    target = target_path("/media/imported/images/article/тест.jpg", tmp_path)
    assert target == tmp_path / "article" / "тест.jpg"
    with pytest.raises(ValueError):
        target_path("/media/imported/images/../../outside.jpg", tmp_path)
    with pytest.raises(ValueError):
        target_path("/media/imported/assets/cache.webp", tmp_path)


def test_finds_cp866_mojibake_copy(tmp_path):
    expected_name = "смет1.jpg"
    broken_name = expected_name.encode("utf-8").decode("cp866")
    broken = tmp_path / broken_name
    broken.write_bytes(b"image")

    assert mojibake_source(tmp_path / expected_name) == broken


def test_legacy_url_quotes_unicode_and_spaces():
    assert legacy_url("/media/imported/images/article/лг лого.png") == (
        "https://humorpedia.ru/images/article/%D0%BB%D0%B3%20%D0%BB%D0%BE%D0%B3%D0%BE.png"
    )

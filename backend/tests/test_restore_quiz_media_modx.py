from pathlib import Path

import pytest

from scripts.restore_quiz_media_modx import target_path


def test_quiz_media_target_stays_inside_imported_root(tmp_path):
    target = target_path("/media/imported/assets/project_files/img/cover.jpg", tmp_path)
    assert target == tmp_path / "assets" / "project_files" / "img" / "cover.jpg"
    with pytest.raises(ValueError):
        target_path("/media/imported/../../outside.jpg", tmp_path)
    with pytest.raises(ValueError):
        target_path("https://humorpedia.ru/images/cover.jpg", tmp_path)

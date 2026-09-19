import pytest

from services.crud import build_alphabetical_pipeline, build_query


def test_alphabetical_pipeline_groups_before_pagination():
    pipeline = build_alphabetical_pipeline(
        {"status": "published"}, 24, 24, ["title", "name"]
    )

    assert [next(iter(stage)) for stage in pipeline] == [
        "$match", "$set", "$set", "$sort", "$skip", "$limit", "$project"
    ]
    assert pipeline[3]["$sort"] == {
        "_alphabet_sort_group": 1,
        "_alphabet_sort_value": 1,
        "_id": 1,
    }
    assert pipeline[4] == {"$skip": 24}
    assert pipeline[5] == {"$limit": 24}

    branches = pipeline[2]["$set"]["_alphabet_sort_group"]["$switch"]["branches"]
    assert branches[0]["case"]["$regexMatch"]["regex"] == (
        "^[\u0400-\u052F\u2DE0-\u2DFF\uA640-\uA69F]"
    )
    assert branches[0]["then"] == 0
    assert branches[1]["case"]["$regexMatch"]["regex"] == "^[A-Za-z]"
    assert branches[1]["then"] == 1


def test_alphabetical_pipeline_uses_first_non_empty_display_field():
    pipeline = build_alphabetical_pipeline({}, 0, 10, ["title", "name"])
    sort_value = pipeline[1]["$set"]["_alphabet_sort_value"]["$trim"]["input"]
    serialized = repr(sort_value)

    assert "$title" in serialized
    assert "$name" in serialized
    assert "$cond" in serialized


def test_alphabetical_pipeline_requires_a_display_field():
    with pytest.raises(ValueError):
        build_alphabetical_pipeline({}, 0, 10, [])


def test_query_builder_treats_search_and_letter_as_literal_text():
    query = build_query(search="[", search_fields=["title"], letter=".")

    assert query["$or"][0]["title"]["$regex"] == r"\["
    assert query["title"]["$regex"] == r"^\."


def test_query_builder_treats_e_and_yo_as_equivalent_in_text_search():
    query = build_query(search="звезды", search_fields=["title"])

    assert query["$or"][0]["title"]["$regex"] == "зв[её]зды"

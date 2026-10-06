import threading

import pytest

from services import persona_research


def make_document(store, lock, text, source_key, now=1):
    return persona_research.create_document(
        {
            "title": f"Source {source_key}",
            "original_name": f"{source_key}.txt",
            "filename": f"{source_key}.txt",
            "content_type": "text/plain",
            "sha256": "a" * 64,
            "size": len(text),
            "source_key": source_key,
        },
        text,
        store,
        lock,
        "researcher",
        now=now,
    )


def make_factoid(store, lock, document, start, end, simplified, now):
    text = document["extracted_text"]
    return persona_research.create_factoid(
        document["id"],
        {
            "start": start,
            "end": end,
            "excerpt": text[start:end],
            "simplified": simplified,
        },
        store,
        lock,
        "researcher",
        now=now,
    )


def test_factoid_requires_exact_source_highlight():
    store = {}
    lock = threading.Lock()
    document = make_document(
        store,
        lock,
        "I ask someone else because I worry about pressing the wrong thing.",
        "interview-01",
    )

    factoid = make_factoid(
        store,
        lock,
        document,
        0,
        18,
        "Seeks help with unfamiliar tasks.",
        2,
    )
    assert factoid["excerpt"] == document["extracted_text"][0:18]

    with pytest.raises(ValueError, match="no longer matches"):
        persona_research.create_factoid(
            document["id"],
            {
                "start": 0,
                "end": 18,
                "excerpt": "Edited quotation",
                "simplified": "Invalid evidence",
            },
            store,
            lock,
            "researcher",
        )


def test_three_or_fewer_factoids_are_weak_but_four_are_supported():
    store = {}
    lock = threading.Lock()
    document = make_document(
        store,
        lock,
        "alpha beta gamma delta epsilon zeta eta theta",
        "interview-01",
    )
    factoids = [
        make_factoid(store, lock, document, 0, 5, "Alpha", 2),
        make_factoid(store, lock, document, 6, 10, "Beta", 3),
        make_factoid(store, lock, document, 11, 16, "Gamma", 4),
        make_factoid(store, lock, document, 17, 22, "Delta", 5),
    ]

    weak = persona_research.evidence_stats(
        [item["id"] for item in factoids[:3]], store, "researcher"
    )
    supported = persona_research.evidence_stats(
        [item["id"] for item in factoids], store, "researcher"
    )

    assert weak["strength"] == "weak"
    assert weak["weak"] is True
    assert supported["strength"] == "supported"
    assert supported["weak"] is False


def test_repeated_factoids_do_not_inflate_independent_source_count():
    store = {}
    lock = threading.Lock()
    first = make_document(
        store,
        lock,
        "alpha beta gamma delta epsilon",
        "interview-01",
    )
    second = make_document(
        store,
        lock,
        "one two three four five",
        "interview-02",
        now=2,
    )
    factoids = [
        make_factoid(store, lock, first, 0, 5, "Alpha", 3),
        make_factoid(store, lock, first, 6, 10, "Beta", 4),
        make_factoid(store, lock, first, 11, 16, "Gamma", 5),
        make_factoid(store, lock, first, 17, 22, "Delta", 6),
    ]
    first_stats = persona_research.evidence_stats(
        [item["id"] for item in factoids], store, "researcher"
    )
    assert first_stats["evidence_count"] == 4
    assert first_stats["independent_source_count"] == 1

    second_factoid = make_factoid(
        store, lock, second, 0, 3, "One", 7
    )
    mixed = persona_research.evidence_stats(
        [*[item["id"] for item in factoids], second_factoid["id"]],
        store,
        "researcher",
    )
    assert mixed["evidence_count"] == 5
    assert mixed["independent_source_count"] == 2


def test_affinity_group_drives_persona_characteristic_evidence():
    store = {}
    lock = threading.Lock()
    document = make_document(
        store,
        lock,
        "I avoid settings. I ask for help. I prefer familiar screens.",
        "participant-a",
    )
    factoids = [
        make_factoid(store, lock, document, 0, 17, "Avoids settings", 2),
        make_factoid(store, lock, document, 18, 33, "Asks for help", 3),
    ]
    group = persona_research.create_affinity_group(
        {"title": "Low confidence", "category": "confidence"},
        store,
        lock,
        "researcher",
        now=4,
    )
    for factoid in factoids:
        persona_research.assign_factoid_to_group(
            factoid["id"], group["id"], store, lock, "researcher"
        )

    persona = persona_research.create_persona(
        {
            "name": "Occasional administrator",
            "persona_type": "archetype",
        },
        store,
        lock,
        "researcher",
        now=5,
    )
    persona_research.add_characteristic(
        persona["id"],
        {
            "label": "Low confidence with unfamiliar settings",
            "category": "confidence",
            "affinity_group_ids": [group["id"]],
        },
        store,
        lock,
        "researcher",
        now=6,
    )

    view = persona_research.persona_view(
        persona["id"], store, "researcher"
    )
    characteristic = view["characteristics"][0]
    assert characteristic["stats"]["evidence_count"] == 2
    assert characteristic["stats"]["independent_source_count"] == 1
    assert characteristic["stats"]["weak"] is True
    assert {item["simplified"] for item in characteristic["factoids"]} == {
        "Avoids settings",
        "Asks for help",
    }


def test_individual_and_archetype_personas_are_distinct():
    store = {}
    lock = threading.Lock()
    individual = persona_research.create_persona(
        {
            "name": "Alex",
            "persona_type": "individual",
            "linked_profile_id": "profile-1",
        },
        store,
        lock,
        "researcher",
    )
    archetype = persona_research.create_persona(
        {
            "name": "Cautious operator",
            "persona_type": "archetype",
            "linked_profile_id": "profile-1",
        },
        store,
        lock,
        "researcher",
    )

    assert individual["linked_profile_id"] == "profile-1"
    assert archetype["linked_profile_id"] == ""

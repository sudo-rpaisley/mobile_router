"""Evidence-backed research personas, factoids, and affinity groups."""

import time
import uuid
from copy import deepcopy


STORE_KEYS = ("documents", "factoids", "affinity_groups", "personas")
PERSONA_TYPES = {"individual", "archetype"}
DEFAULT_CHARACTERISTIC_CATEGORIES = (
    "skills",
    "knowledge",
    "experience",
    "behaviours",
    "goals",
    "motivations",
    "needs",
    "frustrations",
    "perceptions",
    "attitudes",
    "outlooks",
    "confidence",
    "expectations",
    "preferences",
    "constraints",
    "technology familiarity",
)


def ensure_store(store):
    for key in STORE_KEYS:
        store.setdefault(key, {})
    return store


def _clean(value, limit=500):
    return str(value or "").strip()[:limit]


def _owned(record, owner):
    return not owner or record.get("owner") == owner


def list_records(store, kind, owner=None):
    ensure_store(store)
    records = [
        deepcopy(record)
        for record in store[kind].values()
        if _owned(record, owner)
    ]
    return sorted(records, key=lambda item: item.get("updated_at", item.get("created_at", 0)), reverse=True)


def get_record(store, kind, record_id, owner=None):
    ensure_store(store)
    record = store[kind].get(record_id)
    if not record or not _owned(record, owner):
        return None
    return deepcopy(record)


def create_document(metadata, extracted_text, store, lock, owner, now=None):
    title = _clean(metadata.get("title") or metadata.get("original_name"), 200)
    if not title:
        raise ValueError("Document title is required.")
    text = str(extracted_text or "")
    if not text.strip():
        raise ValueError("No searchable text could be extracted from this document.")
    timestamp = now if now is not None else time.time()
    document = {
        "id": str(uuid.uuid4()),
        "owner": owner,
        "title": title,
        "original_name": _clean(metadata.get("original_name"), 255),
        "filename": _clean(metadata.get("filename"), 255),
        "content_type": _clean(metadata.get("content_type"), 120),
        "sha256": _clean(metadata.get("sha256"), 64),
        "size": int(metadata.get("size") or 0),
        "source_key": _clean(metadata.get("source_key"), 160),
        "source_label": _clean(metadata.get("source_label"), 200),
        "participant_profile_id": _clean(metadata.get("participant_profile_id"), 80),
        "notes": _clean(metadata.get("notes"), 2000),
        "extracted_text": text,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    with lock:
        ensure_store(store)
        store["documents"][document["id"]] = document
    return deepcopy(document)



def profile_evidence_candidates(profile):
    """Return non-secret profile fields that may be deliberately used as evidence."""
    profile = profile or {}
    candidates = []

    def add(ref, label, value, kind):
        excerpt = str(value or "").strip()
        if excerpt:
            candidates.append({
                "ref": ref,
                "label": label,
                "excerpt": excerpt[:4000],
                "kind": kind,
            })

    add("profile:notes", "Profile notes", profile.get("notes"), "notes")
    add("profile:organization", "Organisation", profile.get("organization"), "profile")
    add("profile:job_title", "Job title", profile.get("job_title"), "profile")
    if profile.get("tags"):
        add("profile:tags", "Tags", ", ".join(profile.get("tags") or []), "profile")

    for field in profile.get("custom_fields", []):
        field_id = field.get("id") or field.get("name") or str(len(candidates))
        add(
            f"custom:{field_id}",
            f"Custom field: {field.get('name') or 'Field'}",
            field.get("value"),
            "custom_field",
        )

    for device in profile.get("devices", []):
        parts = [
            device.get("name"),
            device.get("device_type"),
            device.get("manufacturer"),
            device.get("model"),
            device.get("operating_system"),
            device.get("hostname"),
            device.get("status"),
            device.get("notes"),
        ]
        add(
            f"device:{device.get('id')}",
            f"Device: {device.get('name') or device.get('device_type') or 'Device'}",
            " · ".join(str(value).strip() for value in parts if value),
            "device",
        )

    for relationship in profile.get("relationships", []):
        parts = [relationship.get("relationship"), relationship.get("notes")]
        add(
            f"relationship:{relationship.get('id')}",
            f"Relationship: {relationship.get('relationship') or 'Relationship'}",
            " · ".join(str(value).strip() for value in parts if value),
            "relationship",
        )

    for link in profile.get("social_links", []):
        parts = [
            link.get("platform"),
            link.get("account"),
            link.get("url"),
            link.get("source"),
        ]
        add(
            f"account:{link.get('id')}",
            f"Account: {link.get('platform') or 'Online account'}",
            " · ".join(str(value).strip() for value in parts if value),
            "account",
        )

    return candidates


def create_profile_factoid(profile_id, source, values, store, lock, owner, now=None):
    """Create an immutable factoid snapshot from an explicitly selected profile field."""
    source_ref = _clean(source.get("ref"), 200)
    source_label = _clean(source.get("label"), 300)
    excerpt = str(source.get("excerpt") or "").strip()
    if not source_ref or not excerpt:
        raise ValueError("Choose a profile evidence source.")
    simplified = _clean(values.get("simplified"), 1000)
    if not simplified:
        simplified = excerpt[:1000]
    timestamp = now if now is not None else time.time()
    factoid = {
        "id": str(uuid.uuid4()),
        "owner": owner,
        "document_id": "",
        "source_type": "profile",
        "source_profile_id": _clean(profile_id, 80),
        "source_ref": source_ref,
        "source_label": source_label,
        "excerpt": excerpt,
        "simplified": simplified,
        "notes": _clean(values.get("notes"), 2000),
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    with lock:
        ensure_store(store)
        store["factoids"][factoid["id"]] = factoid
    return deepcopy(factoid)


def create_factoid(document_id, values, store, lock, owner, now=None):
    with lock:
        ensure_store(store)
        document = store["documents"].get(document_id)
        if not document or not _owned(document, owner):
            raise KeyError(document_id)

        try:
            start = int(values.get("start"))
            end = int(values.get("end"))
        except (TypeError, ValueError):
            raise ValueError("Highlight start and end offsets are required.") from None

        text = document.get("extracted_text") or ""
        if start < 0 or end <= start or end > len(text):
            raise ValueError("The highlighted range is outside the document.")
        excerpt = text[start:end]
        submitted_excerpt = str(values.get("excerpt") or excerpt)
        if submitted_excerpt != excerpt:
            raise ValueError("The highlighted text no longer matches the source document.")

        simplified = _clean(values.get("simplified"), 1000)
        if not simplified:
            simplified = excerpt.strip()[:1000]
        timestamp = now if now is not None else time.time()
        factoid = {
            "id": str(uuid.uuid4()),
            "owner": owner,
            "document_id": document_id,
            "source_type": "document",
            "source_profile_id": document.get("participant_profile_id") or "",
            "source_ref": f"document:{document_id}:{start}:{end}",
            "source_label": document.get("title") or document.get("original_name") or "Research document",
            "start": start,
            "end": end,
            "excerpt": excerpt,
            "simplified": simplified,
            "notes": _clean(values.get("notes"), 2000),
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        store["factoids"][factoid["id"]] = factoid
    return deepcopy(factoid)


def create_affinity_group(values, store, lock, owner, now=None):
    title = _clean(values.get("title"), 160)
    if not title:
        raise ValueError("Affinity group title is required.")
    timestamp = now if now is not None else time.time()
    group = {
        "id": str(uuid.uuid4()),
        "owner": owner,
        "title": title,
        "category": _clean(values.get("category"), 120),
        "description": _clean(values.get("description"), 1000),
        "factoid_ids": [],
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    with lock:
        ensure_store(store)
        store["affinity_groups"][group["id"]] = group
    return deepcopy(group)


def assign_factoid_to_group(factoid_id, group_id, store, lock, owner, now=None):
    timestamp = now if now is not None else time.time()
    with lock:
        ensure_store(store)
        factoid = store["factoids"].get(factoid_id)
        if not factoid or not _owned(factoid, owner):
            raise KeyError(factoid_id)
        target = None
        if group_id:
            target = store["affinity_groups"].get(group_id)
            if not target or not _owned(target, owner):
                raise KeyError(group_id)
        for group in store["affinity_groups"].values():
            if _owned(group, owner) and factoid_id in group.get("factoid_ids", []):
                group["factoid_ids"] = [item for item in group["factoid_ids"] if item != factoid_id]
                group["updated_at"] = timestamp
        if target is not None:
            target.setdefault("factoid_ids", []).append(factoid_id)
            target["updated_at"] = timestamp
    return deepcopy(target) if target else None


def create_persona(values, store, lock, owner, now=None):
    name = _clean(values.get("name"), 160)
    if not name:
        raise ValueError("Persona name is required.")
    persona_type = _clean(values.get("persona_type"), 20).casefold() or "archetype"
    if persona_type not in PERSONA_TYPES:
        raise ValueError("Persona type must be individual or archetype.")
    linked_profile_id = _clean(values.get("linked_profile_id"), 80)
    if persona_type != "individual":
        linked_profile_id = ""
    timestamp = now if now is not None else time.time()
    persona = {
        "id": str(uuid.uuid4()),
        "owner": owner,
        "name": name,
        "persona_type": persona_type,
        "linked_profile_id": linked_profile_id,
        "summary": _clean(values.get("summary"), 3000),
        "characteristics": [],
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    with lock:
        ensure_store(store)
        store["personas"][persona["id"]] = persona
    return deepcopy(persona)


def add_characteristic(persona_id, values, store, lock, owner, now=None):
    label = _clean(values.get("label"), 300)
    if not label:
        raise ValueError("Characteristic text is required.")
    group_ids = values.get("affinity_group_ids") or []
    if isinstance(group_ids, str):
        group_ids = [group_ids]
    factoid_ids = values.get("factoid_ids") or []
    if isinstance(factoid_ids, str):
        factoid_ids = [factoid_ids]
    timestamp = now if now is not None else time.time()

    with lock:
        ensure_store(store)
        persona = store["personas"].get(persona_id)
        if not persona or not _owned(persona, owner):
            raise KeyError(persona_id)

        valid_groups = []
        for group_id in dict.fromkeys(group_ids):
            group = store["affinity_groups"].get(group_id)
            if group and _owned(group, owner):
                valid_groups.append(group_id)
        valid_factoids = []
        for factoid_id in dict.fromkeys(factoid_ids):
            factoid = store["factoids"].get(factoid_id)
            if factoid and _owned(factoid, owner):
                valid_factoids.append(factoid_id)

        characteristic = {
            "id": str(uuid.uuid4()),
            "label": label,
            "category": _clean(values.get("category"), 120),
            "affinity_group_ids": valid_groups,
            "factoid_ids": valid_factoids,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        persona.setdefault("characteristics", []).append(characteristic)
        persona["updated_at"] = timestamp
    return deepcopy(characteristic)


def delete_characteristic(persona_id, characteristic_id, store, lock, owner):
    with lock:
        ensure_store(store)
        persona = store["personas"].get(persona_id)
        if not persona or not _owned(persona, owner):
            raise KeyError(persona_id)
        before = len(persona.get("characteristics", []))
        persona["characteristics"] = [
            item for item in persona.get("characteristics", [])
            if item.get("id") != characteristic_id
        ]
        if len(persona["characteristics"]) == before:
            return False
        persona["updated_at"] = time.time()
        return True


def _characteristic_factoid_ids(characteristic, store):
    factoid_ids = list(characteristic.get("factoid_ids") or [])
    for group_id in characteristic.get("affinity_group_ids") or []:
        group = store["affinity_groups"].get(group_id) or {}
        factoid_ids.extend(group.get("factoid_ids") or [])
    return list(dict.fromkeys(factoid_ids))


def evidence_stats(factoid_ids, store, owner=None):
    ensure_store(store)
    factoids = []
    documents = []
    participant_ids = set()
    independent_sources = set()
    profile_source_ids = set()

    for factoid_id in dict.fromkeys(factoid_ids or []):
        factoid = store["factoids"].get(factoid_id)
        if not factoid or not _owned(factoid, owner):
            continue
        source_type = factoid.get("source_type") or (
            "document" if factoid.get("document_id") else "profile"
        )
        if source_type == "document":
            document = store["documents"].get(factoid.get("document_id"))
            if not document or not _owned(document, owner):
                continue
            documents.append(document)
            participant_id = (
                factoid.get("source_profile_id")
                or document.get("participant_profile_id")
            )
            if participant_id:
                participant_ids.add(participant_id)
            independent_sources.add(
                document.get("source_key")
                or participant_id
                or document["id"]
            )
        elif source_type == "profile":
            participant_id = factoid.get("source_profile_id")
            if not participant_id:
                continue
            participant_ids.add(participant_id)
            profile_source_ids.add(participant_id)
            independent_sources.add(f"profile:{participant_id}")
        else:
            continue
        factoids.append(factoid)

    evidence_count = len(factoids)
    document_ids = {item["id"] for item in documents}
    independent_source_count = len(independent_sources)
    independent_people_count = len(participant_ids)
    strength = (
        "unevidenced"
        if evidence_count == 0
        else ("weak" if evidence_count <= 3 else "supported")
    )
    return {
        "evidence_count": evidence_count,
        "document_count": len(document_ids),
        "participant_count": independent_people_count,
        "independent_people_count": independent_people_count,
        "profile_source_count": len(profile_source_ids),
        "independent_source_count": independent_source_count,
        "source_diversity": (
            "none"
            if independent_source_count == 0
            else ("single" if independent_source_count == 1 else "multiple")
        ),
        "low_diversity": evidence_count > 1 and independent_source_count <= 1,
        "strength": strength,
        "weak": evidence_count <= 3,
    }


def affinity_group_view(group, store, owner=None):
    item = deepcopy(group)
    item["factoids"] = [
        deepcopy(store["factoids"][factoid_id])
        for factoid_id in group.get("factoid_ids", [])
        if factoid_id in store["factoids"] and _owned(store["factoids"][factoid_id], owner)
    ]
    item["stats"] = evidence_stats([factoid["id"] for factoid in item["factoids"]], store, owner)
    return item


def persona_view(persona_id, store, owner=None):
    ensure_store(store)
    persona = store["personas"].get(persona_id)
    if not persona or not _owned(persona, owner):
        return None
    item = deepcopy(persona)
    all_factoid_ids = []
    rendered = []
    for characteristic in persona.get("characteristics", []):
        view = deepcopy(characteristic)
        ids = _characteristic_factoid_ids(characteristic, store)
        view["factoid_ids_resolved"] = ids
        view["stats"] = evidence_stats(ids, store, owner)
        view["factoids"] = [
            deepcopy(store["factoids"][factoid_id])
            for factoid_id in ids
            if factoid_id in store["factoids"] and _owned(store["factoids"][factoid_id], owner)
        ]
        view["groups"] = [
            deepcopy(store["affinity_groups"][group_id])
            for group_id in characteristic.get("affinity_group_ids", [])
            if group_id in store["affinity_groups"] and _owned(store["affinity_groups"][group_id], owner)
        ]
        all_factoid_ids.extend(ids)
        rendered.append(view)
    item["characteristics"] = rendered
    item["stats"] = evidence_stats(all_factoid_ids, store, owner)
    item["weak_characteristics"] = sum(characteristic["stats"]["weak"] for characteristic in rendered)
    item["unevidenced_characteristics"] = sum(characteristic["stats"]["evidence_count"] == 0 for characteristic in rendered)
    return item


def factoid_profile_id(factoid, store):
    """Return the individual profile represented by a factoid, when known."""
    if factoid.get("source_profile_id"):
        return factoid.get("source_profile_id")
    document = store.get("documents", {}).get(factoid.get("document_id")) or {}
    return document.get("participant_profile_id") or ""


def profile_research_view(profile_id, store, owner=None):
    """Collect documents, factoids, themes, and personas connected to one profile."""
    ensure_store(store)
    documents = [
        deepcopy(item)
        for item in store["documents"].values()
        if _owned(item, owner)
        and item.get("participant_profile_id") == profile_id
    ]
    factoids = [
        deepcopy(item)
        for item in store["factoids"].values()
        if _owned(item, owner)
        and factoid_profile_id(item, store) == profile_id
    ]
    factoid_ids = {item["id"] for item in factoids}
    groups = [
        affinity_group_view(item, store, owner)
        for item in store["affinity_groups"].values()
        if _owned(item, owner)
        and factoid_ids.intersection(item.get("factoid_ids") or [])
    ]
    personas = []
    for item in store["personas"].values():
        if not _owned(item, owner):
            continue
        view = persona_view(item["id"], store, owner)
        resolved_ids = {
            factoid_id
            for characteristic in view.get("characteristics", [])
            for factoid_id in characteristic.get("factoid_ids_resolved", [])
        }
        if (
            item.get("linked_profile_id") == profile_id
            or factoid_ids.intersection(resolved_ids)
        ):
            view["relationship_to_profile"] = (
                "individual"
                if item.get("linked_profile_id") == profile_id
                else "contributor"
            )
            personas.append(view)
    stats = evidence_stats(list(factoid_ids), store, owner)
    return {
        "documents": sorted(
            documents, key=lambda item: item.get("created_at", 0), reverse=True
        ),
        "factoids": sorted(
            factoids, key=lambda item: item.get("created_at", 0), reverse=True
        ),
        "groups": groups,
        "personas": personas,
        "stats": stats,
    }


def document_highlights(document_id, store, owner=None):
    ensure_store(store)
    return sorted(
        [
            deepcopy(factoid)
            for factoid in store["factoids"].values()
            if factoid.get("document_id") == document_id and _owned(factoid, owner)
        ],
        key=lambda item: (item.get("start", 0), item.get("end", 0)),
    )

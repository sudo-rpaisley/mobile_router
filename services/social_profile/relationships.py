"""Relationships, duplicate detection, and profile merge workflows."""

import time
import uuid
from copy import deepcopy


def add_relationship(profile_id, values, store, lock, now=None):
    target_id = str(values.get('target_profile_id') or '')
    relationship = str(values.get('relationship') or '').strip()[:80]
    if not relationship or target_id == profile_id:
        raise ValueError(
            'Choose another individual and enter a relationship.'
        )
    with lock:
        if profile_id not in store or target_id not in store:
            raise KeyError(target_id)
        if store[profile_id].get('owner') != store[target_id].get('owner'):
            raise ValueError('Relationships can only link your own profiles.')
        item = {
            'id': str(uuid.uuid4()),
            'target_profile_id': target_id,
            'relationship': relationship,
            'notes': str(values.get('notes') or '').strip()[:500],
            'created_at': now if now is not None else time.time(),
        }
        store[profile_id].setdefault('relationships', []).append(item)
        store[profile_id]['updated_at'] = item['created_at']
        return deepcopy(item)


def delete_relationship(profile_id, relationship_id, store, lock):
    with lock:
        if profile_id not in store:
            raise KeyError(profile_id)
        items = store[profile_id].setdefault('relationships', [])
        store[profile_id]['relationships'] = [
            item
            for item in items
            if item.get('id') != relationship_id
        ]
        return len(items) != len(store[profile_id]['relationships'])


def duplicate_candidates(profiles):
    """Return likely duplicate pairs based on normalized identity values."""
    candidates = []
    for index, left in enumerate(profiles):
        left_values = {
            str(left.get('full_name') or '').casefold().strip()
        }
        left_values.update(
            str(item.get('value') or '').casefold()
            for item in left.get('emails', [])
        )
        left_values.update(
            str(item.get('mac') or '').casefold()
            for item in left.get('devices', [])
        )
        left_values.discard('')
        for right in profiles[index + 1:]:
            right_values = {
                str(right.get('full_name') or '').casefold().strip()
            }
            right_values.update(
                str(item.get('value') or '').casefold()
                for item in right.get('emails', [])
            )
            right_values.update(
                str(item.get('mac') or '').casefold()
                for item in right.get('devices', [])
            )
            matches = sorted(left_values & (right_values - {''}))
            if matches:
                candidates.append(
                    {
                        'primary': left,
                        'duplicate': right,
                        'matches': matches,
                    }
                )
    return candidates


def merge_profiles(primary_id, duplicate_id, store, lock, now=None):
    if primary_id == duplicate_id:
        raise ValueError('Choose two different profiles.')
    with lock:
        primary = store.get(primary_id)
        duplicate = store.get(duplicate_id)
        if not primary or not duplicate:
            raise KeyError(duplicate_id)
        if primary.get('owner') != duplicate.get('owner'):
            raise ValueError('Profiles must have the same owner.')
        for field in (
            'emails',
            'social_links',
            'devices',
            'credentials',
            'relationships',
            'attachments',
            'custom_fields',
        ):
            existing = {
                item.get('id')
                for item in primary.setdefault(field, [])
            }
            primary[field].extend(
                deepcopy(item)
                for item in duplicate.get(field, [])
                if item.get('id') not in existing
            )
        primary['tags'] = sorted(
            set(primary.get('tags', []))
            | set(duplicate.get('tags', [])),
            key=str.casefold,
        )
        primary['notes'] = '\n\n'.join(
            filter(None, [primary.get('notes'), duplicate.get('notes')])
        )[:10000]
        primary['updated_at'] = (
            now if now is not None else time.time()
        )
        del store[duplicate_id]
        for profile in store.values():
            for relation in profile.get('relationships', []):
                if relation.get('target_profile_id') == duplicate_id:
                    relation['target_profile_id'] = primary_id
        return deepcopy(primary)

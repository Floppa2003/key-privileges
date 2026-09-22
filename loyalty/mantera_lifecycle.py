"""Retire only roster-derived Mantera cards, not independently sourced benefits.

A valid complete named roster can withdraw its own earlier claims. It cannot
prove a hotel's departure from the whole programme or invalidate another page.
Many hotel cards share the roster URL, so their native IDs are the unit of scope.
"""
from __future__ import annotations

from mantera_partners import ROSTER_URL, health, native_id, record_id
from normalized import validate_offer


def snapshot(report, records, observed_at):
    """Return a validated native-ID inventory, or None for incomplete evidence."""
    if not health(report, records):
        return None
    if report['observed_at'] != observed_at:
        raise ValueError('inventory_observation_mismatch')
    owned_pair = None
    try:
        for row in records:
            validate_offer(row)
            e = row['details']['public_reward_evidence']
            if e.get('kind') == 'public_partner':
                pair = (e['roster'], e['resort'])
                if owned_pair is not None and pair != owned_pair:
                    return None  # Valid rows from different page versions are not one snapshot.
                owned_pair = pair
    except (ValueError, KeyError, TypeError):
        return None
    if owned_pair is None:
        return None  # Empty roster evidence cannot justify mass withdrawal.
    return {'record_ids': sorted(report['mantera_public_inventory']['record_ids'])}


def hold_reason(row, details, current):
    """Validate a stored roster identity before considering a reversible hold."""
    evidence = details.get('public_reward_evidence', {})
    if evidence.get('kind') != 'public_partner':
        return None  # FAQ tiers and the separate Congress page have other provenance.
    name = evidence.get('name')
    if (not isinstance(name, str) or not name or row[2] != name
            or row[0] != record_id(native_id(name))):
        raise ValueError('lifecycle_stored_identity_mismatch')
    if row[17] != ROSTER_URL or evidence.get('url') != ROSTER_URL:
        raise ValueError('lifecycle_stored_url_mismatch')
    return None if row[0] in current['record_ids'] else 'not_in_complete_inventory'

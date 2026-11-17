"""Which card the blitz shows next (product decisions 17-18).

- Order is random, but cards that are badly overdue *relative to their
  stage interval* go first: 2 hours late on a 30-minute stage is a lot, on
  a 1-month stage it's nothing. So an interrupted session has still covered
  the cards most at risk of being forgotten.
- The same card never comes twice in a row (unless it's the only one).
- A card answered wrong is due again at once, but is held back for 5-6
  other cards and then shown first. With fewer cards left it comes back
  right after them.

The state between answers is a small dict (kept in the web session; the
mobile app keeps the same shape in memory):
    {'last': <card id or None>, 'held': {<card id>: <cards still to wait>}}
The mobile app ports this file; keep the two in step.
"""
import random

from .scheduler import STAGE_INTERVALS

COMEBACK_MIN, COMEBACK_MAX = 5, 6
OVERDUE_RATIO = 1.0  # overdue by at least one full interval of its stage


def new_state():
    return {'last': None, 'held': {}}


def overdue_ratio(card, now):
    interval = STAGE_INTERVALS[min(card.stage, len(STAGE_INTERVALS) - 1)]
    return (now - card.next_review_at) / interval


def choose_next(due_cards, now, state, rng=random):
    """Pick the next card out of `due_cards` (all already due), or None."""
    cards = list(due_cards)
    if not cards:
        return None
    held = {int(k): v for k, v in state.get('held', {}).items()}
    last = state.get('last')

    released = [c for c in cards if held.get(c.pk) == 0 and c.pk != last]
    if released:
        return rng.choice(released)

    ready = [c for c in cards if c.pk not in held and c.pk != last]
    if not ready:
        # Only held-back cards (or the one just shown) are left: show the
        # held card closest to coming back, then anything at all.
        waiting = sorted((c for c in cards if c.pk != last), key=lambda c: held.get(c.pk, 0))
        return waiting[0] if waiting else cards[0]

    urgent = [c for c in ready if overdue_ratio(c, now) >= OVERDUE_RATIO]
    return rng.choice(urgent or ready)


def after_answer(state, card_id, correct, rng=random):
    """Update the session state after `card_id` was answered."""
    held = {int(k): v for k, v in state.get('held', {}).items()}
    for k in list(held):
        if k != card_id and held[k] > 0:
            held[k] -= 1
    if correct:
        held.pop(card_id, None)
    else:
        held[card_id] = rng.randint(COMEBACK_MIN, COMEBACK_MAX)
    # JSON (session) keys are strings.
    return {'last': card_id, 'held': {str(k): v for k, v in held.items()}}

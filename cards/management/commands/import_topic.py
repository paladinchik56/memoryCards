"""Create or update a topic from a JSON file.

    python manage.py import_topic path/to/topic.json [--owner admin]

JSON: {"name": ..., "description": ..., "tags": [...], "visibility": "public",
       "cards": [{"q": "question", "a": "answer"}, ...]}

Idempotent: cards are matched by question within the topic; missing ones are
added, changed answers are updated, nothing is deleted.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Profile
from cards.models import Card, Collection


class Command(BaseCommand):
    help = 'Create or update a topic (with its cards) from a JSON file.'

    def add_arguments(self, parser):
        parser.add_argument('path')
        parser.add_argument('--owner', default='admin', help='Nickname of the owner (default: admin)')

    def handle(self, *args, path, owner, **options):
        try:
            data = json.loads(Path(path).read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as e:
            raise CommandError(f'Cannot read {path}: {e}')
        profile = Profile.objects.filter(nickname__iexact=owner).select_related('user').first()
        if profile is None:
            raise CommandError(f'No user with nickname "{owner}".')
        cards = data.get('cards') or []
        questions = [c['q'].strip() for c in cards]
        if len(set(questions)) != len(questions):
            raise CommandError('Duplicate questions in the file.')
        visibility = data.get('visibility', Collection.VISIBILITY_PUBLIC)
        if visibility not in dict(Collection.VISIBILITY_CHOICES):
            raise CommandError(f'Bad visibility: {visibility}')

        user = profile.user
        with transaction.atomic():
            topic, created = Collection.objects.get_or_create(owner=user, name=data['name'][:100])
            topic.description = data.get('description', '')[:700]
            topic.tags = data.get('tags', [])[:10]
            topic.visibility = visibility
            topic.save()
            existing = {c.question: c for c in topic.cards.all()}
            added = updated = 0
            for item in cards:
                q, a = item['q'].strip(), item['a'].strip()
                card = existing.get(q)
                if card is None:
                    Card.objects.create(user=user, collection=topic, question=q, answer=a)
                    added += 1
                elif card.answer != a:
                    card.answer, card.content_updated_at = a, timezone.now()
                    card.save()
                    updated += 1
        self.stdout.write(
            f'{"Created" if created else "Updated"} "{topic.name}": +{added} new, {updated} changed, '
            f'{topic.cards.count()} total.'
        )

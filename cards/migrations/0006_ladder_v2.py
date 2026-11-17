"""Second version of the review ladder (description/open-decisions.md, #16).

Old ladder: 90s, 30m, 12h, 2d, 2w, 2mo (stages 0-5).
New ladder: 90s, 30m, 12h, 2d, 1w, 2w, 1mo (stages 0-6).
Stages 0-3 keep their index; old 4 (2 weeks) -> new 5; old 5 (2 months,
the max) -> new 6 (1 month, the new max). Review log rows are history and
keep their old stage numbers.
"""
from django.db import migrations, models

OLD_TO_NEW = {4: 5, 5: 6}


def forwards(apps, schema_editor):
    Card = apps.get_model('cards', 'Card')
    # Highest first so a remapped card is never remapped twice.
    for old, new in sorted(OLD_TO_NEW.items(), reverse=True):
        Card.objects.filter(stage=old).update(stage=new)


def backwards(apps, schema_editor):
    Card = apps.get_model('cards', 'Card')
    Card.objects.filter(stage=4).update(stage=3)  # 1 week had no old equivalent
    for old, new in sorted(OLD_TO_NEW.items()):
        Card.objects.filter(stage=new).update(stage=old)


class Migration(migrations.Migration):

    dependencies = [
        ('cards', '0005_sync_fields'),
    ]

    operations = [
        migrations.AddField('card', 'correct_count', models.PositiveSmallIntegerField(default=0)),
        migrations.AddField('reviewlog', 'previous_correct_count', models.PositiveSmallIntegerField(default=0)),
        migrations.AddField('reviewlog', 'new_correct_count', models.PositiveSmallIntegerField(default=0)),
        migrations.RunPython(forwards, backwards),
    ]

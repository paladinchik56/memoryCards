"""Fields the mobile sync needs: client-side UUIDs, change cursors and
deletion tombstones. UUID columns are added nullable, filled per row, then
made unique -- a plain AddField(default=uuid4) would give every existing
row the same value."""
import uuid

import django.utils.timezone
from django.db import migrations, models


def fill_uuids(apps, schema_editor):
    for model_name in ('Collection', 'Card', 'ReviewLog'):
        Model = apps.get_model('cards', model_name)
        for obj in Model.objects.all().only('pk'):
            Model.objects.filter(pk=obj.pk).update(uuid=uuid.uuid4())
    Card = apps.get_model('cards', 'Card')
    Card.objects.update(content_updated_at=models.F('updated_at'))


class Migration(migrations.Migration):

    dependencies = [
        ('cards', '0004_topic_run'),
    ]

    operations = [
        migrations.AddField('collection', 'uuid', models.UUIDField(null=True, editable=False)),
        migrations.AddField('card', 'uuid', models.UUIDField(null=True, editable=False)),
        migrations.AddField('reviewlog', 'uuid', models.UUIDField(null=True, editable=False)),
        migrations.AddField(
            'collection', 'updated_at',
            models.DateTimeField(auto_now=True, default=django.utils.timezone.now), preserve_default=False,
        ),
        migrations.AddField('card', 'content_updated_at', models.DateTimeField(default=django.utils.timezone.now)),
        migrations.RunPython(fill_uuids, migrations.RunPython.noop),
        migrations.AlterField('collection', 'uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
        migrations.AlterField('card', 'uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
        migrations.AlterField('reviewlog', 'uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
        migrations.AlterField(
            'reviewlog', 'reviewed_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now),
        ),
        migrations.CreateModel(
            name='Tombstone',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user_id', models.IntegerField(db_index=True)),
                ('kind', models.CharField(choices=[('card', 'Card'), ('collection', 'Collection'), ('topic_run', 'Topic run')], max_length=10)),
                ('uuid', models.UUIDField()),
                ('deleted_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
            ],
        ),
    ]

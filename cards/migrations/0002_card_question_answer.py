# Generated manually: split Card.text into Card.question + Card.answer.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cards', '0001_initial'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='card',
            name='unique_card_text_per_user',
        ),
        migrations.RenameField(
            model_name='card',
            old_name='text',
            new_name='question',
        ),
        migrations.AddField(
            model_name='card',
            name='answer',
            field=models.TextField(default=''),
            preserve_default=False,
        ),
        migrations.AddConstraint(
            model_name='card',
            constraint=models.UniqueConstraint(fields=('user', 'question'), name='unique_card_question_per_user'),
        ),
    ]

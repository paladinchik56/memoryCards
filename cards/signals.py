from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Card, Collection, Tombstone, TopicRun


@receiver(post_delete, sender=Card)
def card_deleted(sender, instance, **kwargs):
    Tombstone.objects.create(user_id=instance.user_id, kind=Tombstone.KIND_CARD, uuid=instance.uuid)


@receiver(post_delete, sender=Collection)
def collection_deleted(sender, instance, **kwargs):
    # Its cards are kept (collection FK is SET_NULL); clients null them out
    # locally when they see this tombstone.
    Tombstone.objects.create(user_id=instance.owner_id, kind=Tombstone.KIND_COLLECTION, uuid=instance.uuid)


@receiver(post_delete, sender=TopicRun)
def topic_run_deleted(sender, instance, **kwargs):
    # Runs are deleted before their collection in a cascade, so it still exists here.
    collection_uuid = Collection.objects.filter(pk=instance.collection_id).values_list('uuid', flat=True).first()
    if collection_uuid:
        Tombstone.objects.create(user_id=instance.user_id, kind=Tombstone.KIND_TOPIC_RUN, uuid=collection_uuid)

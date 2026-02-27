from .models import LogEntry
from django.contrib.contenttypes.models import ContentType

def log_action(user, action, instance, changes):
    content_type = ContentType.objects.get_for_model(instance)
    LogEntry.objects.create(
        user=user,
        action=action,
        content_type=content_type,
        object_id=instance.pk,
        changes=changes
    )
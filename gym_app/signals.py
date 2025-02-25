from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import TrainerProfile

@receiver(post_save, sender=TrainerProfile)
def set_trainer_flag(sender, instance, created, **kwargs):
    if created:
        user = instance.user
        user.is_trainer = True
        user.save()

@receiver(post_delete, sender=TrainerProfile)
def unset_trainer_flag(sender, instance, **kwargs):
    user = instance.user
    user.is_trainer = False
    user.save()

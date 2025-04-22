from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .models import User

@receiver(post_migrate)
def create_default_manager(sender, **kwargs):
    if sender.name == 'users':
        if not User.objects.filter(userid="1234").exists():
            User.objects.create(
                name="Manager",
                last_name="Main",
                userid="1234",
                password="1234",
                position="manager"
            )
            print("✅ Default manager created (ID: 1234, Password: 1234)")

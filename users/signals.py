from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .models import User

@receiver(post_migrate)
def create_default_manager(sender, **kwargs):
    # Signal to create a default manager user after migrations are applied
    if sender.name == 'users':  # Ensure the signal is triggered for the 'users' app
        if not User.objects.filter(userid="1234").exists():  # Check if the default manager already exists
            user = User(
                name="Manager",  # Default manager's first name
                last_name="Main",  # Default manager's last name
                userid="1234",  # Default manager's unique ID
                position="manager"  # Default manager's position
            )
            user.set_password("1234")  # Hash the default password for security
            user.save()  # Save the default manager to the database
            print("✅ Default manager created (ID: 1234, Password: 1234)")  # Log the creation of the default manager

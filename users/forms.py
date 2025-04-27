# users/forms.py
import random
from django import forms
from .models import User

class UserAdminCreationForm(forms.ModelForm):
    # Custom form for creating a new user in the admin interface
    class Meta:
        model = User  # Specify the model this form is tied to
        fields = ('name', 'last_name', 'userid', 'position')  # Fields to include in the form

    def save(self, commit=True):
        # Override the save method to generate and set a random password
        user = super().save(commit=False)  # Create a user instance without saving to the database
        generated_password = f"{random.randint(1000, 9999)}"  # Generate a random 4-digit password
        user.set_password(generated_password)  # Hash and set the password
        user._plain_password = generated_password  # Temporarily store the plain password for later use
        if commit:
            user.save()  # Save the user instance to the database
        return user  # Return the user instance

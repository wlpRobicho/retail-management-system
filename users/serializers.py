from rest_framework import serializers
from .models import User
from django.db import transaction

class UserSerializer(serializers.ModelSerializer):
    # Serializer for the User model, handles serialization and deserialization of user data
    class Meta:
        model = User  # Specify the model to serialize
        fields = ['id', 'name', 'last_name', 'userid', 'password', 'position']  # Fields to include in the serialization
        extra_kwargs = {
            'password': {'write_only': True}  # Ensure the password is write-only for security
        }

    @transaction.atomic
    def create(self, validated_data):
        # Override the create method to handle password hashing
        password = validated_data.pop('password')  # Extract the password from the validated data
        user = User(**validated_data)  # Create a user instance without saving to the database
        user.set_password(password)  # Hash the password before saving
        user.save()  # Save the user instance to the database
        return user  # Return the created user instance

class LoginSerializer(serializers.Serializer):
    # Serializer for handling user login, validates userid and password
    userid = serializers.CharField()  # Field for the user's unique ID
    password = serializers.CharField()  # Field for the user's password

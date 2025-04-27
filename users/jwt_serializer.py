from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from .models import User

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    # Custom serializer for obtaining JWT tokens using userid instead of username
    username_field = 'userid'  # Use userid as the username field

    def validate(self, attrs):
        # Validate the provided userid and password
        userid = attrs.get("userid")  # Extract userid from the request
        password = attrs.get("password")  # Extract password from the request

        try:
            user = User.objects.get(userid=userid)  # Fetch the user by userid
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid credentials")  # Raise error if user not found

        if not user.check_password(password):  # Verify the password
            raise serializers.ValidationError("Invalid credentials")  # Raise error if password is incorrect

        # Generate JWT tokens for the authenticated user
        token = self.get_token(user)

        return {
            'refresh': str(token),  # Refresh token
            'access': str(token.access_token),  # Access token
            'user': {  # Include user details in the response
                'id': user.id,
                'name': user.name,
                'position': user.position,
            }
        }

    def get_fields(self):
        # Define the fields required for token generation
        fields = super().get_fields()  # Get default fields
        fields['userid'] = serializers.CharField()  # Add userid field
        fields['password'] = serializers.CharField(write_only=True)  # Add password field (write-only)
        return fields

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from .models import User


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'userid'  # 👈 override to use 'userid'

    def validate(self, attrs):
        userid = attrs.get("userid")
        password = attrs.get("password")

        try:
            user = User.objects.get(userid=userid, password=password)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid credentials")

        data = super().get_token(user)

        return {
            'access': str(data.access_token),
            'refresh': str(data),
            'user': {
                'id': user.id,
                'name': user.name,
                'position': user.position,
            }
        }

    def get_fields(self):
        fields = super().get_fields()
        fields['userid'] = serializers.CharField()
        fields['password'] = serializers.CharField()
        return fields

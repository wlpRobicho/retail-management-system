from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from .models import User, UserLog
from .serializers import LoginSerializer, UserSerializer
from .jwt_serializer import CustomTokenObtainPairSerializer
from django.utils.timezone import now
import random

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class UserLoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        userid = serializer.validated_data['userid']
        password = serializer.validated_data['password']

        if not userid.isdigit() or len(userid) != 4:
            return Response({'error': 'User ID must be a 4-digit number.'}, status=status.HTTP_400_BAD_REQUEST)

        if not password.isdigit() or len(password) != 4:
            return Response({'error': 'Password must be a 4-digit number.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(userid=userid, password=password)
        except User.DoesNotExist:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        user.last_login = now()
        user.is_active_now = True
        user.save()

        UserLog.objects.create(user=user, action='login')

        return Response({
            'message': 'Login successful',
            'user': {
                'id': user.id,
                'name': user.name,
                'position': user.position
            }
        })


class UserLogoutView(APIView):
    def post(self, request):
        userid = request.data.get('userid')

        if not userid:
            return Response({'error': 'User ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(userid=userid)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        user.last_logout = now()
        user.is_active_now = False
        user.save()

        UserLog.objects.create(user=user, action='logout')

        return Response({'message': 'Logout successful'})


class CreateEmployeeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.position != 'manager':
            raise PermissionDenied("Only managers can create employees.")

        data = request.data

        if data.get('position') != 'employee':
            return Response({'error': 'Only employees can be created via this endpoint.'}, status=status.HTTP_400_BAD_REQUEST)

        if not data.get('name') or not data.get('last_name'):
            return Response({'error': 'Name and Last Name are required.'}, status=status.HTTP_400_BAD_REQUEST)

        userid = data.get('userid')
        if not userid or not userid.isdigit() or len(userid) != 4:
            return Response({'error': 'User ID must be a 4-digit number.'}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(userid=userid).exists():
            return Response({'error': 'This User ID already exists. Please choose a different one.'}, status=status.HTTP_409_CONFLICT)

        generated_password = f"{random.randint(1000, 9999)}"

        new_data = {
            'name': data.get('name'),
            'last_name': data.get('last_name'),
            'userid': userid,
            'password': generated_password,
            'position': 'employee'
        }

        serializer = UserSerializer(data=new_data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                'message': 'Employee created successfully',
                'userid': user.userid,
                'password': generated_password
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

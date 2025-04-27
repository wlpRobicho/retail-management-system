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
from django.db import transaction
from django.db.utils import IntegrityError  
import random

class CustomTokenObtainPairView(TokenObtainPairView):
    # Custom view for obtaining JWT tokens using the CustomTokenObtainPairSerializer
    serializer_class = CustomTokenObtainPairSerializer

class UserLoginView(APIView):
    # View for handling user login
    def post(self, request):
        serializer = LoginSerializer(data=request.data)  # Validate login data
        serializer.is_valid(raise_exception=True)

        userid = serializer.validated_data['userid']  # Extract userid
        password = serializer.validated_data['password']  # Extract password

        try:
            user = User.objects.get(userid=userid)  # Fetch user by userid
        except User.DoesNotExist:
            # Log failed login attempt for unknown userid
            UserLog.objects.create(
                user=None,
                action='failed_login',
                description=f"Invalid login attempt - Unknown UserID: {userid}"
            )
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.check_password(password):  # Verify password
            # Log failed login attempt for incorrect password
            UserLog.objects.create(
                user=user,
                action='failed_login',
                description="Invalid login attempt - Wrong password"
            )
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        # Update user login status and log the successful login
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
    # View for handling user logout
    def post(self, request):
        userid = request.data.get('userid')  # Extract userid from request

        if not userid:
            return Response({'error': 'User ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(userid=userid)  # Fetch user by userid
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        # Update user logout status and log the logout action
        user.last_logout = now()
        user.is_active_now = False
        user.save()
        UserLog.objects.create(user=user, action='logout')

        return Response({'message': 'Logout successful'})

class CreateEmployeeView(APIView):
    # View for creating a new employee (restricted to managers)
    permission_classes = [IsAuthenticated]  # Require authentication

    @transaction.atomic  # Ensure atomicity for database operations
    def post(self, request):
        if request.user.position != 'manager':  # Restrict access to managers
            raise PermissionDenied("Only managers can create employees.")

        data = request.data  # Extract request data

        # Validate employee position
        if data.get('position') != 'employee':
            return Response({'error': 'Only employees can be created via this endpoint.'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate required fields
        if not data.get('name') or not data.get('last_name'):
            return Response({'error': 'Name and Last Name are required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate userid format
        userid = data.get('userid')
        if not userid or not userid.isdigit() or len(userid) != 4:
            return Response({'error': 'User ID must be a 4-digit number.'}, status=status.HTTP_400_BAD_REQUEST)

        # Check for duplicate userid
        if User.objects.filter(userid=userid).exists():
            return Response({'error': 'This User ID already exists. Please choose a different one.'}, status=status.HTTP_409_CONFLICT)

        # Generate a random password for the new employee
        generated_password = f"{random.randint(1000, 9999)}"

        # Prepare data for the new employee
        new_data = {
            'name': data.get('name'),
            'last_name': data.get('last_name'),
            'userid': userid,
            'password': generated_password,
            'position': 'employee'
        }

        # Serialize and save the new employee
        serializer = UserSerializer(data=new_data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Log the creation of the new employee
        UserLog.objects.create(
            user=request.user,
            action='create_user',
            description=f"Created employee with UserID: {user.userid}"
        )

        return Response({
            'message': 'Employee created successfully',
            'userid': user.userid,
            'password': generated_password
        }, status=status.HTTP_201_CREATED)

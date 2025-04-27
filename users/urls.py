from django.urls import path
from .views import (
    UserLoginView,  # View for user login
    UserLogoutView,  # View for user logout
    CreateEmployeeView,  # View for creating a new employee
    CustomTokenObtainPairView  # View for obtaining JWT tokens
)

urlpatterns = [
    path('login/', UserLoginView.as_view(), name='user-login'),  # Endpoint for user login
    path('logout/', UserLogoutView.as_view(), name='user-logout'),  # Endpoint for user logout
    path('create/', CreateEmployeeView.as_view(), name='user-create'),  # Endpoint for creating a new employee
    path('token/', CustomTokenObtainPairView.as_view(), name='user-token'),  # Endpoint for obtaining JWT tokens
]

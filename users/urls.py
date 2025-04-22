# users/urls.py

from django.urls import path
from .views import UserLoginView, CreateEmployeeView, UserLogoutView, CustomTokenObtainPairView

urlpatterns = [
    path('login/', UserLoginView.as_view(), name='login'),
    path('create-employee/', CreateEmployeeView.as_view(), name='create-employee'),
    path('logout/', UserLogoutView.as_view(), name='logout'),
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),

]

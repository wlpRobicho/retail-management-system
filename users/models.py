# users/models.py

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

class UserManager(BaseUserManager):
    def create_user(self, userid, password=None, **extra_fields):
        if not userid:
            raise ValueError("The User ID must be set")
        user = self.model(userid=userid, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, userid, password=None, **extra_fields):
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_staff', True)
        return self.create_user(userid, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    POSITION_CHOICES = (
        ('manager', 'Manager'),
        ('employee', 'Employee'),
    )

    name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    userid = models.CharField(max_length=4, unique=True)
    position = models.CharField(max_length=10, choices=POSITION_CHOICES)
    is_active_now = models.BooleanField(default=False)
    last_login = models.DateTimeField(null=True, blank=True)
    last_logout = models.DateTimeField(null=True, blank=True)
    
    is_staff = models.BooleanField(default=False)  # Required for admin access
    is_active = models.BooleanField(default=True)  # Required for auth system

    USERNAME_FIELD = 'userid'
    REQUIRED_FIELDS = ['name', 'last_name', 'position']

    objects = UserManager()

    def __str__(self):
        return f"{self.name} ({self.position})"

class UserLog(models.Model):
    ACTION_CHOICES = (
        ('login', 'Login'),
        ('logout', 'Logout'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.name} - {self.action} at {self.timestamp}"

# users/models.py

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

class UserManager(BaseUserManager):
    # Custom manager for the User model to handle user creation
    def create_user(self, userid, password=None, **extra_fields):
        # Create and return a regular user
        if not userid:
            raise ValueError("The User ID must be set")
        user = self.model(userid=userid, **extra_fields)  # Create user instance
        user.set_password(password)  # Hash and set the password
        user.save(using=self._db)  # Save the user to the database
        return user

    def create_superuser(self, userid, password=None, **extra_fields):
        # Create and return a superuser with elevated permissions
        extra_fields.setdefault('is_superuser', True)  # Ensure superuser flag is set
        extra_fields.setdefault('is_staff', True)  # Ensure staff flag is set
        return self.create_user(userid, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    # Custom user model with additional fields and functionality
    POSITION_CHOICES = (
        ('manager', 'Manager'),
        ('employee', 'Employee'),
    )

    name = models.CharField(max_length=100)  # User's first name
    last_name = models.CharField(max_length=100)  # User's last name
    userid = models.CharField(max_length=4, unique=True)  # Unique user ID (4 digits)
    position = models.CharField(max_length=10, choices=POSITION_CHOICES)  # User's position (manager/employee)
    is_active_now = models.BooleanField(default=False)  # Indicates if the user is currently active
    last_login = models.DateTimeField(null=True, blank=True)  # Timestamp of the last login
    last_logout = models.DateTimeField(null=True, blank=True)  # Timestamp of the last logout

    is_staff = models.BooleanField(default=False)  # Required for admin access
    is_active = models.BooleanField(default=True)  # Required for authentication system

    USERNAME_FIELD = 'userid'  # Field used as the unique identifier for authentication
    REQUIRED_FIELDS = ['name', 'last_name', 'position']  # Required fields for creating a user

    objects = UserManager()  # Assign the custom manager to the model

    def __str__(self):
        # String representation of the user
        return f"{self.name} ({self.position})"

class UserLog(models.Model):
    # Model to log user actions (e.g., login, logout)
    ACTION_CHOICES = (
        ('login', 'Login'),  # User logged in
        ('logout', 'Logout'),  # User logged out
        ('failed_login', 'Failed Login'),  # Failed login attempt
        ('create_user', 'User Created'),  # New user created
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)  # Reference to the user
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)  # Action performed
    timestamp = models.DateTimeField(auto_now_add=True)  # Timestamp of the action

    def __str__(self):
        # String representation of the log entry
        return f"{self.user.name} - {self.action} at {self.timestamp}"

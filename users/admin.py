# users/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import path, reverse
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import User, UserLog
from .forms import UserAdminCreationForm
import random

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    # Custom admin interface for the User model
    change_form_template = "admin/users/change_form.html"  # Use a custom template for the change form
    add_form = UserAdminCreationForm  # Form used for adding users
    form = UserAdminCreationForm  # Form used for editing users

    # Fields to display in the admin list view
    list_display = (
        'userid', 'name', 'last_name', 'position',
        'is_active_now', 'last_login', 'last_logout'
    )
    search_fields = ('name', 'last_name', 'userid')  # Enable search by these fields
    list_filter = ('position', 'is_active_now')  # Filters for the list view
    readonly_fields = ('last_login', 'last_logout', 'is_active_now')  # Fields that cannot be edited
    ordering = ('userid',)  # Default ordering by userid

    # Fieldsets for organizing fields in the admin form
    fieldsets = (
        (None, {
            'fields': ('name', 'last_name', 'userid', 'position')
        }),
        ('Status', {
            'fields': ('is_active_now', 'last_login', 'last_logout')
        }),
        ('Permissions', {
            'fields': ('is_staff', 'is_active', 'is_superuser', 'groups', 'user_permissions'),
        }),
    )

    # Fieldsets used specifically for adding new users
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('name', 'last_name', 'userid', 'position'),
        }),
    )

    def get_fieldsets(self, request, obj=None):
        # Use add_fieldsets when creating a new user, otherwise use the default fieldsets
        if not obj:
            return self.add_fieldsets
        return super().get_fieldsets(request, obj)

    def response_add(self, request, obj, post_url_continue=None):
        # Display a success message with the generated password after adding a user
        generated_password = getattr(obj, '_plain_password', None)
        if generated_password:
            self.message_user(
                request,
                f"✅ User '{obj.userid}' created with password: {generated_password}",
                level=messages.SUCCESS
            )
        return super().response_add(request, obj, post_url_continue)

    def get_urls(self):
        # Add custom URLs for admin actions
        urls = super().get_urls()

        # Wrapper for CSRF-exempt JSON endpoint
        @csrf_exempt
        def wrapped_regen_password_view(request, object_id):
            return self.regenerate_password(request, object_id)

        custom_urls = [
            path(
                '<int:object_id>/regenerate-password/',
                wrapped_regen_password_view,  # Custom endpoint for regenerating passwords
                name='users_user_regenerate_password'
            ),
        ]
        return custom_urls + urls

    def regenerate_password(self, request, object_id):
        # Regenerate a user's password and return it as a JSON response
        if request.method == 'POST':
            user = get_object_or_404(User, pk=object_id)  # Ensure the user exists
            new_password = f"{random.randint(1000, 9999)}"  # Generate a random 4-digit password
            user.set_password(new_password)  # Set the new password
            user.save()  # Save the user with the updated password
            return JsonResponse({'userid': user.userid, 'password': new_password})  # Return the new password
        return JsonResponse({'error': 'Invalid request'}, status=400)  # Handle invalid requests

@admin.register(UserLog)
class UserLogAdmin(admin.ModelAdmin):
    # Custom admin interface for the UserLog model
    list_display = ('user', 'colored_action', 'timestamp')  # Fields to display in the list view
    list_filter = ('action', 'timestamp')  # Filters for the list view
    search_fields = ('user__name', 'user__userid')  # Enable search by user name or userid
    ordering = ('-timestamp',)  # Default ordering by timestamp (newest first)

    def colored_action(self, obj):
        # Display the action with a color-coded label
        color = {
            'login': 'green',
            'logout': 'blue',
            'failed_login': 'red',
            'create_user': 'orange'
        }.get(obj.action, 'gray')  # Default to gray if action is not recognized
        return format_html(f'<strong style="color:{color}">{obj.get_action_display()}</strong>')

    colored_action.short_description = "Action"  # Column header for the colored action

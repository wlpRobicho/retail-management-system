from django.contrib import admin
from .models import User, UserLog

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'last_name', 'userid', 'position',
        'is_active_now', 'last_login', 'last_logout'
    )
    search_fields = ('name', 'userid', 'position')
    list_filter = ('position', 'is_active_now')


@admin.register(UserLog)
class UserLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'timestamp')
    list_filter = ('action', 'timestamp')
    search_fields = ('user__name', 'user__userid')

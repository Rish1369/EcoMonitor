from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import ProjectUser

@admin.register(ProjectUser)
class ProjectUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'organization', 'phone', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('Project Info', {'fields': ('organization', 'phone')}),
    )

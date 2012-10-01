from django.contrib import admin

from parliament.accounts.models import *

class UserAdmin(admin.ModelAdmin):

	list_display = ['email', 'created', 'last_login']

admin.site.register(User, UserAdmin)
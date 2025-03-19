from django.contrib import admin

from accounts.models import User

admin.site.site_header = 'WIB Challenge Administration'


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    pass

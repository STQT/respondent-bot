from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.utils.translation import gettext_lazy as _

from .forms import UserAdminChangeForm
from .forms import UserAdminCreationForm
from .models import User, TGUser


@admin.register(User)
class UserAdmin(auth_admin.UserAdmin):
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (_("Personal info"), {"fields": ("name", "email")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    list_display = ["username", "name", "is_superuser"]
    search_fields = ["name"]


@admin.register(TGUser)
class TGUserAdmin(admin.ModelAdmin):
    list_display = ["id", "username", "fullname", "is_active", "blocked_bot", "last_activity"]
    list_filter = ["is_active", "blocked_bot", "last_activity"]
    search_fields = ["id", "username", "fullname"]
    readonly_fields = ["last_activity"]
    list_editable = ["is_active", "blocked_bot"]
    
    fieldsets = (
        (None, {
            'fields': ('id', 'username', 'fullname')
        }),
        ('Статус', {
            'fields': ('is_active', 'blocked_bot', 'last_activity')
        }),
    )
    
    actions = ['mark_as_active', 'mark_as_blocked', 'reset_block_status']
    
    def mark_as_active(self, request, queryset):
        """Пометить выбранных пользователей как активных"""
        updated = queryset.update(is_active=True, blocked_bot=False)
        self.message_user(request, f'{updated} пользователей помечено как активных.')
    mark_as_active.short_description = "Пометить как активных"
    
    def mark_as_blocked(self, request, queryset):
        """Пометить выбранных пользователей как заблокировавших бота"""
        updated = queryset.update(is_active=False, blocked_bot=True)
        self.message_user(request, f'{updated} пользователей помечено как заблокировавших бота.')
    mark_as_blocked.short_description = "Пометить как заблокировавших бота"
    
    def reset_block_status(self, request, queryset):
        """Сбросить статус блокировки для выбранных пользователей"""
        updated = queryset.update(blocked_bot=False, is_active=True)
        self.message_user(request, f'Статус блокировки сброшен для {updated} пользователей.')
    reset_block_status.short_description = "Сбросить статус блокировки"

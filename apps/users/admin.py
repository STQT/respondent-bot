from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from .forms import UserAdminChangeForm
from .forms import UserAdminCreationForm
from .models import User, TGUser, WithdrawalRequest, TransactionHistory


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
    list_display = ["id", "username", "fullname", "balance", "lang", "is_active", "blocked_bot", "last_activity"]
    list_filter = ["is_active", "blocked_bot", "lang", "last_activity"]
    search_fields = ["id", "username", "fullname"]
    readonly_fields = ["last_activity"]
    list_editable = ["is_active", "blocked_bot"]
    
    fieldsets = (
        (None, {
            'fields': ('id', 'username', 'fullname')
        }),
        ('Финансы', {
            'fields': ('balance',)
        }),
        ('Настройки', {
            'fields': ('lang',)
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


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount', 'status', 'created_at', 'processed_at', 'processed_by']
    list_filter = ['status', 'created_at', 'processed_at']
    search_fields = ['user__fullname', 'user__username', 'payment_details']
    readonly_fields = ['created_at', 'processed_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'amount', 'payment_details', 'status')
        }),
        ('Обработка', {
            'fields': ('processed_by', 'processed_at', 'admin_notes')
        }),
        ('Временные метки', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_withdrawal', 'reject_withdrawal', 'complete_withdrawal']
    
    def approve_withdrawal(self, request, queryset):
        """Одобрить запросы на вывод"""
        queryset = queryset.filter(status='pending')
        updated = queryset.update(
            status='approved',
            processed_by=request.user,
            processed_at=timezone.now()
        )
        self.message_user(request, f'Одобрено {updated} запросов на вывод.')
    approve_withdrawal.short_description = "Одобрить запросы"
    
    def reject_withdrawal(self, request, queryset):
        """Отклонить запросы на вывод"""
        queryset = queryset.filter(status__in=['pending', 'approved'])
        
        # Возвращаем деньги на баланс для отклоненных запросов
        for withdrawal in queryset:
            user = withdrawal.user
            user.balance += withdrawal.amount
            user.save()
            
            # Создаем транзакцию возврата
            TransactionHistory.objects.create(
                user=user,
                transaction_type='refund',
                amount=withdrawal.amount,
                description=f'Возврат отклоненного запроса на вывод #{withdrawal.id}',
                withdrawal_request=withdrawal
            )
        
        updated = queryset.update(
            status='rejected',
            processed_by=request.user,
            processed_at=timezone.now()
        )
        self.message_user(request, f'Отклонено {updated} запросов. Средства возвращены на баланс пользователей.')
    reject_withdrawal.short_description = "Отклонить запросы"
    
    def complete_withdrawal(self, request, queryset):
        """Завершить выполнение запросов на вывод"""
        queryset = queryset.filter(status='approved')
        
        # Списываем деньги и создаем транзакции
        for withdrawal in queryset:
            # Создаем транзакцию вывода
            TransactionHistory.objects.create(
                user=withdrawal.user,
                transaction_type='withdrawal',
                amount=-withdrawal.amount,  # отрицательная сумма для вывода
                description=f'Вывод средств #{withdrawal.id}',
                withdrawal_request=withdrawal
            )
        
        updated = queryset.update(
            status='completed',
            processed_by=request.user,
            processed_at=timezone.now()
        )
        self.message_user(request, f'Завершено {updated} выводов средств.')
    complete_withdrawal.short_description = "Завершить вывод"


@admin.register(TransactionHistory)
class TransactionHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'transaction_type', 'amount', 'related_poll', 'created_at']
    list_filter = ['transaction_type', 'created_at']
    search_fields = ['user__fullname', 'user__username', 'description']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'transaction_type', 'amount', 'description')
        }),
        ('Связанные объекты', {
            'fields': ('related_poll', 'withdrawal_request'),
            'classes': ('collapse',)
        }),
        ('Временные метки', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        return False  # Запрещаем ручное создание транзакций
    
    def has_change_permission(self, request, obj=None):
        return False  # Запрещаем редактирование транзакций

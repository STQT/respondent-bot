from django.contrib import admin

from apps.orders.models import OrderProduct, Order


class OrderProductInline(admin.TabularInline):
    model = OrderProduct
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderProductInline]
    list_display = ['customer_name', 'customer_phone',
                    'customer_address', 'total_sum', 'created_at', 'cash_type']

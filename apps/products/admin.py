from django.contrib import admin

from .models import Product, Category


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name_uz", "name_ru"]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name_uz", "name_ru"]

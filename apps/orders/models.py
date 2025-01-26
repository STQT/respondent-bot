from django.db import models

from django.utils.translation import gettext_lazy as _


class Order(models.Model):
    class CashTypeChoices(models.TextChoices):
        CASH = "cash", _("Наличные")
        CLICK = "click", _("ClickUZ")

    customer_name = models.CharField(verbose_name=_("Xaridor ismi"), max_length=255)
    customer_phone = models.CharField(verbose_name=_("Xaridor raqami"), max_length=20)
    customer_address = models.CharField(verbose_name=_("Xaridor manzili"), max_length=255, blank=True, null=True)
    cash_type = models.CharField(verbose_name=_("To'lov usuli"), max_length=255)
    total_sum = models.CharField(verbose_name=_("Umumiy summa"), max_length=10)
    created_at = models.DateTimeField(verbose_name=_("Yaratilgan vaqt"), auto_now_add=True)

    class Meta:
        verbose_name = _("Buyurtma")
        verbose_name_plural = _("Buyurtmalar")


class OrderProduct(models.Model):
    order = models.ForeignKey(Order, verbose_name=_("Buyurtma"), on_delete=models.CASCADE)
    product_name = models.CharField(verbose_name=_("Maxsulot nomi"), max_length=255)
    product_count = models.IntegerField(verbose_name=_("Maxsulot soni"), default=1)
    total_price = models.IntegerField(verbose_name=_("Umumiy narx"))

    class Meta:
        verbose_name = _("Buyurtma maxsuloti")
        verbose_name_plural = _("Buyurtma maxsulotlari")

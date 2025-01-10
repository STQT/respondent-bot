from django.db import models
from django.utils.translation import gettext_lazy as _


class Category(models.Model):
    name_uz = models.CharField(verbose_name=_("Nomi UZ"), max_length=100)
    name_ru = models.CharField(verbose_name=_("Nomi RU"), max_length=100, blank=True, null=True)

    class Meta:
        verbose_name = _("Kategoriya")
        verbose_name_plural = _("Kategoriyalar")

    def __str__(self):
        return self.name_uz


class Product(models.Model):
    category = models.ForeignKey(Category, verbose_name=_("Kategoriya"), on_delete=models.CASCADE,
                                 related_name='products')
    price = models.IntegerField(verbose_name=_("Narxi"))
    photo = models.ImageField(verbose_name=_("Rasmi"))
    name_uz = models.CharField(verbose_name=_("Nomi UZ"), max_length=100)
    name_ru = models.CharField(verbose_name=_("Nomi RU"), max_length=100, blank=True, null=True)
    photo_uri = models.CharField(verbose_name=_("Rasmi URI"), max_length=255, blank=True, null=True, editable=False)
    photo_updated = models.BooleanField(verbose_name=_("Rasm yangilandimi?"), default=False, editable=False)
    order_with_respect_to = "category"

    class Meta:
        verbose_name = _("Maxsulot")
        verbose_name_plural = _("Maxsulotlar")

    def __str__(self):
        return self.name_uz

    def save(self, *args, **kwargs):
        # Check if the photo field has changed
        if self.pk is not None:
            original_photo = Product.objects.get(pk=self.pk).photo
            if original_photo and original_photo != self.photo:
                self.photo_updated = True
        super(Product, self).save(*args, **kwargs)

from django.conf import settings

from apps.contrib.clickuz.clickuz import ClickUz
from apps.contrib.clickuz.views import ClickUzMerchantAPIView
from apps.orders.models import Order


class CheckOrder(ClickUz):
    def check_order(self, order_id: str, amount: str):
        return self.ORDER_FOUND

    def successfully_payment(self, order_id: str, transaction: object):
        print(order_id)


class ClickUzView(ClickUzMerchantAPIView):
    VALIDATE_CLASS = CheckOrder

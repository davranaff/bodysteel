from dataclasses import dataclass
from typing import Protocol

from payments.models import Payment


@dataclass(frozen=True)
class PaymentStart:
    provider: str
    payment_id: int
    checkout_url: str | None = None


class PaymentProvider(Protocol):
    name: str

    def create_payment(self, payment: Payment) -> PaymentStart:
        ...

    def query_status(self, payment: Payment) -> str:
        ...

    def verify_webhook(self, raw_body: bytes, signature: str) -> bool:
        ...


class ManualPaymentProvider:
    name = 'manual'

    def create_payment(self, payment):
        return PaymentStart(provider=self.name, payment_id=payment.pk)

    def query_status(self, payment):
        return payment.status

    def verify_webhook(self, raw_body, signature):
        return False


def provider_for(name):
    if name == ManualPaymentProvider.name:
        return ManualPaymentProvider()
    raise ValueError('Unsupported payment provider')

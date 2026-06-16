"""Payment provider integrations — real implementations go here.

Supported providers: Stripe, PayPal, WeChat Pay, Alipay.
Each provider class exposes a uniform interface so the app doesn't care
which one is used. To activate a provider, set the corresponding env vars.
"""

import os
import json
import hashlib
import time
from abc import ABC, abstractmethod


class PaymentProvider(ABC):
    """Base class for payment providers."""

    @abstractmethod
    def create_checkout(self, amount: float, currency: str, user_email: str, plan: str) -> dict:
        """Create a checkout session. Returns {'url': '...', 'session_id': '...'}."""
        ...

    @abstractmethod
    def verify_payment(self, session_id: str) -> dict:
        """Verify a payment. Returns {'success': bool, 'amount': float, 'provider_payment_id': str}."""
        ...

    @abstractmethod
    def name(self) -> str:
        ...


class StripeProvider(PaymentProvider):
    """Stripe payment integration.

    To activate: set STRIPE_SECRET_KEY and STRIPE_PRICE_IDS env vars.
    STRIPE_PRICE_IDS: JSON like {"pro": "price_xxx", "enterprise": "price_yyy"}
    """

    def __init__(self):
        self.secret_key = os.getenv("STRIPE_SECRET_KEY", "")
        self.price_ids = json.loads(os.getenv("STRIPE_PRICE_IDS", "{}"))
        self._active = bool(self.secret_key)

    def name(self) -> str:
        return "stripe"

    def is_active(self) -> bool:
        return self._active

    def create_checkout(self, amount: float, currency: str, user_email: str, plan: str) -> dict:
        if not self._active:
            session_id = f"cs_demo_{hashlib.sha256(f'{user_email}{time.time()}'.encode()).hexdigest()[:16]}"
            return {
                "url": f"/demo-payment?session={session_id}&plan={plan}&amount={amount}",
                "session_id": session_id,
                "mode": "demo",
            }

        import stripe
        stripe.api_key = self.secret_key

        # Use price ID from config, or create a dynamic line item
        price_id = self.price_ids.get(plan)
        if price_id:
            line_items = [{"price": price_id, "quantity": 1}]
        else:
            # Dynamic pricing — create a one-time price on the fly
            line_items = [{
                "price_data": {
                    "currency": currency.lower(),
                    "product_data": {"name": f"Lighthouse Analytics — {plan.upper()} Plan"},
                    "unit_amount": int(amount * 100),  # Stripe uses cents
                    "recurring": {"interval": "month"},
                },
                "quantity": 1,
            }]

        base_url = os.getenv("BASE_URL", "http://localhost:5001")
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="subscription",
            success_url=f"{base_url}/dashboard?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base_url}/pricing",
            customer_email=user_email,
            metadata={"plan": plan, "user_email": user_email},
        )
        return {"url": session.url, "session_id": session.id, "mode": "live"}


    def verify_payment(self, session_id: str) -> dict:
        if session_id.startswith("cs_demo_"):
            return {"success": True, "amount": 29.0, "provider_payment_id": f"pi_demo_{session_id}"}

        import stripe
        stripe.api_key = self.secret_key
        session = stripe.checkout.Session.retrieve(session_id)

        if session.payment_status == "paid":
            return {
                "success": True,
                "amount": session.amount_total / 100,
                "provider_payment_id": session.payment_intent,
                "customer_id": session.customer,
            }
        return {"success": False, "status": session.payment_status}


class PayPalProvider(PaymentProvider):
    """PayPal payment integration.

    To activate: set PAYPAL_CLIENT_ID and PAYPAL_SECRET env vars.
    """

    def __init__(self):
        self.client_id = os.getenv("PAYPAL_CLIENT_ID", "")
        self.secret = os.getenv("PAYPAL_SECRET", "")
        self._active = bool(self.client_id and self.secret)

    def name(self) -> str:
        return "paypal"

    def is_active(self) -> bool:
        return self._active

    def create_checkout(self, amount: float, currency: str, user_email: str, plan: str) -> dict:
        if not self._active:
            session_id = f"pp_demo_{hashlib.sha256(f'{user_email}{time.time()}'.encode()).hexdigest()[:16]}"
            return {
                "url": f"/demo-payment?session={session_id}&plan={plan}&amount={amount}",
                "session_id": session_id,
                "mode": "demo",
            }
        # Real PayPal integration uses Orders API
        raise NotImplementedError("PayPal is not configured.")


    def verify_payment(self, session_id: str) -> dict:
        if session_id.startswith("pp_demo_"):
            return {"success": True, "amount": 29.0, "provider_payment_id": f"pp_pi_demo_{session_id}"}
        raise NotImplementedError("PayPal is not configured.")


class WeChatPayProvider(PaymentProvider):
    """WeChat Pay integration.

    To activate: set WECHAT_APP_ID, WECHAT_MCH_ID, WECHAT_API_KEY env vars.
    """

    def __init__(self):
        self.app_id = os.getenv("WECHAT_APP_ID", "")
        self.mch_id = os.getenv("WECHAT_MCH_ID", "")
        self.api_key = os.getenv("WECHAT_API_KEY", "")
        self._active = bool(self.app_id and self.mch_id and self.api_key)

    def name(self) -> str:
        return "wechat_pay"

    def is_active(self) -> bool:
        return self._active

    def create_checkout(self, amount: float, currency: str, user_email: str, plan: str) -> dict:
        if not self._active:
            session_id = f"wx_demo_{hashlib.sha256(f'{user_email}{time.time()}'.encode()).hexdigest()[:16]}"
            return {
                "url": f"/demo-payment?session={session_id}&plan={plan}&amount={amount}",
                "session_id": session_id,
                "qr_url": f"/demo-qrcode?session={session_id}",
                "mode": "demo",
            }
        # Real WeChat Pay: Native支付 / JSAPI 支付
        raise NotImplementedError("WeChat Pay is not configured.")


    def verify_payment(self, session_id: str) -> dict:
        if session_id.startswith("wx_demo_"):
            return {"success": True, "amount": 29.0, "provider_payment_id": f"wx_pi_demo_{session_id}"}
        raise NotImplementedError("WeChat Pay is not configured.")


class AlipayProvider(PaymentProvider):
    """Alipay integration.

    To activate: set ALIPAY_APP_ID, ALIPAY_PRIVATE_KEY, ALIPAY_PUBLIC_KEY env vars.
    """

    def __init__(self):
        self.app_id = os.getenv("ALIPAY_APP_ID", "")
        self._active = bool(self.app_id)

    def name(self) -> str:
        return "alipay"

    def is_active(self) -> bool:
        return self._active

    def create_checkout(self, amount: float, currency: str, user_email: str, plan: str) -> dict:
        if not self._active:
            session_id = f"ali_demo_{hashlib.sha256(f'{user_email}{time.time()}'.encode()).hexdigest()[:16]}"
            return {
                "url": f"/demo-payment?session={session_id}&plan={plan}&amount={amount}",
                "session_id": session_id,
                "qr_url": f"/demo-qrcode?session={session_id}",
                "mode": "demo",
            }
        raise NotImplementedError("Alipay is not configured.")


    def verify_payment(self, session_id: str) -> dict:
        if session_id.startswith("ali_demo_"):
            return {"success": True, "amount": 29.0, "provider_payment_id": f"ali_pi_demo_{session_id}"}
        raise NotImplementedError("Alipay is not configured.")


# ── Provider Registry ──────────────────────────────────────────

_providers = {}


def get_providers() -> dict[str, PaymentProvider]:
    """Get all registered payment providers."""
    global _providers
    if not _providers:
        _providers = {
            "stripe": StripeProvider(),
            "paypal": PayPalProvider(),
            "wechat_pay": WeChatPayProvider(),
            "alipay": AlipayProvider(),
        }
    return _providers


def get_active_providers() -> list[PaymentProvider]:
    """Get providers that are actually configured or in demo mode."""
    providers = get_providers()
    return [p for p in providers.values() if p.is_active()]


def get_provider(name: str) -> PaymentProvider | None:
    """Get a specific provider by name."""
    return get_providers().get(name)


def any_provider_available() -> bool:
    """Check if any real payment provider is configured."""
    return any(p.is_active() for p in get_providers().values())

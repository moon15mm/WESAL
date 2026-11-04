"""External delivery channels (email, SMS, WhatsApp, Web Push).

Each provider implements ``send(target, subject, body, payload) -> provider_ref``.
Providers that need credentials raise ``IntegrationUnavailable`` when not configured.
`memory` providers are used by automated tests; `console` providers log messages in
development. Real-provider adapters (SMTP, Unifonic, Twilio, Meta WhatsApp Cloud,
Web Push/VAPID) are implemented against their public HTTP APIs but have NOT been
exercised against live accounts in this repository – see DEPLOYMENT.md.
"""
from __future__ import annotations

import json
import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Protocol

import httpx

from app.core.config import settings
from app.core.errors import IntegrationUnavailable

log = logging.getLogger("wesal.channels")

OUTBOX: list[dict] = []  # memory providers write here (tests)


class Provider(Protocol):
    def send(self, target: str, subject: str, body: str, payload: dict) -> str | None: ...


class MemoryProvider:
    def __init__(self, channel: str):
        self.channel = channel

    def send(self, target, subject, body, payload):
        OUTBOX.append({"channel": self.channel, "target": target, "subject": subject, "body": body, "payload": payload})
        return f"mem-{len(OUTBOX)}"


class ConsoleProvider:
    def __init__(self, channel: str):
        self.channel = channel

    def send(self, target, subject, body, payload):
        # Development only. Codes are printed so a developer can complete flows locally.
        log.warning("[%s → %s] %s | %s", self.channel, target, subject, body)
        OUTBOX.append({"channel": self.channel, "target": target, "subject": subject, "body": body, "payload": payload})
        return "console"


class SMTPProvider:
    def send(self, target, subject, body, payload):
        if not settings.smtp_host:
            raise IntegrationUnavailable("email_not_configured")
        msg = EmailMessage()
        msg["From"] = settings.smtp_from
        msg["To"] = target
        msg["Subject"] = subject
        msg.set_content(body)
        if payload.get("html"):
            msg.add_alternative(payload["html"], subtype="html")
        ctx = ssl.create_default_context()
        if settings.smtp_port == 465:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=ctx, timeout=20) as s:
                if settings.smtp_user:
                    s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as s:
                if settings.smtp_starttls:
                    s.starttls(context=ctx)
                if settings.smtp_user:
                    s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg)
        return "smtp"


class UnifonicSMSProvider:
    URL = "https://el.cloud.unifonic.com/rest/SMS/messages"

    def send(self, target, subject, body, payload):
        if not settings.unifonic_app_sid:
            raise IntegrationUnavailable("sms_not_configured")
        r = httpx.post(self.URL, data={"AppSid": settings.unifonic_app_sid, "SenderID": settings.sms_sender,
                                       "Recipient": target.lstrip("+"), "Body": body}, timeout=15)
        r.raise_for_status()
        data = r.json()
        if not data.get("success", False):
            raise RuntimeError(f"unifonic error: {data.get('message')}")
        return str(data.get("data", {}).get("MessageID", ""))


class TwilioSMSProvider:
    def send(self, target, subject, body, payload):
        if not (settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from):
            raise IntegrationUnavailable("sms_not_configured")
        url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
        r = httpx.post(url, data={"To": target, "From": settings.twilio_from, "Body": body},
                       auth=(settings.twilio_account_sid, settings.twilio_auth_token), timeout=15)
        r.raise_for_status()
        return r.json().get("sid")


class MetaWhatsAppProvider:
    """WhatsApp Business Cloud API. Business-initiated messages require pre-approved templates."""

    def send(self, target, subject, body, payload):
        if not (settings.whatsapp_token and settings.whatsapp_phone_number_id):
            raise IntegrationUnavailable("whatsapp_not_configured")
        url = f"https://graph.facebook.com/v21.0/{settings.whatsapp_phone_number_id}/messages"
        template = payload.get("whatsapp_template")
        if template:
            message = {"messaging_product": "whatsapp", "to": target.lstrip("+"), "type": "template",
                       "template": {"name": template, "language": {"code": payload.get("locale", "ar")},
                                    "components": [{"type": "body", "parameters": [
                                        {"type": "text", "text": str(p)} for p in payload.get("template_params", [])]}]}}
        else:
            message = {"messaging_product": "whatsapp", "to": target.lstrip("+"), "type": "text", "text": {"body": body}}
        r = httpx.post(url, json=message, headers={"Authorization": f"Bearer {settings.whatsapp_token}"}, timeout=15)
        r.raise_for_status()
        return (r.json().get("messages") or [{}])[0].get("id")


class WebPushProvider:
    def send(self, target, subject, body, payload):
        if not (settings.vapid_private_key and settings.vapid_public_key):
            raise IntegrationUnavailable("push_not_configured")
        try:
            from pywebpush import webpush  # optional dependency
        except ImportError:  # pragma: no cover
            raise IntegrationUnavailable("push_library_missing")
        sub = json.loads(target)
        webpush(subscription_info=sub, data=json.dumps({"title": subject, "body": body, "link": payload.get("link")}),
                vapid_private_key=settings.vapid_private_key, vapid_claims={"sub": settings.vapid_subject})
        return "webpush"


def provider_for(channel: str) -> Provider | None:
    if channel == "email":
        return {"smtp": SMTPProvider(), "console": ConsoleProvider("email"), "memory": MemoryProvider("email")}[settings.email_backend]
    if channel == "sms":
        return {"none": None, "console": ConsoleProvider("sms"), "memory": MemoryProvider("sms"),
                "unifonic": UnifonicSMSProvider(), "twilio": TwilioSMSProvider()}[settings.sms_provider]
    if channel == "whatsapp":
        return {"none": None, "memory": MemoryProvider("whatsapp"), "meta_cloud": MetaWhatsAppProvider()}[settings.whatsapp_provider]
    if channel == "push":
        return {"none": None, "memory": MemoryProvider("push"), "webpush": WebPushProvider()}[settings.push_provider]
    return None


def channel_enabled(channel: str) -> bool:
    return provider_for(channel) is not None

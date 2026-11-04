"""Provider adapters tested with isolated mocks (no network, no real credentials).

These prove request shapes, error handling and fallbacks. They do NOT prove that the real providers
(Anthropic, Unifonic, Twilio, Meta WhatsApp, an SMTP server) accept these requests — that needs live
credentials and is listed as an open item in PROJECT_STATUS.md."""
from types import SimpleNamespace

import httpx
import pytest

from app.core.config import settings
from app.core.errors import IntegrationUnavailable


# ------------------------------------------------------------------ Claude adapter
def _text(t):
    return SimpleNamespace(type="text", text=t)


def _tool_use(i, name, args):
    return SimpleNamespace(type="tool_use", id=i, name=name, input=args)


class FakeMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def fake_client(responses):
    msgs = FakeMessages(responses)
    return SimpleNamespace(beta=SimpleNamespace(messages=msgs)), msgs


def test_claude_tool_loop_uses_only_scoped_tools():
    from app.integrations.ai_anthropic import ClaudeAssistant, tool

    client, msgs = fake_client([
        SimpleNamespace(stop_reason="tool_use", content=[_text("checking"), _tool_use("t1", "my_orders_summary", {})]),
        SimpleNamespace(stop_reason="end_turn", content=[_text("لديك طلبان بانتظار موافقتك.")]),
    ])
    executed = []

    def executor(name, args):
        executed.append(name)
        return {"pending": 2}

    tools = [tool("my_orders_summary", "Summary of my orders")]
    res = ClaudeAssistant(client=client).ask("كم طلب بانتظاري؟", "ar", tools, executor)
    assert res["answer"] == "لديك طلبان بانتظار موافقتك." and res["tools_used"] == ["my_orders_summary"]
    assert executed == ["my_orders_summary"]
    first = msgs.calls[0]
    assert first["model"] == settings.ai_model and first["tools"] == tools
    assert first["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in first["betas"]
    assert "Never invent prices" in first["system"] and "(ar)" in first["system"]
    # the tool result is sent back as a user turn referencing the tool_use id
    second = msgs.calls[1]["messages"]
    assert second[-1]["role"] == "user" and second[-1]["content"][0]["tool_use_id"] == "t1"
    assert tools[0]["strict"] is True and tools[0]["input_schema"]["additionalProperties"] is False


def test_claude_refusal_and_tool_errors_are_handled():
    from app.integrations.ai_anthropic import ClaudeAssistant

    client, _ = fake_client([SimpleNamespace(stop_reason="refusal", content=[])])
    assert ClaudeAssistant(client=client).ask("x", "en", [], lambda n, a: {})["refused"] is True

    client, msgs = fake_client([
        SimpleNamespace(stop_reason="tool_use", content=[_tool_use("t9", "boom", {})]),
        SimpleNamespace(stop_reason="end_turn", content=[_text("I could not get that data.")]),
    ])

    def executor(name, args):
        raise ValueError("not allowed")

    res = ClaudeAssistant(client=client).ask("x", "en", [], executor)
    assert res["answer"] == "I could not get that data."
    assert msgs.calls[1]["messages"][-1]["content"][0]["is_error"] is True


def test_claude_api_errors_map_to_integration_unavailable():
    import anthropic

    from app.integrations.ai_anthropic import ClaudeAssistant

    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    for exc, code in [
        (anthropic.RateLimitError("slow down", response=httpx.Response(429, request=req), body=None), "ai_rate_limited"),
        (anthropic.AuthenticationError("bad key", response=httpx.Response(401, request=req), body=None), "ai_not_configured"),
        (anthropic.InternalServerError("oops", response=httpx.Response(500, request=req), body=None), "ai_provider_error"),
        (anthropic.APIConnectionError(request=req), "ai_provider_unreachable"),
    ]:
        client, _ = fake_client([exc])
        with pytest.raises(IntegrationUnavailable) as e:
            ClaudeAssistant(client=client).ask("x", "en", [], lambda n, a: {})
        assert e.value.code == code


def test_ask_endpoint_falls_back_to_local_engine_when_claude_fails(monkeypatch):
    from app.integrations import ai_anthropic
    from tests.conftest import register

    class Broken:
        def ask(self, *a, **k):
            raise IntegrationUnavailable("ai_provider_unreachable")

    monkeypatch.setattr(settings, "ai_provider", "anthropic")
    monkeypatch.setattr(ai_anthropic, "ClaudeAssistant", lambda: Broken())
    store = register("retailer")
    r = store.post("/ai/ask", {"question": "كم مشترياتي هذا الشهر؟"})
    assert r.status_code == 200, r.text
    assert r.json()["provider"] == "local"


def test_claude_requires_api_key(monkeypatch):
    from app.integrations.ai_anthropic import ClaudeAssistant

    monkeypatch.setattr(settings, "anthropic_api_key", "")
    with pytest.raises(IntegrationUnavailable):
        ClaudeAssistant()


# ------------------------------------------------------------------ messaging channels
class Recorder:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def __call__(self, url, **kw):
        self.calls.append((url, kw))
        return httpx.Response(self.response[0], json=self.response[1], request=httpx.Request("POST", url))


def test_unifonic_sms_request_and_errors(monkeypatch):
    from app.integrations import channels

    monkeypatch.setattr(settings, "unifonic_app_sid", "APPSID")
    rec = Recorder((200, {"success": True, "data": {"MessageID": 42}}))
    monkeypatch.setattr(channels.httpx, "post", rec)
    assert channels.UnifonicSMSProvider().send("+966500000001", "", "رمز التحقق 123456", {}) == "42"
    url, kw = rec.calls[0]
    assert url.startswith("https://") and kw["data"]["Recipient"] == "966500000001" and kw["data"]["AppSid"] == "APPSID"
    monkeypatch.setattr(channels.httpx, "post", Recorder((200, {"success": False, "message": "insufficient balance"})))
    with pytest.raises(RuntimeError):
        channels.UnifonicSMSProvider().send("+966500000001", "", "x", {})
    monkeypatch.setattr(settings, "unifonic_app_sid", "")
    with pytest.raises(IntegrationUnavailable):
        channels.UnifonicSMSProvider().send("+966500000001", "", "x", {})


def test_twilio_sms_request(monkeypatch):
    from app.integrations import channels

    monkeypatch.setattr(settings, "twilio_account_sid", "AC123")
    monkeypatch.setattr(settings, "twilio_auth_token", "tok")
    monkeypatch.setattr(settings, "twilio_from", "+15550001")
    rec = Recorder((201, {"sid": "SM1"}))
    monkeypatch.setattr(channels.httpx, "post", rec)
    assert channels.TwilioSMSProvider().send("+966500000002", "", "hello", {}) == "SM1"
    url, kw = rec.calls[0]
    assert "/Accounts/AC123/Messages.json" in url and kw["auth"] == ("AC123", "tok") and kw["data"]["To"] == "+966500000002"
    monkeypatch.setattr(channels.httpx, "post", Recorder((401, {"message": "auth"})))
    with pytest.raises(httpx.HTTPStatusError):
        channels.TwilioSMSProvider().send("+966500000002", "", "hello", {})


def test_whatsapp_template_and_text_messages(monkeypatch):
    from app.integrations import channels

    monkeypatch.setattr(settings, "whatsapp_token", "WATOKEN")
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", "PNID")
    rec = Recorder((200, {"messages": [{"id": "wamid.1"}]}))
    monkeypatch.setattr(channels.httpx, "post", rec)
    out = channels.MetaWhatsAppProvider().send("+966500000003", "", "", {"whatsapp_template": "order_approved", "locale": "ar",
                                                                         "template_params": ["WSL-1", "120.00"]})
    assert out == "wamid.1"
    url, kw = rec.calls[0]
    assert url.endswith("/PNID/messages") and kw["headers"]["Authorization"] == "Bearer WATOKEN"
    body = kw["json"]
    assert body["type"] == "template" and body["template"]["language"]["code"] == "ar"
    assert [p["text"] for p in body["template"]["components"][0]["parameters"]] == ["WSL-1", "120.00"]
    channels.MetaWhatsAppProvider().send("+966500000003", "", "plain", {})
    assert rec.calls[1][1]["json"]["text"]["body"] == "plain"


def test_smtp_starttls_login_and_send(monkeypatch):
    from app.integrations import channels

    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            sent["host"] = (host, port)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self, context):
            sent["tls"] = True

        def login(self, u, p):
            sent["login"] = u

        def send_message(self, msg):
            sent["msg"] = msg

    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_user", "mailer")
    monkeypatch.setattr(settings, "smtp_starttls", True)
    monkeypatch.setattr(channels.smtplib, "SMTP", FakeSMTP)
    channels.SMTPProvider().send("user@example.com", "تأكيد الطلب", "نص", {"html": "<p>نص</p>"})
    assert sent["host"] == ("smtp.example.com", 587) and sent["tls"] and sent["login"] == "mailer"
    assert sent["msg"]["Subject"] == "تأكيد الطلب" and sent["msg"].is_multipart()

"""Provider tests against a fake OpenAI client: no network."""
from types import SimpleNamespace

import httpx2 as httpx  # openai 3.x ships httpx2
import openai
import pytest

from zenai.providers import JSONParseError, Provider, QuotaError, extract_json

CFG = {"provider": {
    "name": "test", "base_url": "https://example.test", "chat_model": "chat-m", "embed_model": "embed-m",
    "api_key_env": "UNUSED", "temperature": 0, "reasoning_effort": "minimal", "embed_batch_size": 64,
    "chat_requests_per_minute": 1000, "chat_requests_per_day": 1000,
    "embed_requests_per_minute": 1000, "embed_requests_per_day": 1000,
}}


def api_error(cls, status, message, headers=None):
    request = httpx.Request("POST", "https://example.test")
    return cls(message, response=httpx.Response(status, request=request, headers=headers or {}), body=None)


def chat_reply(content):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class FakeClient:
    """Mimics openai.OpenAI: chat.completions.create and embeddings.create."""

    def __init__(self, chat=None, embed=None):
        self.chat_calls, self.embed_calls = [], []
        self._chat = chat or (lambda kw: chat_reply('{"ok": true}'))
        self._embed = embed or (lambda kw: SimpleNamespace(
            data=[SimpleNamespace(index=i, embedding=[float(len(t)), 1.0]) for i, t in enumerate(kw["input"])]))
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._chat_create))
        self.embeddings = SimpleNamespace(create=self._embed_create)

    def _chat_create(self, **kw):
        self.chat_calls.append(kw)
        return self._chat(kw)

    def _embed_create(self, **kw):
        self.embed_calls.append(kw)
        return self._embed(kw)


@pytest.fixture
def make(tmp_path):
    sleeps = []

    def _make(client, cfg=CFG):
        return Provider(cfg, cache_dir=tmp_path, client=client, sleep=sleeps.append), sleeps
    return _make


MSGS = [{"role": "user", "content": "the printer in block Z is jammed"}]


def test_chat_cache_hit_makes_no_network_call(make):
    client = FakeClient()
    p, _ = make(client)
    assert p.chat_json(MSGS) == {"ok": True}
    assert p.chat_json(MSGS) == {"ok": True}
    assert len(client.chat_calls) == 1
    assert p.stats() == {"calls_made": 1, "cache_hits": 1}


def test_cache_survives_new_provider_instance(make):
    make(FakeClient())[0].chat_json(MSGS)
    client = FakeClient()
    p, _ = make(client)
    p.chat_json(MSGS)
    assert client.chat_calls == [] and p.cache_hits == 1


def test_different_messages_miss_cache(make):
    client = FakeClient()
    p, _ = make(client)
    p.chat_json(MSGS)
    p.chat_json([{"role": "user", "content": "something else entirely"}])
    assert len(client.chat_calls) == 2


def test_sends_json_mode_and_reasoning_effort(make):
    client = FakeClient()
    p, _ = make(client)
    p.chat_json(MSGS)
    sent = client.chat_calls[0]
    assert sent["response_format"] == {"type": "json_object"}
    assert sent["reasoning_effort"] == "minimal"
    assert sent["temperature"] == 0


def test_json_mode_rejected_falls_back_to_prompt_instruction(make):
    def chat(kw):
        if "response_format" in kw:
            raise api_error(openai.BadRequestError, 400, "response_format json_object is not supported")
        return chat_reply('Sure! ```json\n{"topics": []}\n``` hope that helps')
    client = FakeClient(chat=chat)
    p, _ = make(client)
    assert p.chat_json(MSGS) == {"topics": []}
    assert "response_format" not in client.chat_calls[-1]
    assert "JSON" in client.chat_calls[-1]["messages"][0]["content"]
    assert p.metadata()["json_mode"] == "prompt_instruction"


def test_reasoning_effort_rejected_is_dropped_and_recorded(make):
    def chat(kw):
        if "reasoning_effort" in kw:
            raise api_error(openai.BadRequestError, 400, "reasoning_effort minimal is not supported")
        return chat_reply('{"ok": 1}')
    p, _ = make(FakeClient(chat=chat))
    assert p.chat_json(MSGS) == {"ok": 1}
    assert p.metadata()["reasoning_effort_sent"] is None
    assert p.metadata()["reasoning_effort_requested"] == "minimal"


def test_unparseable_reply_raises_with_raw_text(make):
    p, _ = make(FakeClient(chat=lambda kw: chat_reply("I cannot help with that")))
    with pytest.raises(JSONParseError) as exc:
        p.chat_json(MSGS)
    assert exc.value.raw == "I cannot help with that"


def test_extract_json_first_object():
    assert extract_json('noise {"a": {"b": 1}} {"c": 2}') == {"a": {"b": 1}}
    assert extract_json('{bad} then {"ok": true}') == {"ok": True}


def test_429_backs_off_honouring_retry_after(make):
    replies = [api_error(openai.RateLimitError, 429, "slow down", {"retry-after": "7"}), chat_reply('{"ok": 1}')]

    def chat(kw):
        r = replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    p, sleeps = make(FakeClient(chat=chat))
    assert p.chat_json(MSGS) == {"ok": 1}
    assert sleeps == [7.0]


def test_5xx_exhausts_retries_then_raises_quota_error(make):
    def chat(kw):
        raise api_error(openai.InternalServerError, 503, "overloaded")
    client = FakeClient(chat=chat)
    p, sleeps = make(client)
    with pytest.raises(QuotaError, match="probably hit"):
        p.chat_json(MSGS)
    assert len(client.chat_calls) == 5
    assert sleeps == [2.0, 4.0, 8.0, 16.0]


def test_per_day_quota_error_stops_immediately(make):
    def chat(kw):
        raise api_error(openai.RateLimitError, 429, "quota GenerateRequestsPerDayPerProjectPerModel exceeded")
    client = FakeClient(chat=chat)
    p, _ = make(client)
    with pytest.raises(QuotaError):
        p.chat_json(MSGS)
    assert len(client.chat_calls) == 1


def test_local_daily_cap_blocks_before_network(make):
    cfg = {"provider": {**CFG["provider"], "chat_requests_per_day": 1}}
    client = FakeClient()
    p, _ = make(client, cfg)
    p.chat_json(MSGS)
    with pytest.raises(QuotaError, match="daily chat cap"):
        p.chat_json([{"role": "user", "content": "a new question"}])
    assert len(client.chat_calls) == 1


def test_embed_batches_and_caches_per_text(make):
    client = FakeClient()
    p, _ = make(client)
    texts = [f"text number {i}" for i in range(130)]
    vecs = p.embed(texts)
    assert [len(c["input"]) for c in client.embed_calls] == [64, 64, 2]
    assert vecs[5] == [float(len(texts[5])), 1.0]

    client.embed_calls.clear()
    assert p.embed(texts[:10] + ["one brand new text"]) == vecs[:10] + [[18.0, 1.0]]
    assert [c["input"] for c in client.embed_calls] == [["one brand new text"]]


def test_embed_missing_index_means_zero(make):
    # Gemini returns index=None for the first item; items may also arrive out of order.
    def embed(kw):
        return SimpleNamespace(data=[SimpleNamespace(index=1, embedding=[2.0]),
                                     SimpleNamespace(index=None, embedding=[1.0])])
    p, _ = make(FakeClient(embed=embed))
    assert p.embed(["first", "second"]) == [[1.0], [2.0]]


def test_embed_duplicate_texts_sent_once(make):
    client = FakeClient()
    p, _ = make(client)
    out = p.embed(["same", "same", "other"])
    assert client.embed_calls[0]["input"] == ["same", "other"]
    assert out[0] == out[1]

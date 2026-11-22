"""Azure provider selection, chat_text, embedding-size checks and the FakeProvider extensions: no network."""
from types import SimpleNamespace

import openai
import pytest

from tests.test_providers import FakeClient, chat_reply
from zenai.config import load_config
from zenai.providers import FakeProvider, Provider, ProviderError, make_provider, resolve_provider_cfg

GEMINI = {"name": "gemini", "base_url": "https://example.test", "chat_model": "g-chat", "embed_model": "g-embed",
          "api_key_env": "GEMINI_TEST_KEY", "temperature": 0, "reasoning_effort": "minimal",
          "chat_requests_per_minute": 1000, "embed_requests_per_minute": 1000}
AZURE = {"endpoint_env": "AZURE_TEST_ENDPOINT", "api_key_env": "AZURE_TEST_KEY", "api_version": "2024-10-21",
         "chat_model": "chat-deploy", "embed_model": "embed-deploy", "embed_dim": 4, "temperature": 0,
         "reasoning_effort": None, "chat_requests_per_minute": 1000, "chat_requests_per_day": None,
         "embed_requests_per_minute": 1000, "embed_requests_per_day": None}
CFG = {"provider": GEMINI, "providers": {"azure": AZURE}}


def embed_client(dim):
    return FakeClient(embed=lambda kw: SimpleNamespace(
        data=[SimpleNamespace(index=i, embedding=[0.5] * dim) for i, _ in enumerate(kw["input"])]))


# ---- choosing the provider ----

def test_default_provider_is_config_yaml_provider():
    assert resolve_provider_cfg(CFG, env={}) is GEMINI
    assert resolve_provider_cfg(CFG, env={"LLM_PROVIDER": "gemini"}) is GEMINI
    assert resolve_provider_cfg(CFG, env={"LLM_PROVIDER": " "}) is GEMINI


def test_llm_provider_env_selects_azure_and_deployment_names_can_be_overridden():
    p = resolve_provider_cfg(CFG, env={"LLM_PROVIDER": "Azure"})
    assert p["name"] == "azure" and (p["chat_model"], p["embed_model"]) == ("chat-deploy", "embed-deploy")
    p = resolve_provider_cfg(CFG, env={"LLM_PROVIDER": "azure", "AZURE_CHAT_DEPLOYMENT": "c2",
                                       "AZURE_EMBED_DEPLOYMENT": "e2"})
    assert (p["chat_model"], p["embed_model"]) == ("c2", "e2")
    assert AZURE["chat_model"] == "chat-deploy"  # the config itself is not modified


def test_unknown_provider_is_refused():
    with pytest.raises(ProviderError, match="LLM_PROVIDER='openai'"):
        resolve_provider_cfg(CFG, env={"LLM_PROVIDER": "openai"})


def test_cfg_without_providers_section_ignores_the_env_override():
    assert resolve_provider_cfg({"provider": GEMINI}, env={"LLM_PROVIDER": "azure"}) is GEMINI


def test_real_config_has_gemini_default_and_azure_ready():
    cfg = load_config()
    assert cfg["provider"]["name"] == "gemini"
    azure = resolve_provider_cfg(cfg, env={"LLM_PROVIDER": "azure"})
    assert azure["embed_dim"] == 1536 and azure["api_version"] == "2024-10-21"
    assert azure["chat_model"] == "gpt-4.1-mini" and azure["embed_model"] == "embed"


def test_azure_client_is_built_from_env_with_pinned_api_version(monkeypatch, tmp_path):
    seen = {}

    class FakeAzure:
        def __init__(self, **kw):
            seen.update(kw)

    monkeypatch.setattr(openai, "AzureOpenAI", FakeAzure)
    monkeypatch.setenv("LLM_PROVIDER", "azure")
    monkeypatch.setenv("AZURE_TEST_ENDPOINT", "https://example.openai.azure.test/")
    monkeypatch.setenv("AZURE_TEST_KEY", "k-secret")
    p = Provider(CFG, cache_dir=tmp_path)
    assert seen == {"azure_endpoint": "https://example.openai.azure.test/", "api_key": "k-secret",
                    "api_version": "2024-10-21", "max_retries": 0}
    assert p.name == "azure" and p.chat_model == "chat-deploy" and p.embed_dim == 4 and not p.effort_active


def test_azure_without_endpoint_or_key_says_which_variable(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_PROVIDER", "azure")
    monkeypatch.delenv("AZURE_TEST_ENDPOINT", raising=False)
    monkeypatch.setenv("AZURE_TEST_KEY", "k")
    with pytest.raises(ProviderError, match="AZURE_TEST_ENDPOINT is not set"):
        Provider(CFG, cache_dir=tmp_path)
    monkeypatch.setenv("AZURE_TEST_ENDPOINT", "https://example.test/")
    monkeypatch.delenv("AZURE_TEST_KEY", raising=False)
    with pytest.raises(ProviderError, match="AZURE_TEST_KEY is not set"):
        Provider(CFG, cache_dir=tmp_path)


def test_azure_requests_use_deployment_names_and_no_reasoning_effort(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_PROVIDER", "azure")
    client = FakeClient(embed=embed_client(4)._embed)
    p = Provider(CFG, cache_dir=tmp_path, client=client)
    p.chat_json([{"role": "user", "content": "hi"}])
    p.embed(["a"])
    assert client.chat_calls[0]["model"] == "chat-deploy" and "reasoning_effort" not in client.chat_calls[0]
    assert client.embed_calls[0]["model"] == "embed-deploy"


# ---- chat_text ----

def test_chat_text_returns_plain_text_and_is_cached(tmp_path):
    client = FakeClient(chat=lambda kw: chat_reply("Library opens at nine."))
    p = Provider({"provider": GEMINI}, cache_dir=tmp_path, client=client)
    msgs = [{"role": "user", "content": "when does the library open?"}]
    assert p.chat_text(msgs) == "Library opens at nine."
    assert p.chat_text(msgs) == "Library opens at nine."
    assert len(client.chat_calls) == 1 and p.cache_hits == 1
    assert "response_format" not in client.chat_calls[0]
    assert client.chat_calls[0]["messages"] == msgs  # no JSON instruction added


def test_chat_text_and_chat_json_do_not_share_cache_entries(tmp_path):
    client = FakeClient(chat=lambda kw: chat_reply('{"ok": true}'))
    p = Provider({"provider": GEMINI}, cache_dir=tmp_path, client=client)
    msgs = [{"role": "user", "content": "same prompt"}]
    p.chat_text(msgs)
    p.chat_json(msgs)
    assert len(client.chat_calls) == 2


def test_chat_text_downgrades_reasoning_effort_like_chat_json(tmp_path):
    def chat(kw):
        if "reasoning_effort" in kw:
            raise openai.BadRequestError("reasoning_effort not supported", response=_response(400), body=None)
        return chat_reply("ok")

    client = FakeClient(chat=chat)
    p = Provider({"provider": GEMINI}, cache_dir=tmp_path, client=client)
    assert p.chat_text([{"role": "user", "content": "x"}]) == "ok" and not p.effort_active


def _response(status):
    import httpx2 as httpx
    return httpx.Response(status, request=httpx.Request("POST", "https://example.test"))


# ---- embedding size ----

def test_wrong_embedding_size_fails_loudly_and_is_not_cached(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_PROVIDER", "azure")
    p = Provider(CFG, cache_dir=tmp_path, client=embed_client(5))
    with pytest.raises(ProviderError, match="returned 5 dimensions but config expects 4"):
        p.embed(["hello"])
    right = Provider(CFG, cache_dir=tmp_path, client=embed_client(4))
    assert len(right.embed(["hello"])[0]) == 4  # nothing wrong was cached under that key


def test_wrong_size_found_in_cache_also_fails(monkeypatch, tmp_path):
    p = Provider({"provider": GEMINI}, cache_dir=tmp_path, client=embed_client(5))  # no embed_dim: allowed
    p.embed(["hello"])
    monkeypatch.setenv("LLM_PROVIDER", "azure")
    strict = Provider({"provider": {**GEMINI, "embed_dim": 4}}, cache_dir=tmp_path, client=embed_client(4))
    with pytest.raises(ProviderError, match="dimensions"):
        strict.embed(["hello"])


def test_make_provider_verifies_embedding_size_once_and_caches_it(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_PROVIDER", "azure")
    client = embed_client(4)
    make_provider(CFG, cache_dir=tmp_path, client=client)
    make_provider(CFG, cache_dir=tmp_path, client=client)
    assert len(client.embed_calls) == 1
    with pytest.raises(ProviderError, match="dimensions"):
        make_provider(CFG, cache_dir=tmp_path / "other", client=embed_client(3))


def test_make_provider_makes_no_call_without_embed_dim(tmp_path):
    client = embed_client(7)
    make_provider({"provider": GEMINI}, cache_dir=tmp_path, client=client)
    assert client.embed_calls == []


def test_metadata_reports_embed_dim_only_when_configured(monkeypatch, tmp_path):
    assert "embed_dim" not in Provider({"provider": GEMINI}, cache_dir=tmp_path, client=object()).metadata()
    monkeypatch.setenv("LLM_PROVIDER", "azure")
    assert Provider(CFG, cache_dir=tmp_path, client=object()).metadata()["embed_dim"] == 4


# ---- v1 stays reproducible ----

def test_v1_cache_keys_are_unchanged(tmp_path):
    """Keys of the pre-Azure provider, computed before this change. If these move, v1 would re-call the API."""
    p = Provider({"provider": {**GEMINI, "chat_model": "gemini-3.5-flash-lite", "embed_model": "gemini-embedding-2"}},
                 cache_dir=tmp_path, client=object())
    assert p._key({"model": "gemini-embedding-2", "input": "hostel curfew"}) == \
        "1bbb18137c9566a2683f589587df3d5e83427a395402939785f3afa0625c21c1"
    chat = {"model": "gemini-3.5-flash-lite", "messages": [{"role": "user", "content": "hi"}], "temperature": 0,
            "response_format": {"type": "json_object"}, "reasoning_effort": "minimal"}
    assert p._key(chat) == "6040f4d5f75df5c89965968df03e5fc46ebf67d959a35ed34bce87acbc93cd8e"


# ---- FakeProvider ----

def test_fake_provider_chat_text_and_recording():
    fake = FakeProvider(text_replies=["first"], text_fn=None)
    assert fake.chat_text([{"role": "user", "content": "q"}]) == "first"
    assert fake.text_requests == [[{"role": "user", "content": "q"}]]
    fn = FakeProvider(text_fn=lambda m: m[-1]["content"].upper())
    assert fn.chat_text([{"role": "user", "content": "abc"}]) == "ABC"
    fake.embed(["a", "b"])
    assert fake.embed_requests == [["a", "b"]]


def test_fake_provider_embed_dim_check_matches_the_real_one():
    assert FakeProvider(dim=8, embed_dim=8).check_embed_dim() == 8
    with pytest.raises(ProviderError, match="expects 16"):
        FakeProvider(dim=8, embed_dim=16).embed(["x"])

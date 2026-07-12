"""Tests for model normalization and validation."""
from reidx.provider.models import (
    NormalizedModel,
    denormalize_model_id,
    normalize_model_id,
    validate_model_against_provider,
)


def test_normalize_basic_openrouter_model():
    result = normalize_model_id("cohere/north-mini-code:free", provider_name="openrouter")
    assert result.provider == "openrouter"
    assert result.model_id == "cohere/north-mini-code:free"
    assert result.full_id == "openrouter/cohere/north-mini-code:free"
    assert result.variant == "free"
    assert result.base_model == "cohere/north-mini-code"
    assert result.is_valid is True


def test_normalize_with_duplicated_provider_prefix():
    result = normalize_model_id("openrouter/cohere/north-mini-code:free", provider_name="openrouter")
    assert result.provider == "openrouter"
    assert result.model_id == "cohere/north-mini-code:free"
    assert result.full_id == "openrouter/cohere/north-mini-code:free"
    assert result.is_valid is True


def test_normalize_strips_ui_display_text():
    result = normalize_model_id("cohere/north-mini-code:free [via openrouter]", provider_name="openrouter")
    assert result.provider == "openrouter"
    assert result.model_id == "cohere/north-mini-code:free"
    assert result.full_id == "openrouter/cohere/north-mini-code:free"
    assert result.is_valid is True


def test_normalize_removes_provider_dash_prefix():
    result = normalize_model_id("OpenRouter - cohere/north-mini-code:free", provider_name="openrouter")
    assert result.provider == "openrouter"
    assert result.model_id == "cohere/north-mini-code:free"
    assert result.is_valid is True


def test_normalize_case_insensitive_variant():
    result = normalize_model_id("COHERE/NORTH-MINI-CODE:FREE", provider_name="openrouter")
    assert result.provider == "openrouter"
    assert result.variant == "free"
    assert result.base_model == "COHERE/NORTH-MINI-CODE"
    assert result.is_valid is True


def test_normalize_no_variant():
    result = normalize_model_id("cohere/north-mini-code", provider_name="openrouter")
    assert result.provider == "openrouter"
    assert result.model_id == "cohere/north-mini-code"
    assert result.variant is None
    assert result.base_model == "cohere/north-mini-code"
    assert result.is_valid is True


def test_normalize_invalid_format():
    result = normalize_model_id("invalid-model", provider_name="openrouter")
    assert result.is_valid is False
    assert result.provider == "openrouter"


def test_denormalize_with_provider():
    model = NormalizedModel(
        provider="openrouter",
        model_id="cohere/north-mini-code:free",
        full_id="openrouter/cohere/north-mini-code:free",
        variant="free",
        base_model="cohere/north-mini-code",
        is_valid=True,
    )
    assert denormalize_model_id(model) == "openrouter/cohere/north-mini-code:free"


def test_denormalize_without_provider():
    model = NormalizedModel(
        provider="openrouter",
        model_id="cohere/north-mini-code:free",
        full_id="openrouter/cohere/north-mini-code:free",
        variant="free",
        base_model="cohere/north-mini-code",
        is_valid=True,
    )
    assert denormalize_model_id(model, include_provider=False) == "cohere/north-mini-code:free"


def test_validate_model_exact_match():
    models = ["openrouter/cohere/north-mini-code:free", "openrouter/meta-llama/llama-3.1-70b-instruct"]
    normalized = normalize_model_id("cohere/north-mini-code:free", provider_name="openrouter")
    valid, msg = validate_model_against_provider(normalized, models)
    assert valid is True
    assert "found in provider catalog" in msg


def test_validate_model_base_model_match():
    models = ["openrouter/cohere/north-mini-code", "openrouter/meta-llama/llama-3.1-70b-instruct"]
    normalized = normalize_model_id("cohere/north-mini-code:free", provider_name="openrouter")
    valid, msg = validate_model_against_provider(normalized, models)
    assert valid is True
    assert "Base model found with provider prefix" in msg


def test_validate_model_not_found():
    models = ["openrouter/meta-llama/llama-3.1-70b-instruct"]
    normalized = normalize_model_id("cohere/north-mini-code:free", provider_name="openrouter")
    valid, msg = validate_model_against_provider(normalized, models)
    assert valid is False
    assert "not found in provider catalog" in msg


def test_validate_model_fuzzy_match():
    models = ["openrouter/cohere/command-r-plus"]
    normalized = normalize_model_id("cohere/command-r", provider_name="openrouter")
    valid, msg = validate_model_against_provider(normalized, models)
    assert valid is True
    assert "Similar model found" in msg


def test_validate_no_models_available():
    normalized = normalize_model_id("cohere/north-mini-code:free", provider_name="openrouter")
    valid, msg = validate_model_against_provider(normalized, [])
    assert valid is True
    assert "skipping validation" in msg


def test_validate_invalid_format():
    model = NormalizedModel(
        provider="",
        model_id="invalid",
        full_id="invalid",
        variant=None,
        base_model="invalid",
        is_valid=False,
    )
    valid, msg = validate_model_against_provider(model, ["openrouter/cohere/north-mini-code"])
    assert valid is False
    assert "Invalid model format" in msg
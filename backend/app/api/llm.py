"""LLM options API."""

from fastapi import APIRouter

from app.schemas.llm import LlmModelOption, LlmOptionsResponse, LlmProviderOption

router = APIRouter(prefix="/llm", tags=["llm"])

_DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.5-flash",
    "mock": "mock",
}


@router.get("/options", response_model=LlmOptionsResponse)
def list_llm_options() -> LlmOptionsResponse:
    return LlmOptionsResponse(
        providers=[
            LlmProviderOption(
                id="openai",
                label="OpenAI",
                default_model=_DEFAULT_MODELS["openai"],
                models=[
                    LlmModelOption(id="gpt-4o-mini", label="GPT-4o Mini"),
                ],
            ),
            LlmProviderOption(
                id="gemini",
                label="Google Gemini",
                default_model=_DEFAULT_MODELS["gemini"],
                models=[
                    LlmModelOption(id="gemini-2.5-flash", label="Gemini 2.5 Flash"),
                ],
            ),
            LlmProviderOption(
                id="mock",
                label="Mock (dry-run)",
                default_model=_DEFAULT_MODELS["mock"],
                models=[LlmModelOption(id="mock", label="Mock responses")],
            ),
        ],
    )

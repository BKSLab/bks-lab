"""Explicit registry of verified publisher profiles."""

from src.news_sources.base import SourceProfile
from src.news_sources.labs_anthropic import PROFILE as LABS_ANTHROPIC
from src.news_sources.labs_deepmind import PROFILE as LABS_DEEPMIND
from src.news_sources.labs_google_ai import PROFILE as LABS_GOOGLE_AI
from src.news_sources.labs_huggingface import PROFILE as LABS_HUGGINGFACE
from src.news_sources.labs_meta import PROFILE as LABS_META
from src.news_sources.labs_ms_research import PROFILE as LABS_MS_RESEARCH
from src.news_sources.labs_mistral import PROFILE as LABS_MISTRAL
from src.news_sources.labs_nvidia import PROFILE as LABS_NVIDIA
from src.news_sources.labs_ibm import PROFILE as LABS_IBM
from src.news_sources.labs_qwen import PROFILE as LABS_QWEN
from src.news_sources.eng_simon import PROFILE as ENG_SIMON
from src.news_sources.eng_weng import PROFILE as ENG_WENG
from src.news_sources.eng_huyen import PROFILE as ENG_HUYEN
from src.news_sources.eng_hf_papers import PROFILE as ENG_HF_PAPERS
from src.news_sources.eng_arxiv_cl import PROFILE as ENG_ARXIV_CL
from src.news_sources.eng_hamel import PROFILE as ENG_HAMEL
from src.news_sources.eng_raschka import PROFILE as ENG_RASCHKA
from src.news_sources.eng_github import PROFILE as ENG_GITHUB
from src.news_sources.biz_mollick import PROFILE as BIZ_MOLLICK
from src.news_sources.biz_ms_worklab import PROFILE as BIZ_MS_WORKLAB
from src.news_sources.soc_ai_now import PROFILE as SOC_AI_NOW
from src.news_sources.soc_ada import PROFILE as SOC_ADA
from src.news_sources.soc_oecd import PROFILE as SOC_OECD
from src.news_sources.soc_metr import PROFILE as SOC_METR
from src.news_sources.soc_partnership import PROFILE as SOC_PARTNERSHIP
from src.news_sources.soc_gradient import PROFILE as SOC_GRADIENT
from src.news_sources.soc_noema import PROFILE as SOC_NOEMA
from src.news_sources.soc_nature import PROFILE as SOC_NATURE
from src.news_sources.authors_alexander import PROFILE as AUTHORS_ALEXANDER
from src.news_sources.ru_habr_ai import PROFILE as RU_HABR_AI
from src.news_sources.ru_habr_ml import PROFILE as RU_HABR_ML
from src.news_sources.ru_tproger import PROFILE as RU_TPROGER
from src.news_sources.ru_comnews import PROFILE as RU_COMNEWS
from src.news_sources.ru_gorky import PROFILE as RU_GORKY
from src.news_sources.ru_cnews import PROFILE as RU_CNEWS
from src.news_sources.ru_rbc import PROFILE as RU_RBC
from src.news_sources.ru_forbes import PROFILE as RU_FORBES
from src.news_sources.ru_kod import PROFILE as RU_KOD

_PROFILES: tuple[SourceProfile, ...] = (
    LABS_ANTHROPIC,
    LABS_DEEPMIND,
    LABS_GOOGLE_AI,
    LABS_HUGGINGFACE,
    LABS_META,
    LABS_MS_RESEARCH,
    LABS_MISTRAL,
    LABS_NVIDIA,
    LABS_IBM,
    LABS_QWEN,
    ENG_SIMON,
    ENG_WENG,
    ENG_HUYEN,
    ENG_HF_PAPERS,
    ENG_ARXIV_CL,
    ENG_HAMEL,
    ENG_RASCHKA,
    ENG_GITHUB,
    BIZ_MOLLICK,
    BIZ_MS_WORKLAB,
    SOC_AI_NOW,
    SOC_ADA,
    SOC_OECD,
    SOC_METR,
    SOC_PARTNERSHIP,
    SOC_GRADIENT,
    SOC_NOEMA,
    SOC_NATURE,
    AUTHORS_ALEXANDER,
    RU_HABR_AI,
    RU_HABR_ML,
    RU_TPROGER,
    RU_COMNEWS,
    RU_GORKY,
    RU_CNEWS,
    RU_RBC,
    RU_FORBES,
    RU_KOD,
)


def get_source_profiles() -> tuple[SourceProfile, ...]:
    """Return supported publishers in their stable catalogue order."""
    return _PROFILES


def get_source_profile(profile_id: str) -> SourceProfile | None:
    """Resolve a supported publisher; unsupported IDs never use a fallback."""
    return next((profile for profile in _PROFILES if profile.id == profile_id), None)

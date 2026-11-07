"""
Centralized configuration management module.
Loads location parameters, tax registration filters, target CNAEs, and sales funnel rules
from config.json.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Tuple

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

_CONFIG_CACHE: Dict[str, Any] = {}


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """Loads configuration data from a JSON file, or falls back to default settings."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE and config_path == DEFAULT_CONFIG_PATH:
        return _CONFIG_CACHE

    if not config_path.exists():
        default_config = {
            "location": {
                "city": "LONDRINA",
                "state": "PR",
                "default_area_code": "43",
                "priority_neighborhoods": ["Centro", "Gleba Palhano"],
            },
            "registration_filters": {
                "required_status": "ACTIVE",
                "only_with_phone": False,
            },
            "target_segments": [
                {
                    "code": "4781400",
                    "description": "Comércio varejista de artigos do vestuário e acessórios",
                    "segment": "Moda e Vestuário",
                }
            ],
            "sales_funnel": {
                "allowed_statuses": ["NEW", "CONTACTED", "MEETING_SCHEDULED"],
                "outreach_channels": ["WhatsApp", "Phone", "Email"],
            },
        }
        return default_config

    with open(config_path, "r", encoding="utf-8") as file:
        _CONFIG_CACHE = json.load(file)
    return _CONFIG_CACHE


def get_city_state(config_path: Path = DEFAULT_CONFIG_PATH) -> Tuple[str, str]:
    """Returns a tuple (city, state) in uppercase."""
    config = load_config(config_path)
    location = config.get("location") or config.get("localizacao") or {}
    city = location.get("city") or location.get("municipio") or "LONDRINA"
    state = location.get("state") or location.get("uf") or "PR"
    return city.upper(), state.upper()


def get_default_area_code(config_path: Path = DEFAULT_CONFIG_PATH) -> str:
    """Returns the default telephone area code (DDD)."""
    config = load_config(config_path)
    location = config.get("location") or config.get("localizacao") or {}
    area_code = location.get("default_area_code") or location.get("ddd_padrao") or "43"
    return str(area_code)


def get_target_cnaes(config_path: Path = DEFAULT_CONFIG_PATH) -> List[Dict[str, str]]:
    """Returns the list of target CNAEs and business segments."""
    config = load_config(config_path)
    segments = config.get("target_segments") or config.get("segmentos_alvo") or []
    normalized_segments = []
    for item in segments:
        code = item.get("code") or item.get("codigo") or ""
        description = item.get("description") or item.get("descricao") or ""
        segment = item.get("segment") or item.get("segmento") or ""
        normalized_segments.append({
            "code": str(code),
            "description": description,
            "segment": segment,
        })
    return normalized_segments

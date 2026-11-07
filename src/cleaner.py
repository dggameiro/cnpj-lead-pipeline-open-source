"""
Data sanitization, validation, and standardization module.
Provides routines for string cleaning, CNPJ formatting and validation,
phone mask application, and company record normalization.
"""

import re
from typing import Dict, Any, Optional

from src.config import get_city_state, get_default_area_code


def clean_cnpj(cnpj: str) -> str:
    """Removes non-numeric characters from a CNPJ string."""
    if not cnpj:
        return ""
    return re.sub(r"\D", "", str(cnpj))


def format_cnpj(cnpj: str) -> str:
    """Formats a 14-digit numeric string to standard XX.XXX.XXX/XXXX-XX format."""
    digits = clean_cnpj(cnpj)
    if len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    return cnpj


def validate_cnpj(cnpj: str) -> bool:
    """Validates the length (14 digits) and non-triviality of a CNPJ."""
    digits = clean_cnpj(cnpj)
    if len(digits) != 14:
        return False
    if len(set(digits)) == 1:
        return False
    return True


def format_phone(phone: Optional[str], default_area_code: Optional[str] = None) -> str:
    """
    Sanitizes and applies standard mask to landline or mobile phone numbers.
    If the number lacks an area code (8 or 9 digits), prepends the default area code.
    """
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))

    # Prepend default area code if missing
    if len(digits) in [8, 9]:
        area_code = default_area_code or get_default_area_code()
        digits = f"{area_code}{digits}"

    if len(digits) == 11:  # Mobile with area code (e.g., 43 99999-8888)
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    elif len(digits) == 10:  # Landline with area code (e.g., 43 3333-2222)
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    return str(phone).strip()


def sanitize_text(text: Optional[str]) -> str:
    """Collapses consecutive whitespaces and trims leading/trailing spaces."""
    if not text:
        return ""
    cleaned = " ".join(str(text).split())
    return cleaned.strip()


def normalize_company(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizes company record attributes into canonical English domain format:
    - Extracts digits from CNPJ and zip code
    - Standardizes legal name, trade name, addresses, and contacts
    - Normalizes status enums (e.g., ATIVA -> ACTIVE, NOVO -> NEW)
    """
    default_city, default_state = get_city_state()

    raw_cnpj = record.get("cnpj") or ""
    cleaned_cnpj = clean_cnpj(raw_cnpj)

    raw_legal_name = record.get("legal_name") or record.get("razao_social") or ""
    legal_name = sanitize_text(raw_legal_name).upper()

    raw_trade_name = record.get("trade_name") or record.get("nome_fantasia") or ""
    trade_name = sanitize_text(raw_trade_name).title()
    if not trade_name or trade_name.upper() in ["SEM NOME FANTASIA", "NONE"]:
        trade_name = legal_name.title()

    raw_neighborhood = record.get("neighborhood") or record.get("bairro") or ""
    neighborhood = sanitize_text(raw_neighborhood).title()

    raw_street = record.get("street") or record.get("logradouro") or ""
    street = sanitize_text(raw_street).title()

    raw_number = record.get("number") or record.get("numero") or "S/N"
    number = sanitize_text(raw_number)

    raw_city = record.get("city") or record.get("municipio") or default_city
    city = sanitize_text(raw_city).upper()

    raw_state = record.get("state") or record.get("uf") or default_state
    state = sanitize_text(raw_state).upper()

    raw_email = record.get("email") or ""
    email = sanitize_text(raw_email).lower()

    raw_phone = record.get("phone") or record.get("telefone") or ""
    phone = format_phone(raw_phone)

    raw_cnae = record.get("primary_cnae") or record.get("cnae_fiscal") or ""
    primary_cnae = clean_cnpj(raw_cnae)

    raw_status = record.get("registration_status") or record.get("situacao_cadastral") or "ACTIVE"
    status_upper = sanitize_text(raw_status).upper()
    registration_status = "ACTIVE" if status_upper in ["ACTIVE", "ATIVA"] else status_upper

    raw_opening_date = record.get("opening_date") or record.get("data_abertura") or ""
    opening_date = sanitize_text(raw_opening_date)

    raw_zip = record.get("zip_code") or record.get("cep") or ""
    zip_code = clean_cnpj(raw_zip)

    raw_prospecting = record.get("prospecting_status") or record.get("status_prospeccao") or "NEW"
    prospecting_upper = sanitize_text(raw_prospecting).upper()
    if prospecting_upper in ["NEW", "NOVO"]:
        prospecting_status = "NEW"
    elif prospecting_upper in ["CONTACTED", "CONTATADO"]:
        prospecting_status = "CONTACTED"
    elif prospecting_upper in ["MEETING_SCHEDULED", "REUNIAO_AGENDADA"]:
        prospecting_status = "MEETING_SCHEDULED"
    elif prospecting_upper in ["PROPOSAL_SENT", "PROPOSTA_ENVIADA"]:
        prospecting_status = "PROPOSAL_SENT"
    elif prospecting_upper in ["CONTRACT_SIGNED", "CONTRATO_FECHADO"]:
        prospecting_status = "CONTRACT_SIGNED"
    elif prospecting_upper in ["NOT_INTERESTED", "SEM_INTERESSE"]:
        prospecting_status = "NOT_INTERESTED"
    else:
        prospecting_status = prospecting_upper

    has_ecommerce_cnae = int(record.get("has_ecommerce_cnae") or record.get("cnae_ecommerce") or 0)
    website_domain = record.get("website_domain") or record.get("dominio_proprio")
    detected_platform = record.get("detected_platform") or record.get("plataforma_detectada") or "None"

    raw_maturity = record.get("digital_maturity") or record.get("maturidade_digital") or "NO_DIGITAL_PRESENCE"
    maturity_upper = sanitize_text(raw_maturity).upper()
    if maturity_upper in ["NO_DIGITAL_PRESENCE", "SEM_PRESENCA_DIGITAL"]:
        digital_maturity = "NO_DIGITAL_PRESENCE"
    elif maturity_upper in ["INSTITUTIONAL_WEBSITE", "PRESENCA_INSTITUCIONAL"]:
        digital_maturity = "INSTITUTIONAL_WEBSITE"
    elif maturity_upper in ["BASIC_ECOMMERCE", "ECOMMERCE_BASICO"]:
        digital_maturity = "BASIC_ECOMMERCE"
    elif maturity_upper in ["ADVANCED_ECOMMERCE", "ECOMMERCE_AVANCADO"]:
        digital_maturity = "ADVANCED_ECOMMERCE"
    else:
        digital_maturity = maturity_upper

    return {
        "cnpj": cleaned_cnpj,
        "legal_name": legal_name,
        "trade_name": trade_name,
        "registration_status": registration_status,
        "opening_date": opening_date,
        "primary_cnae": primary_cnae,
        "street": street,
        "number": number,
        "neighborhood": neighborhood,
        "city": city,
        "state": state,
        "zip_code": zip_code,
        "phone": phone,
        "email": email,
        "prospecting_status": prospecting_status,
        "has_ecommerce_cnae": has_ecommerce_cnae,
        "website_domain": website_domain,
        "detected_platform": detected_platform,
        "digital_maturity": digital_maturity,
    }

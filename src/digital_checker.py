"""
Digital presence qualification and lead scoring module.
Implements a 3-layer analysis funnel:
- Layer 1: Registration data checks (e-commerce CNAE 4791-2/01 and email provider type).
- Layer 2: Domain syntax validation for corporate web addresses.
- Layer 3: Lightweight HTTP inspection for e-commerce platforms, cart routes, and tracking pixels.
"""

import re
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Tuple

from src.database import list_companies, insert_company

FREE_EMAIL_DOMAINS = {
    "gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "yahoo.com.br",
    "icloud.com", "bol.com.br", "uol.com.br", "live.com", "terra.com.br"
}

ECOMMERCE_FINGERPRINTS = {
    "Shopify": [r"cdn\.shopify\.com", r"Shopify\.theme", r"myshopify\.com"],
    "WooCommerce": [r"wp-content/plugins/woocommerce", r"woocommerce-cart", r"wc-api"],
    "Nuvemshop": [r"nuvemshop\.com\.br", r"tiendanube\.com", r"d26lpennugtm8s\.cloudfront\.net"],
    "Tray": [r"tray\.com\.br", r"images\.tray\.com\.br", r"assets\.tray\.net\.br"],
    "Loja Integrada": [r"lojaintegrada\.com\.br", r"cdn\.awsli\.com\.br"],
    "Vtex": [r"vteximg\.com\.br", r"vtex\.com"],
}

TRAFFIC_TAGS = [
    r"fbevents\.js",            # Meta Pixel
    r"googletagmanager\.com",   # Google Tag Manager
    r"analytics\.js|gtag\(",    # Google Analytics
    r"clarity\.ms",             # Microsoft Clarity
    r"hotjar\.com"              # Hotjar
]


def analyze_layer_1(record: Dict[str, Any]) -> Tuple[int, Optional[str]]:
    """
    Layer 1: Offline cadastral inspection.
    Detects secondary CNAE 4791-2/01 (retail via internet) and checks for corporate email domains.
    Returns: (has_ecommerce_cnae: 1 or 0, candidate_domain: Optional[str])
    """
    has_ecommerce_cnae = 0
    primary_cnae = str(record.get("primary_cnae") or record.get("cnae_fiscal") or "")
    secondary_cnaes = str(record.get("secondary_cnaes") or record.get("cnaes_secundarios") or "")

    cnae_text = f"{primary_cnae} {secondary_cnaes}"
    if "4791201" in cnae_text or "4791-2/01" in cnae_text or "4791-201" in cnae_text:
        has_ecommerce_cnae = 1

    email = str(record.get("email", "")).strip().lower()
    candidate_domain = None

    if "@" in email:
        provider = email.split("@")[-1].strip()
        if provider and provider not in FREE_EMAIL_DOMAINS and "contab" not in provider:
            candidate_domain = provider

    return has_ecommerce_cnae, candidate_domain


def analyze_layer_2(candidate_domain: Optional[str]) -> Optional[str]:
    """
    Layer 2: Domain syntax validation.
    Checks whether candidate domain string forms a valid web URL.
    Returns: Formatted URL string or None.
    """
    if not candidate_domain:
        return None

    cleaned_domain = candidate_domain.replace("http://", "").replace("https://", "").strip("/")
    if "." in cleaned_domain and len(cleaned_domain) > 4:
        return f"https://www.{cleaned_domain}"
    return None


def analyze_layer_3_http(url: str, timeout: int = 3) -> Tuple[str, bool, bool]:
    """
    Layer 3: HTTP GET inspection and lightweight HTML fingerprinting.
    Analyzes page content for e-commerce platforms, cart routes, and marketing tracking tags.
    Returns: (detected_platform, has_cart, has_pixel)
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LeadScoring/1.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    try:
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status == 200:
                html = response.read(150000).decode("utf-8", errors="ignore")

                # 1. Platform signature detection
                detected_platform = "None"
                for platform_name, patterns in ECOMMERCE_FINGERPRINTS.items():
                    for pattern in patterns:
                        if re.search(pattern, html, re.IGNORECASE):
                            detected_platform = platform_name
                            break
                    if detected_platform != "None":
                        break

                # 2. Cart / checkout route detection
                has_cart = bool(re.search(
                    r"(/cart|/carrinho|/checkout|/sacola|data-cart|add-to-cart|carrinho-vazio)",
                    html,
                    re.IGNORECASE
                ))

                # 3. Marketing tracking tags
                has_pixel = False
                for tag in TRAFFIC_TAGS:
                    if re.search(tag, html, re.IGNORECASE):
                        has_pixel = True
                        break

                if detected_platform == "None" and has_cart:
                    detected_platform = "Other (Custom E-commerce)"

                return detected_platform, has_cart, has_pixel
    except Exception:
        pass

    return "None", False, False


def classify_digital_maturity(
    has_ecommerce_cnae: int,
    website_domain: Optional[str],
    detected_platform: str,
    has_cart: bool,
    has_pixel: bool
) -> str:
    """
    Classifies company digital presence into four standard categories:
    - ADVANCED_ECOMMERCE: E-commerce platform or cart identified with active tracking pixels/tags.
    - BASIC_ECOMMERCE: E-commerce platform or cart identified without tracking pixels.
    - INSTITUTIONAL_WEBSITE: Domain active or online CNAE without active web store.
    - NO_DIGITAL_PRESENCE: No website domain or e-commerce detected.
    """
    if detected_platform != "None" or has_cart:
        if has_pixel:
            return "ADVANCED_ECOMMERCE"
        return "BASIC_ECOMMERCE"

    if website_domain:
        return "INSTITUTIONAL_WEBSITE"

    if has_ecommerce_cnae == 1:
        return "INSTITUTIONAL_WEBSITE"

    return "NO_DIGITAL_PRESENCE"


def enrich_company_digital(record: Dict[str, Any], check_http: bool = True) -> Dict[str, Any]:
    """Applies the 3-layer digital presence checks to a company record and returns calculated fields."""
    has_ecom, candidate_domain = analyze_layer_1(record)
    domain = analyze_layer_2(candidate_domain)

    platform = "None"
    has_cart = False
    has_pixel = False

    if domain and check_http:
        platform, has_cart, has_pixel = analyze_layer_3_http(domain)

    maturity = classify_digital_maturity(has_ecom, domain, platform, has_cart, has_pixel)

    return {
        "has_ecommerce_cnae": has_ecom,
        "website_domain": domain,
        "detected_platform": platform,
        "digital_maturity": maturity,
    }


def qualify_companies_digital(check_http: bool = False, max_workers: int = 5) -> int:
    """Updates digital maturity fields for all companies stored in SQLite using multithreading."""
    companies = list_companies()
    if not companies:
        return 0

    updated_count = 0

    def _process(company):
        digital_info = enrich_company_digital(company, check_http=check_http)
        merged = dict(company)
        merged.update(digital_info)
        insert_company(merged)
        return 1

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_process, comp) for comp in companies]
        for fut in as_completed(futures):
            updated_count += fut.result()

    return updated_count

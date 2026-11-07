"""
Data pipeline orchestration module.
Data Engineering & Commercial Lead Intelligence.

Coordinates database initialization, data ingestion, digital presence qualification,
relational persistence, and statistical reporting.
"""

import sys
from pathlib import Path
from typing import Optional

from src.database import (
    init_db,
    get_metrics,
    export_leads_to_csv,
)
from src.extractor import (
    load_local_seed_data,
    ingest_radar_cnpj_export,
    fetch_brasil_api_cnpj,
    load_target_cnaes,
)
from src.config import load_config
from src.digital_checker import qualify_companies_digital

MATURITY_LABELS_PT = {
    "NO_DIGITAL_PRESENCE": "SEM PRESENÇA DIGITAL (Sem domínio ou plataforma)",
    "INSTITUTIONAL_WEBSITE": "PRESENÇA INSTITUCIONAL (Domínio ativo sem loja)",
    "BASIC_ECOMMERCE": "E-COMMERCE BÁSICO (Loja ativa sem tags de tráfego)",
    "ADVANCED_ECOMMERCE": "E-COMMERCE AVANÇADO (Loja ativa com tags de tráfego)",
}

STATUS_LABELS_PT = {
    "NEW": "Novo",
    "CONTACTED": "Contatado",
    "MEETING_SCHEDULED": "Reunião Agendada",
    "PROPOSAL_SENT": "Proposta Enviada",
    "CONTRACT_SIGNED": "Contrato Fechado",
    "NOT_INTERESTED": "Sem Interesse",
}


def print_metrics_dashboard() -> None:
    """Prints a consolidated statistical summary of companies in SQLite database."""
    config = load_config()
    location = config.get("location") or {}
    city = location.get("city") or "LONDRINA"
    state = location.get("state") or "PR"

    metrics = get_metrics()
    total = metrics["total_companies"]

    print("\n" + "=" * 65)
    print(f"PAINEL ANALÍTICO DE DADOS - {city}/{state}")
    print("=" * 65)
    print(f"Total de registros na base: {total}")

    print("\nDistribuição por Segmento:")
    for item in metrics["segments"]:
        percentage = (item["quantity"] / total * 100) if total else 0
        print(f"  • {item['segment']:<24}: {item['quantity']:>2} ({percentage:>5.1f}%)")

    print("\nClassificação de Presença Digital:")
    for item in metrics["maturities"]:
        percentage = (item["quantity"] / total * 100) if total else 0
        maturity_code = item["digital_maturity"]
        description = MATURITY_LABELS_PT.get(maturity_code, maturity_code)
        print(f"  • {description:<58}: {item['quantity']:>2} ({percentage:>5.1f}%)")

    print("\nConcentração por Bairro (Top 5):")
    for item in metrics["neighborhoods"][:5]:
        print(f"  • {item['neighborhood']:<24}: {item['quantity']:>2} empresas")

    print("\nStatus no Funil de Vendas:")
    for item in metrics["funnel"]:
        status_code = item["status"]
        status_desc = STATUS_LABELS_PT.get(status_code, status_code)
        percentage = (item["quantity"] / total * 100) if total else 0
        print(f"  • {status_desc:<24}: {item['quantity']:>2} ({percentage:>5.1f}%)")

    print("=" * 65 + "\n")


def run_pipeline(
    source: str = "local",
    target_cnpj: Optional[str] = None,
    radar_file: Optional[str] = None,
) -> int:
    """
    Executes the pipeline lifecycle for the selected source mode:
    - local: reads local structured JSON data
    - radar: ingests exported file from radar-cnpj-mcp
    - brasilapi: executes live query against BrasilAPI
    - full: integrated execution across all data sources
    """
    config = load_config()
    location = config.get("location") or {}
    city = location.get("city") or "LONDRINA"
    state = location.get("state") or "PR"
    area_code = location.get("default_area_code") or "43"

    reg_filters = config.get("registration_filters") or {}
    status_filter = reg_filters.get("status") or "ACTIVE"
    segments = config.get("target_segments") or []

    print("\n" + "=" * 65)
    print(f"EXECUÇÃO DO PIPELINE DE DADOS - MODO: [{source.upper()}]")
    print(f"Região: {city} - {state} (DDD: {area_code})")
    print(f"Segmentos: {len(segments)} CNAEs mapeados | Filtro cadastral: {status_filter}")
    print("=" * 65)

    # 1. Database schema and target CNAEs setup
    init_db()
    load_target_cnaes()
    processed_count = 0

    # 2. Ingestion based on selected source mode
    if source == "local":
        print(f"\n[Etapa 1/4] Ingestão de dados locais ({city})...")
        processed_count = load_local_seed_data()
        print(f" -> {processed_count} empresas processadas do arquivo local.")

    elif source == "radar":
        default_radar = Path("data/export_radar_cnpj_londrina.json")
        if not default_radar.exists():
            default_radar = Path("data/export_radar_sample.json")
        file_path = Path(radar_file or default_radar)
        print(f"\n[Etapa 1/4] Ingestão de dados do radar-cnpj: {file_path}...")
        processed_count = ingest_radar_cnpj_export(file_path)
        print(f" -> {processed_count} empresas processadas via radar-cnpj.")

    elif source == "brasilapi":
        cnpjs_to_query = [target_cnpj] if target_cnpj else ["56032902000164", "17829739000103"]
        print(f"\n[Etapa 1/4] Consulta à API pública da Receita Federal via BrasilAPI...")
        for c in cnpjs_to_query:
            print(f" -> Consultando CNPJ: {c}...")
            result = fetch_brasil_api_cnpj(c)
            if result:
                processed_count += 1
                legal_name = result.get("legal_name")
                neighborhood = result.get("neighborhood")
                rec_city = result.get("city")
                print(f"    [OK] {legal_name} ({neighborhood} - {rec_city})")
            else:
                print(f"    [AVISO] Não foi possível obter dados para {c}.")

    elif source == "full":
        print("\n[Etapa 1/4] Ingestão integrada de todas as fontes...")
        p1 = load_local_seed_data()
        p2 = ingest_radar_cnpj_export(Path("data/export_radar_cnpj_londrina.json"))
        p3 = 0
        for c in ["56032902000164", "17829739000103"]:
            if fetch_brasil_api_cnpj(c):
                p3 += 1
        processed_count = p1 + p2 + p3
        print(f" -> Total processado nas fontes integradas: {processed_count} registros.")

    else:
        print(f"Erro: Modo '{source}' inválido.")
        print("Opções disponíveis: local | radar | brasilapi | full")
        sys.exit(1)

    print("\n[Etapa 2/4] Dados higienizados e persistidos no banco SQLite.")

    # 3. Digital presence qualification
    print("\n[Etapa 3/4] Executando classificação de presença digital (3 camadas)...")
    qualified_count = qualify_companies_digital(check_http=False)
    print(f" -> {qualified_count} empresas qualificadas.")

    # 4. CSV export
    print("\n[Etapa 4/4] Exportando registros consolidados para CSV...")
    total_csv = export_leads_to_csv()
    print(f" -> Arquivo CSV atualizado em 'data/leads_londrina.csv' ({total_csv} registros).")

    # 5. Summary dashboard
    print_metrics_dashboard()
    print("Pipeline finalizado com sucesso.\n")
    return processed_count

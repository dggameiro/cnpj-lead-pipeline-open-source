#!/usr/bin/env python3
"""
Command Line Interface (CLI) and Orchestrator entry point.
Data Engineering & Commercial Lead Intelligence.

Commands:
  run [source]               -> Execute pipeline ETL (sources: local, radar, brasilapi, full)
  list                       -> List companies with optional filters (maturity, neighborhood, cnae, status)
  details <cnpj>             -> Display company full profile and digital indicators
  status <cnpj> <new_status> -> Update prospecting funnel status
  outreach <cnpj>            -> Record commercial contact history
  metrics                    -> Display analytical distribution summary
  dashboard                  -> Generate interactive standalone HTML dashboard
  export                     -> Export filtered database records to CSV
  config                     -> Display active parameters from config.json
"""

import argparse
from pathlib import Path

from src.database import (
    list_companies,
    update_prospecting_status,
    record_outreach,
    export_leads_to_csv,
)
from src.cleaner import format_cnpj
from src.pipeline import run_pipeline, print_metrics_dashboard
from src.config import load_config
from src.dashboard import generate_html_dashboard


def cmd_run(args) -> None:
    """Executes data pipeline ETL for specified source."""
    run_pipeline(
        source=args.source,
        target_cnpj=args.cnpj,
        radar_file=args.file,
    )


def cmd_config(args) -> None:
    """Displays active settings from config.json."""
    config = load_config()
    location = config.get("location") or {}
    city = location.get("city") or "LONDRINA"
    state = location.get("state") or "PR"
    area_code = location.get("default_area_code") or "43"
    neighborhoods = location.get("priority_neighborhoods") or []

    filters = config.get("registration_filters") or {}
    segments = config.get("target_segments") or []
    funnel = config.get("sales_funnel") or {}

    print("\n" + "=" * 65)
    print("CONFIGURAÇÕES DO PROJETO (config.json)")
    print("=" * 65)
    print(f"Município:             {city} - {state} (DDD: {area_code})")
    print(f"Bairros Prioritários:  {', '.join(neighborhoods)}")
    print(f"Situação Cadastral:    {filters.get('status', 'ACTIVE')}")
    print(f"Somente com Telefone:  {filters.get('only_with_phone', False)}")

    print("\nSegmentos Alvo Mapeados (CNAEs):")
    for item in segments:
        code = item.get("code")
        segment = item.get("segment")
        description = item.get("description")
        print(f" • CNAE {code}: {segment} ({description})")

    allowed_statuses = funnel.get("allowed_statuses") or []
    channels = funnel.get("outreach_channels") or []
    print(f"\nEtapas do Funil:       {' -> '.join(allowed_statuses)}")
    print(f"Canais de Abordagem:   {', '.join(channels)}")
    print("=" * 65)
    print("Para alterar parâmetros, edite o arquivo 'config.json'.\n")


def cmd_list(args) -> None:
    """Lists company records with optional filters."""
    config = load_config()
    location = config.get("location") or {}
    default_city = location.get("city") or "LONDRINA"
    city_filter = args.city or default_city

    companies = list_companies(
        cnae=args.cnae,
        neighborhood=args.neighborhood,
        status=args.status,
        digital_maturity=args.maturity,
        city=city_filter,
    )
    if not companies:
        print(f"Nenhum registro encontrado com os filtros informados em {city_filter}.")
        return

    maturity_label = f" [Maturidade: {args.maturity}]" if args.maturity else ""
    print(f"\nTotal encontrado: {len(companies)} empresa(s) em {city_filter}{maturity_label}")
    print("-" * 115)
    print(f"{'CNPJ':<19} | {'NOME FANTASIA':<24} | {'BAIRRO':<16} | {'TELEFONE':<15} | {'MATURIDADE DIGITAL'}")
    print("-" * 115)
    for company in companies:
        cnpj_fmt = format_cnpj(company["cnpj"])
        name = (company.get("trade_name") or company.get("legal_name") or "")[:23]
        neighborhood = (company.get("neighborhood") or "N/D")[:15]
        phone = (company.get("phone") or "Sem telefone")[:15]
        maturity = company.get("digital_maturity") or "NO_DIGITAL_PRESENCE"
        print(f"{cnpj_fmt:<19} | {name:<24} | {neighborhood:<16} | {phone:<15} | {maturity}")
    print("-" * 115)
    print("Para exibir a ficha completa do registro: python main.py details <CNPJ>\n")


def cmd_details(args) -> None:
    """Displays detailed company record information."""
    companies = list_companies()
    target_record = None
    cnpj_clean = args.cnpj.replace(".", "").replace("/", "").replace("-", "")
    for company in companies:
        if company["cnpj"] == cnpj_clean:
            target_record = company
            break

    if not target_record:
        print(f"Empresa com CNPJ {args.cnpj} não encontrada no banco local.")
        return

    print("\n" + "=" * 65)
    print("FICHA CADASTRAL E INDICADORES DIGITAIS")
    print("=" * 65)
    print(f"CNPJ:               {format_cnpj(target_record['cnpj'])}")
    print(f"Razão Social:       {target_record.get('legal_name')}")
    print(f"Nome Fantasia:      {target_record.get('trade_name')}")
    print(f"Situação:           {target_record.get('registration_status')}")
    print(f"CNAE Fiscal:        {target_record.get('primary_cnae')} - {target_record.get('cnae_description')}")
    print(f"Segmento:           {target_record.get('segment')}")
    print(f"Endereço:           {target_record.get('street')}, {target_record.get('number')} - {target_record.get('neighborhood')}")
    print(f"Município/UF:       {target_record.get('city')} - {target_record.get('state')} (CEP: {target_record.get('zip_code')})")
    print(f"Telefone:           {target_record.get('phone') or 'Não informado'}")
    print(f"E-mail:             {target_record.get('email') or 'Não informado'}")
    print("-" * 65)
    print("AVALIAÇÃO DE PRESENÇA DIGITAL:")
    print(f" • Maturidade:      {target_record.get('digital_maturity') or 'NO_DIGITAL_PRESENCE'}")
    print(f" • Plataforma:      {target_record.get('detected_platform') or 'None'}")
    print(f" • Domínio Web:     {target_record.get('website_domain') or 'Nenhum'}")
    has_ecom = target_record.get('has_ecommerce_cnae')
    print(f" • CNAE E-commerce: {'SIM (4791-2/01)' if has_ecom == 1 else 'NÃO'}")
    print("-" * 65)
    print(f"Status no Funil:    {target_record.get('prospecting_status')}")
    print("=" * 65 + "\n")


def cmd_status(args) -> None:
    """Updates prospecting_status column for given company CNPJ."""
    cnpj_clean = args.cnpj.replace(".", "").replace("/", "").replace("-", "")
    target_status = args.new_status.upper()
    success = update_prospecting_status(cnpj_clean, target_status)
    if success:
        print(f"Status do CNPJ {format_cnpj(cnpj_clean)} atualizado para '{target_status}'.\n")
    else:
        print(f"Empresa com CNPJ {args.cnpj} não encontrada.\n")


def cmd_outreach(args) -> None:
    """Inserts a contact interaction in outreach_history table and synchronizes company status."""
    cnpj_clean = args.cnpj.replace(".", "").replace("/", "").replace("-", "")
    target_result = args.result.upper()
    outreach_id = record_outreach(
        cnpj=cnpj_clean,
        channel=args.channel,
        result=target_result,
        notes=args.notes or "",
    )
    if outreach_id > 0:
        update_prospecting_status(cnpj_clean, target_result)
        print(f"Abordagem #{outreach_id} registrada para o CNPJ {format_cnpj(cnpj_clean)}.\n")
    else:
        print("Falha ao registrar abordagem.\n")


def cmd_export(args) -> None:
    """Exports filtered companies to a CSV file."""
    output_path = Path(args.output)
    total = export_leads_to_csv(
        output_path=output_path,
        cnae=args.cnae,
        neighborhood=args.neighborhood,
        status=args.status,
        digital_maturity=args.maturity,
    )
    if total > 0:
        print(f"Registros exportados com sucesso ({total} itens) para: {output_path}\n")
    else:
        print("Nenhum registro encontrado para exportação com os filtros informados.\n")


def cmd_metrics(args) -> None:
    """Displays statistical metrics dashboard."""
    print_metrics_dashboard()


def cmd_dashboard(args) -> None:
    """Generates an interactive HTML dashboard and optionally opens it in the browser."""
    output_path = Path(args.output) if args.output else Path("data/dashboard_leads.html")
    auto_open = not args.no_open
    generated_path = generate_html_dashboard(output_path=output_path, auto_open=auto_open)
    print(f"\n -> Painel interativo gerado com sucesso em: '{generated_path}'")
    if auto_open:
        print(" -> Abrindo no navegador padrão...")
    print(f" -> Para visualizar diretamente: abra '{generated_path}' em qualquer navegador web.\n")


def main():
    parser = argparse.ArgumentParser(
        description="Sistema de Pipeline e Gestão Comercial de Dados de CNPJ",
        epilog="Exemplos de uso:\n"
               "  python main.py run\n"
               "  python main.py run radar\n"
               "  python main.py run brasilapi --cnpj 56032902000164\n"
               "  python main.py run full\n"
               "  python main.py list\n"
               "  python main.py list --maturity NO_DIGITAL_PRESENCE\n"
               "  python main.py details 52513049000155\n"
               "  python main.py status 52513049000155 MEETING_SCHEDULED\n"
               "  python main.py outreach 52513049000155 --channel WhatsApp --result MEETING_SCHEDULED\n"
               "  python main.py metrics\n"
               "  python main.py dashboard\n"
               "  python main.py export --output data/leads.csv\n"
               "  python main.py config\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponíveis")

    # 1. Pipeline Run
    p_run = subparsers.add_parser("run", help="Executa o pipeline ETL (fontes: local, radar, brasilapi, full)")
    p_run.add_argument(
        "source",
        nargs="?",
        default="local",
        choices=["local", "radar", "brasilapi", "full"],
        help="Fonte de dados para extração (padrão: local)"
    )
    p_run.add_argument("--cnpj", help="CNPJ específico para consulta (usado no modo brasilapi)")
    p_run.add_argument("--file", help="Caminho do arquivo JSON (usado no modo radar)")

    # 2. Config
    subparsers.add_parser("config", help="Exibe os parâmetros configurados em config.json")

    # 3. List
    p_list = subparsers.add_parser("list", help="Lista empresas cadastradas no banco SQLite")
    p_list.add_argument("--cnae", help="Filtrar por código de CNAE")
    p_list.add_argument("--neighborhood", help="Filtrar por bairro")
    p_list.add_argument(
        "--status",
        choices=["NEW", "CONTACTED", "MEETING_SCHEDULED", "PROPOSAL_SENT", "CONTRACT_SIGNED", "NOT_INTERESTED"],
        help="Filtrar por status no funil de vendas"
    )
    p_list.add_argument(
        "--maturity",
        choices=["NO_DIGITAL_PRESENCE", "INSTITUTIONAL_WEBSITE", "BASIC_ECOMMERCE", "ADVANCED_ECOMMERCE"],
        help="Filtrar por maturidade digital"
    )
    p_list.add_argument("--city", help="Sobrescrever município padrão")

    # 4. Details
    p_det = subparsers.add_parser("details", help="Exibe os detalhes de um registro por CNPJ")
    p_det.add_argument("cnpj", help="Número do CNPJ da empresa")

    # 5. Status
    p_stat = subparsers.add_parser("status", help="Atualiza o status de prospecção do lead")
    p_stat.add_argument("cnpj", help="Número do CNPJ da empresa")
    p_stat.add_argument(
        "new_status",
        choices=["NEW", "CONTACTED", "MEETING_SCHEDULED", "PROPOSAL_SENT", "CONTRACT_SIGNED", "NOT_INTERESTED"],
        help="Novo status no funil de prospecção"
    )

    # 6. Outreach
    p_out = subparsers.add_parser("outreach", help="Registra uma interação de contato no histórico")
    p_out.add_argument("cnpj", help="Número do CNPJ")
    p_out.add_argument("--channel", required=True, help="Canal de comunicação (ex: WhatsApp, Telefone)")
    p_out.add_argument(
        "--result",
        required=True,
        choices=["NEW", "CONTACTED", "MEETING_SCHEDULED", "PROPOSAL_SENT", "CONTRACT_SIGNED", "NOT_INTERESTED"],
        help="Resultado da interação"
    )
    p_out.add_argument("--notes", help="Observações da abordagem comercial")

    # 7. Metrics
    subparsers.add_parser("metrics", help="Exibe painel analítico resumido com distribuição da base")

    # 8. Dashboard
    p_dash = subparsers.add_parser("dashboard", help="Gera painel visual HTML interativo com filtros e WhatsApp")
    p_dash.add_argument("--output", default="data/dashboard_leads.html", help="Caminho do arquivo HTML de saída")
    p_dash.add_argument("--no-open", action="store_true", help="Não abre o navegador automaticamente")

    # 9. Export
    p_exp = subparsers.add_parser("export", help="Exporta registros para arquivo CSV")
    p_exp.add_argument("--output", default="data/leads_londrina.csv", help="Caminho do arquivo de saída")
    p_exp.add_argument("--cnae", help="Filtrar por CNAE")
    p_exp.add_argument("--neighborhood", help="Filtrar por bairro")
    p_exp.add_argument("--status", help="Filtrar por status")
    p_exp.add_argument("--maturity", help="Filtrar por maturidade digital")

    args = parser.parse_args()

    # Route commands to handlers
    if args.command == "run":
        cmd_run(args)
    elif args.command == "config":
        cmd_config(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "details":
        cmd_details(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "outreach":
        cmd_outreach(args)
    elif args.command == "metrics":
        cmd_metrics(args)
    elif args.command == "dashboard":
        cmd_dashboard(args)
    elif args.command == "export":
        cmd_export(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

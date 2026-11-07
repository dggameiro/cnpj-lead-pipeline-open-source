"""
HTML Dashboard Generator for commercial leads presentation.
Data Engineering & Commercial Lead Intelligence.

Generates a standalone, dependency-free interactive HTML dashboard
from the SQLite database for local viewing in a web browser.
"""

import html
import json
import logging
import re
import webbrowser
from pathlib import Path
from typing import Dict, List, Optional

from src.cleaner import format_cnpj
from src.database import get_metrics, list_companies

logger = logging.getLogger(__name__)

MATURITY_TRANSLATIONS = {
    "NO_DIGITAL_PRESENCE": {
        "label": "Sem Presença Digital",
        "badge_class": "badge-danger",
        "description": "Sem domínio registrado ou plataforma identificada.",
    },
    "INSTITUTIONAL_WEBSITE": {
        "label": "Presença Institucional",
        "badge_class": "badge-warning",
        "description": "Possui domínio ativo, mas sem loja virtual.",
    },
    "BASIC_ECOMMERCE": {
        "label": "E-commerce Básico",
        "badge_class": "badge-info",
        "description": "Loja virtual ativa sem tags avançadas de tráfego.",
    },
    "ADVANCED_ECOMMERCE": {
        "label": "E-commerce Avançado",
        "badge_class": "badge-success",
        "description": "Loja estruturada com tags de mensuração e tráfego.",
    },
}

STATUS_TRANSLATIONS = {
    "NEW": "Novo",
    "CONTACTED": "Contatado",
    "MEETING_SCHEDULED": "Reunião Agendada",
    "PROPOSAL_SENT": "Proposta Enviada",
    "CONTRACT_SIGNED": "Contrato Fechado",
    "NOT_INTERESTED": "Sem Interesse",
}


def _clean_phone_number(phone_raw: Optional[str]) -> str:
    """Extracts only digits from a phone string."""
    if not phone_raw:
        return ""
    return re.sub(r"\D", "", phone_raw)


def _build_whatsapp_link(phone_raw: Optional[str], trade_name: str) -> Optional[str]:
    """
    Constructs a direct wa.me link with a pre-filled approach greeting.
    Appends the country code 55 if missing.
    """
    digits = _clean_phone_number(phone_raw)
    if len(digits) < 10:
        return None

    if not digits.startswith("55"):
        digits = f"55{digits}"

    name = trade_name or "sua empresa"
    text = (
        f"Olá! Gostaria de conversar com o responsável sobre soluções digitais "
        f"e desenvolvimento para a {name} em Londrina."
    )
    encoded_text = html.escape(text)
    return f"https://wa.me/{digits}?text={encoded_text}"


def generate_html_dashboard(
    db_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
    auto_open: bool = False,
) -> Path:
    """
    Renders companies and metrics from SQLite into a single-file interactive HTML.

    Args:
        db_path: Path to SQLite database. Defaults to database/prospeccao_comercial.db.
        output_path: Destination HTML path. Defaults to data/dashboard_leads.html.
        auto_open: If True, opens the file in the default web browser.

    Returns:
        Path to the generated HTML file.
    """
    if output_path is None:
        output_path = Path("data/dashboard_leads.html")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    companies = list_companies(db_path=db_path)
    metrics = get_metrics(db_path=db_path)

    total_companies = metrics.get("total_companies", 0)
    maturity_stats = metrics.get("by_maturity", {})
    segment_stats = metrics.get("by_segment", {})
    status_stats = metrics.get("by_status", {})

    no_digital_count = maturity_stats.get("NO_DIGITAL_PRESENCE", 0)
    institutional_count = maturity_stats.get("INSTITUTIONAL_WEBSITE", 0)
    ecommerce_count = maturity_stats.get("BASIC_ECOMMERCE", 0) + maturity_stats.get(
        "ADVANCED_ECOMMERCE", 0
    )

    # Prepare JSON dataset for client-side filtering without server
    client_records: List[Dict] = []
    unique_neighborhoods = set()
    unique_segments = set()

    for row in companies:
        maturity_key = row.get("digital_maturity") or "NO_DIGITAL_PRESENCE"
        maturity_info = MATURITY_TRANSLATIONS.get(
            maturity_key,
            {
                "label": maturity_key,
                "badge_class": "badge-secondary",
                "description": "",
            },
        )
        status_key = row.get("prospecting_status") or "NEW"
        status_label = STATUS_TRANSLATIONS.get(status_key, status_key)

        neighborhood = row.get("neighborhood") or "Não informado"
        segment = row.get("segment") or "Outro"
        trade_name = row.get("trade_name") or row.get("legal_name") or "Empresa"
        wa_link = _build_whatsapp_link(row.get("phone"), trade_name)

        unique_neighborhoods.add(neighborhood)
        unique_segments.add(segment)

        client_records.append(
            {
                "cnpj": format_cnpj(row.get("cnpj", "")),
                "legal_name": row.get("legal_name", ""),
                "trade_name": trade_name,
                "cnae": row.get("primary_cnae", ""),
                "cnae_desc": row.get("cnae_description", ""),
                "segment": segment,
                "neighborhood": neighborhood,
                "street": row.get("street", ""),
                "number": row.get("number", ""),
                "phone": row.get("phone", ""),
                "email": row.get("email", ""),
                "website_domain": row.get("website_domain") or "",
                "detected_platform": row.get("detected_platform") or "",
                "has_ecommerce_cnae": bool(row.get("has_ecommerce_cnae")),
                "maturity_key": maturity_key,
                "maturity_label": maturity_info["label"],
                "maturity_badge": maturity_info["badge_class"],
                "status_key": status_key,
                "status_label": status_label,
                "whatsapp_url": wa_link or "",
            }
        )

    json_data = json.dumps(client_records, ensure_ascii=False)
    neighborhoods_sorted = sorted([n for n in unique_neighborhoods if n])
    segments_sorted = sorted([s for s in unique_segments if s])

    html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Painel de Leads e Presença Digital - Londrina/PR</title>
<style>
  :root {{
    --bg-color: #f8fafc;
    --card-bg: #ffffff;
    --border-color: #e2e8f0;
    --text-primary: #1e293b;
    --text-muted: #64748b;
    --primary: #2563eb;
    --primary-hover: #1d4ed8;
    --success: #16a34a;
    --warning: #d97706;
    --danger: #dc2626;
    --info: #0284c7;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background-color: var(--bg-color);
    color: var(--text-primary);
    line-height: 1.5;
    padding: 24px;
  }}

  .container {{ max-width: 1280px; margin: 0 auto; }}

  header {{
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 24px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  }}

  header h1 {{ font-size: 1.5rem; font-weight: 700; color: var(--text-primary); margin-bottom: 6px; }}
  header p {{ font-size: 0.92rem; color: var(--text-muted); }}

  /* KPI Grid */
  .kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
  }}

  .kpi-card {{
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 10px;
    padding: 20px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
  }}

  .kpi-title {{ font-size: 0.85rem; font-weight: 600; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.5px; }}
  .kpi-value {{ font-size: 2rem; font-weight: 700; color: var(--text-primary); margin: 6px 0; }}
  .kpi-desc {{ font-size: 0.82rem; color: var(--text-muted); }}

  /* Controls and Filters */
  .filter-panel {{
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 24px;
  }}

  .search-row {{
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 16px;
  }}

  .search-input {{
    flex: 1;
    min-width: 260px;
    padding: 10px 14px;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    font-size: 0.95rem;
    outline: none;
  }}

  .search-input:focus {{ border-color: var(--primary); }}

  .select-filter {{
    padding: 10px 14px;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    background: #fff;
    font-size: 0.9rem;
    color: var(--text-primary);
  }}

  .btn-chips {{
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }}

  .chip {{
    padding: 6px 14px;
    border-radius: 20px;
    border: 1px solid var(--border-color);
    background: #fff;
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 500;
    transition: all 0.15s ease-in-out;
  }}

  .chip:hover {{ background: #f1f5f9; }}
  .chip.active {{ background: var(--primary); color: #fff; border-color: var(--primary); }}

  /* Table */
  .table-container {{
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 10px;
    overflow-x: auto;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  }}

  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
    text-align: left;
  }}

  thead {{ background: #f8fafc; border-bottom: 1px solid var(--border-color); }}
  th {{ padding: 14px 16px; font-weight: 600; color: var(--text-muted); font-size: 0.82rem; text-transform: uppercase; }}
  td {{ padding: 14px 16px; border-bottom: 1px solid var(--border-color); vertical-align: middle; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #f8fafc; }}

  /* Badges */
  .badge {{
    display: inline-block;
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.2px;
  }}

  .badge-danger {{ background: #fee2e2; color: #991b1b; }}
  .badge-warning {{ background: #fef3c7; color: #92400e; }}
  .badge-info {{ background: #e0f2fe; color: #075985; }}
  .badge-success {{ background: #dcfce7; color: #166534; }}
  .badge-secondary {{ background: #f1f5f9; color: #475569; }}

  /* WhatsApp Action Button */
  .btn-whatsapp {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #25d366;
    color: #fff;
    text-decoration: none;
    font-size: 0.8rem;
    font-weight: 600;
    padding: 6px 12px;
    border-radius: 6px;
    transition: background 0.15s ease;
  }}

  .btn-whatsapp:hover {{ background: #1eb956; }}
  .btn-disabled {{
    color: var(--text-muted);
    font-size: 0.8rem;
  }}

  .counter-bar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.85rem;
    color: var(--text-muted);
    margin-bottom: 12px;
  }}

  @media print {{
    body {{ background: #fff; padding: 0; }}
    .filter-panel, .btn-whatsapp {{ display: none; }}
    header, .kpi-card, .table-container {{ border: none; box-shadow: none; }}
  }}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>Painel de Prospecção Comercial e Presença Digital</h1>
    <p>Inteligência de Mercado e Qualificação Digital | Região: Londrina - PR (DDD 43)</p>
  </header>

  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-title">Total de Empresas</div>
      <div class="kpi-value">{total_companies}</div>
      <div class="kpi-desc">Base estruturada no banco SQLite</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-title">Sem Presença Digital</div>
      <div class="kpi-value" style="color: var(--danger);">{no_digital_count}</div>
      <div class="kpi-desc">Potenciais clientes para 1ª loja virtual</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-title">Presença Institucional</div>
      <div class="kpi-value" style="color: var(--warning);">{institutional_count}</div>
      <div class="kpi-desc">Têm domínio próprio, mas não vendem online</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-title">Lojas Virtuais Ativas</div>
      <div class="kpi-value" style="color: var(--success);">{ecommerce_count}</div>
      <div class="kpi-desc">Oportunidade para migração ou otimização</div>
    </div>
  </div>

  <div class="filter-panel">
    <div class="search-row">
      <input type="text" id="searchInput" class="search-input" placeholder="Buscar por Nome Fantasia, Razão Social, Bairro ou Telefone...">
      <select id="segmentSelect" class="select-filter">
        <option value="">Todos os Segmentos</option>
        {"".join(f'<option value="{html.escape(s)}">{html.escape(s)}</option>' for s in segments_sorted)}
      </select>
      <select id="neighborhoodSelect" class="select-filter">
        <option value="">Todos os Bairros</option>
        {"".join(f'<option value="{html.escape(n)}">{html.escape(n)}</option>' for n in neighborhoods_sorted)}
      </select>
    </div>

    <div class="btn-chips">
      <button class="chip active" data-maturity="">Todas as Maturidades</button>
      <button class="chip" data-maturity="NO_DIGITAL_PRESENCE">Sem Presença Digital</button>
      <button class="chip" data-maturity="INSTITUTIONAL_WEBSITE">Presença Institucional</button>
      <button class="chip" data-maturity="BASIC_ECOMMERCE">E-commerce Básico</button>
      <button class="chip" data-maturity="ADVANCED_ECOMMERCE">E-commerce Avançado</button>
    </div>
  </div>

  <div class="counter-bar">
    <span id="renderedCount">Exibindo {len(client_records)} registros</span>
    <button onclick="window.print()" style="padding: 4px 10px; font-size: 0.8rem; cursor: pointer; border: 1px solid var(--border-color); background:#fff; border-radius: 6px;">Imprimir / Salvar PDF</button>
  </div>

  <div class="table-container">
    <table>
      <thead>
        <tr>
          <th>Empresa / CNPJ</th>
          <th>Segmento</th>
          <th>Bairro / Endereço</th>
          <th>Maturidade Digital</th>
          <th>Plataforma / Site</th>
          <th>Contato</th>
          <th>Ação</th>
        </tr>
      </thead>
      <tbody id="leadsTableBody">
      </tbody>
    </table>
  </div>
</div>

<script>
  const leadsData = {json_data};
  let currentMaturityFilter = "";

  const searchInput = document.getElementById("searchInput");
  const segmentSelect = document.getElementById("segmentSelect");
  const neighborhoodSelect = document.getElementById("neighborhoodSelect");
  const tableBody = document.getElementById("leadsTableBody");
  const renderedCount = document.getElementById("renderedCount");
  const chips = document.querySelectorAll(".chip");

  chips.forEach(chip => {{
    chip.addEventListener("click", () => {{
      chips.forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      currentMaturityFilter = chip.getAttribute("data-maturity");
      renderTable();
    }});
  }});

  searchInput.addEventListener("input", renderTable);
  segmentSelect.addEventListener("change", renderTable);
  neighborhoodSelect.addEventListener("change", renderTable);

  function renderTable() {{
    const query = searchInput.value.toLowerCase().trim();
    const selectedSegment = segmentSelect.value;
    const selectedNeighborhood = neighborhoodSelect.value;

    const filtered = leadsData.filter(item => {{
      const matchesMaturity = !currentMaturityFilter || item.maturity_key === currentMaturityFilter;
      const matchesSegment = !selectedSegment || item.segment === selectedSegment;
      const matchesNeighborhood = !selectedNeighborhood || item.neighborhood === selectedNeighborhood;

      const searchableText = [
        item.trade_name,
        item.legal_name,
        item.cnpj,
        item.neighborhood,
        item.street,
        item.phone,
        item.email
      ].join(" ").toLowerCase();

      const matchesSearch = !query || searchableText.includes(query);

      return matchesMaturity && matchesSegment && matchesNeighborhood && matchesSearch;
    }});

    renderedCount.textContent = `Exibindo ${{filtered.length}} de ${{leadsData.length}} empresas`;

    if (filtered.length === 0) {{
      tableBody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 32px; color: var(--text-muted);">Nenhum lead encontrado com os filtros selecionados.</td></tr>`;
      return;
    }}

    tableBody.innerHTML = filtered.map(row => {{
      const address = [row.street, row.number].filter(Boolean).join(", ");
      const siteDisplay = row.website_domain 
        ? `<a href="http://${{row.website_domain}}" target="_blank" rel="noopener" style="color:var(--primary); text-decoration:none;">${{row.website_domain}}</a>`
        : `<span style="color:var(--text-muted);">-</span>`;
      
      const platformDisplay = row.detected_platform
        ? `<div style="font-size:0.75rem; color:var(--text-muted);">Plataforma: <b>${{row.detected_platform}}</b></div>`
        : "";

      const actionButton = row.whatsapp_url
        ? `<a class="btn-whatsapp" href="${{row.whatsapp_url}}" target="_blank" rel="noopener">WhatsApp</a>`
        : `<span class="btn-disabled">Sem WhatsApp</span>`;

      return `
        <tr>
          <td>
            <div style="font-weight:600; color:var(--text-primary);">${{row.trade_name}}</div>
            <div style="font-size:0.78rem; color:var(--text-muted);">${{row.legal_name}}</div>
            <div style="font-size:0.75rem; font-family:monospace; color:var(--text-muted);">${{row.cnpj}}</div>
          </td>
          <td>
            <span class="badge badge-secondary">${{row.segment}}</span>
          </td>
          <td>
            <div style="font-weight:500;">${{row.neighborhood}}</div>
            <div style="font-size:0.78rem; color:var(--text-muted);">${{address}}</div>
          </td>
          <td>
            <span class="badge ${{row.maturity_badge}}">${{row.maturity_label}}</span>
          </td>
          <td>
            <div>${{siteDisplay}}</div>
            ${{platformDisplay}}
          </td>
          <td>
            <div style="font-size:0.85rem; font-weight:500;">${{row.phone || "Não informado"}}</div>
            <div style="font-size:0.75rem; color:var(--text-muted);">${{row.email || ""}}</div>
          </td>
          <td>
            ${{actionButton}}
          </td>
        </tr>
      `;
    }}).join("");
  }}

  // Initial render
  renderTable();
</script>
</body>
</html>
"""

    output_path.write_text(html_content, encoding="utf-8")
    logger.info("Interactive HTML dashboard generated at: %s", output_path)

    if auto_open:
        try:
            webbrowser.open(output_path.resolve().as_uri())
        except Exception as exc:
            logger.warning("Could not auto-open browser: %s", exc)

    return output_path

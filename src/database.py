"""
Relational SQLite persistence module.
Defines schemas, tables, indexes, UPSERT operations, filtered queries,
aggregated metrics calculation, and CSV file exports.
"""

import csv
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.cleaner import format_cnpj

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "database" / "prospeccao_comercial.db"


def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Creates a connection to SQLite database with foreign keys enabled."""
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Creates tables (cnaes, companies, outreach_history) and indexes if they do not exist."""
    connection = get_db_connection(db_path)
    cursor = connection.cursor()

    # CNAEs catalog table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cnaes (
        code TEXT PRIMARY KEY,
        description TEXT NOT NULL,
        segment TEXT NOT NULL
    );
    """)

    # Companies table with digital presence attributes
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS companies (
        cnpj TEXT PRIMARY KEY,
        legal_name TEXT NOT NULL,
        trade_name TEXT,
        registration_status TEXT NOT NULL DEFAULT 'ACTIVE',
        opening_date TEXT,
        primary_cnae TEXT NOT NULL,
        street TEXT,
        number TEXT,
        neighborhood TEXT,
        city TEXT NOT NULL DEFAULT 'LONDRINA',
        state TEXT NOT NULL DEFAULT 'PR',
        zip_code TEXT,
        phone TEXT,
        email TEXT,
        prospecting_status TEXT NOT NULL DEFAULT 'NEW',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        has_ecommerce_cnae INTEGER DEFAULT 0,
        website_domain TEXT,
        detected_platform TEXT DEFAULT 'None',
        digital_maturity TEXT DEFAULT 'NO_DIGITAL_PRESENCE',
        FOREIGN KEY (primary_cnae) REFERENCES cnaes(code)
    );
    """)

    # Outreach history table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS outreach_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_cnpj TEXT NOT NULL,
        contact_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        channel TEXT NOT NULL,
        result TEXT NOT NULL,
        notes TEXT,
        FOREIGN KEY (company_cnpj) REFERENCES companies(cnpj) ON DELETE CASCADE
    );
    """)

    # Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_companies_cnae ON companies(primary_cnae);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_companies_neighborhood ON companies(neighborhood);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_companies_status ON companies(prospecting_status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_companies_maturity ON companies(digital_maturity);")

    connection.commit()
    connection.close()


def save_cnaes(cnaes: List[Dict[str, str]], db_path: Path = DEFAULT_DB_PATH) -> None:
    """Inserts or updates economic activity codes (CNAEs) in the database."""
    connection = get_db_connection(db_path)
    cursor = connection.cursor()
    records = []
    for item in cnaes:
        code = item.get("code") or item.get("codigo") or ""
        description = item.get("description") or item.get("descricao") or ""
        segment = item.get("segment") or item.get("segmento") or ""
        records.append({"code": code, "description": description, "segment": segment})

    cursor.executemany("""
    INSERT OR REPLACE INTO cnaes (code, description, segment)
    VALUES (:code, :description, :segment);
    """, records)
    connection.commit()
    connection.close()


def insert_company(company: Dict[str, Any], db_path: Path = DEFAULT_DB_PATH) -> bool:
    """Performs an UPSERT of a company record into the database."""
    payload = {
        "cnpj": company.get("cnpj"),
        "legal_name": company.get("legal_name") or company.get("razao_social"),
        "trade_name": company.get("trade_name") or company.get("nome_fantasia"),
        "registration_status": company.get("registration_status") or company.get("situacao_cadastral") or "ACTIVE",
        "opening_date": company.get("opening_date") or company.get("data_abertura"),
        "primary_cnae": company.get("primary_cnae") or company.get("cnae_fiscal"),
        "street": company.get("street") or company.get("logradouro"),
        "number": company.get("number") or company.get("numero"),
        "neighborhood": company.get("neighborhood") or company.get("bairro"),
        "city": company.get("city") or company.get("municipio") or "LONDRINA",
        "state": company.get("state") or company.get("uf") or "PR",
        "zip_code": company.get("zip_code") or company.get("cep"),
        "phone": company.get("phone") or company.get("telefone"),
        "email": company.get("email"),
        "prospecting_status": company.get("prospecting_status") or company.get("status_prospeccao") or "NEW",
        "has_ecommerce_cnae": int(company.get("has_ecommerce_cnae") or company.get("cnae_ecommerce") or 0),
        "website_domain": company.get("website_domain") or company.get("dominio_proprio"),
        "detected_platform": company.get("detected_platform") or company.get("plataforma_detectada") or "None",
        "digital_maturity": company.get("digital_maturity") or company.get("maturidade_digital") or "NO_DIGITAL_PRESENCE",
    }
    connection = get_db_connection(db_path)
    cursor = connection.cursor()
    try:
        cursor.execute("""
        INSERT INTO companies (
            cnpj, legal_name, trade_name, registration_status,
            opening_date, primary_cnae, street, number, neighborhood,
            city, state, zip_code, phone, email, prospecting_status,
            has_ecommerce_cnae, website_domain, detected_platform, digital_maturity
        ) VALUES (
            :cnpj, :legal_name, :trade_name, :registration_status,
            :opening_date, :primary_cnae, :street, :number, :neighborhood,
            :city, :state, :zip_code, :phone, :email,
            COALESCE(:prospecting_status, 'NEW'),
            COALESCE(:has_ecommerce_cnae, 0),
            :website_domain,
            COALESCE(:detected_platform, 'None'),
            COALESCE(:digital_maturity, 'NO_DIGITAL_PRESENCE')
        )
        ON CONFLICT(cnpj) DO UPDATE SET
            legal_name = excluded.legal_name,
            trade_name = excluded.trade_name,
            registration_status = excluded.registration_status,
            street = excluded.street,
            number = excluded.number,
            neighborhood = excluded.neighborhood,
            phone = excluded.phone,
            email = excluded.email,
            has_ecommerce_cnae = COALESCE(excluded.has_ecommerce_cnae, companies.has_ecommerce_cnae),
            website_domain = COALESCE(excluded.website_domain, companies.website_domain),
            detected_platform = COALESCE(excluded.detected_platform, companies.detected_platform),
            digital_maturity = COALESCE(excluded.digital_maturity, companies.digital_maturity);
        """, payload)
        connection.commit()
        return True
    finally:
        connection.close()


def list_companies(
    cnae: Optional[str] = None,
    neighborhood: Optional[str] = None,
    status: Optional[str] = None,
    digital_maturity: Optional[str] = None,
    city: Optional[str] = None,
    db_path: Path = DEFAULT_DB_PATH
) -> List[Dict[str, Any]]:
    """Queries companies table applying optional filters and returns clean canonical records."""
    connection = get_db_connection(db_path)
    cursor = connection.cursor()

    query = """
    SELECT c.*, cn.description AS cnae_description, cn.segment
    FROM companies c
    LEFT JOIN cnaes cn ON c.primary_cnae = cn.code
    WHERE 1=1
    """
    params: List[Any] = []

    if cnae:
        query += " AND c.primary_cnae = ?"
        params.append(cnae)
    if neighborhood:
        query += " AND LOWER(c.neighborhood) LIKE LOWER(?)"
        params.append(f"%{neighborhood}%")
    if status:
        query += " AND c.prospecting_status = ?"
        params.append(status)
    if digital_maturity:
        query += " AND c.digital_maturity = ?"
        params.append(digital_maturity)
    if city:
        query += " AND LOWER(c.city) = LOWER(?)"
        params.append(city)

    query += " ORDER BY c.neighborhood, c.legal_name"

    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    connection.close()
    return rows


def update_prospecting_status(cnpj: str, new_status: str, db_path: Path = DEFAULT_DB_PATH) -> bool:
    """Updates prospecting_status column for a given company CNPJ."""
    connection = get_db_connection(db_path)
    cursor = connection.cursor()
    cursor.execute("""
    UPDATE companies SET prospecting_status = ? WHERE cnpj = ?
    """, (new_status, cnpj))
    rows_affected = cursor.rowcount
    connection.commit()
    connection.close()
    return rows_affected > 0


def record_outreach(
    cnpj: str, channel: str, result: str, notes: str = "", db_path: Path = DEFAULT_DB_PATH
) -> int:
    """Inserts a record in the outreach history table and returns the generated ID."""
    connection = get_db_connection(db_path)
    cursor = connection.cursor()
    cursor.execute("""
    INSERT INTO outreach_history (company_cnpj, channel, result, notes)
    VALUES (?, ?, ?, ?)
    """, (cnpj, channel, result, notes))
    outreach_id = cursor.lastrowid or 0
    connection.commit()
    connection.close()
    return outreach_id


def get_metrics(db_path: Path = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """Calculates aggregated metrics by segment, neighborhood, status, and digital maturity."""
    connection = get_db_connection(db_path)
    cursor = connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM companies")
    total = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COALESCE(cn.segment, 'Outros') AS seg, COUNT(c.cnpj) AS qty
    FROM companies c
    LEFT JOIN cnaes cn ON c.primary_cnae = cn.code
    GROUP BY seg
    ORDER BY qty DESC
    """)
    segments = [{"segment": row[0], "quantity": row[1]} for row in cursor.fetchall()]

    cursor.execute("""
    SELECT neighborhood, COUNT(*) AS qty
    FROM companies
    GROUP BY neighborhood
    ORDER BY qty DESC
    """)
    neighborhoods = [{"neighborhood": row[0], "quantity": row[1]} for row in cursor.fetchall()]

    cursor.execute("""
    SELECT prospecting_status, COUNT(*) AS qty
    FROM companies
    GROUP BY prospecting_status
    ORDER BY qty DESC
    """)
    statuses = [{"status": row[0], "quantity": row[1]} for row in cursor.fetchall()]

    cursor.execute("""
    SELECT COALESCE(digital_maturity, 'NO_DIGITAL_PRESENCE') AS mat, COUNT(*) AS qty
    FROM companies
    GROUP BY mat
    ORDER BY qty DESC
    """)
    maturities = [{"digital_maturity": row[0], "quantity": row[1]} for row in cursor.fetchall()]

    connection.close()
    return {
        "total_companies": total,
        "segments": segments,
        "neighborhoods": neighborhoods,
        "funnel": statuses,
        "maturities": maturities,
    }


def export_leads_to_csv(
    output_path: Optional[Path] = None,
    db_path: Path = DEFAULT_DB_PATH,
    cnae: Optional[str] = None,
    neighborhood: Optional[str] = None,
    status: Optional[str] = None,
    digital_maturity: Optional[str] = None,
) -> int:
    """Exports filtered companies to a CSV file formatted with semicolon delimiter and UTF-8 with BOM."""
    if output_path is None:
        output_path = Path(__file__).resolve().parent.parent / "data" / "leads_londrina.csv"

    companies = list_companies(
        cnae=cnae,
        neighborhood=neighborhood,
        status=status,
        digital_maturity=digital_maturity,
        db_path=db_path
    )
    if not companies:
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "cnpj", "legal_name", "trade_name", "segment", "primary_cnae",
        "cnae_description", "neighborhood", "street", "number", "phone",
        "email", "prospecting_status", "digital_maturity", "detected_platform",
        "website_domain", "has_ecommerce_cnae"
    ]

    with open(output_path, "w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames, extrasaction="ignore", delimiter=";")
        writer.writeheader()
        for company in companies:
            row = dict(company)
            row["cnpj"] = format_cnpj(row["cnpj"])
            writer.writerow(row)

    return len(companies)

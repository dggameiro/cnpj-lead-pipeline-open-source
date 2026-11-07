# Pipeline de Dados Abertos de CNPJ para Mapeamento Comercial de Microempresas

Sistema profissional em Python e SQLite para coleta, higienização, enriquecimento cadastral e qualificação de presença digital de pessoas jurídicas para prospecção ativa de clientes e serviços de e-commerce.

---

## 1. Propósito do Projeto

Este projeto consiste em um pipeline de dados em Python e SQLite voltado a apoiar um desenvolvedor autônomo de software na prospecção comercial de micro e pequenas empresas em Londrina/PR.

O objetivo técnico é coletar, higienizar e estruturar dados cadastrais públicos de pessoas jurídicas (oriundos da base de Dados Abertos da Receita Federal e da BrasilAPI) e enriquecê-los com indicadores de presença digital. A ferramenta classifica cada empresa de acordo com seu nível de maturidade na web (ausência de domínio próprio, site institucional ou loja virtual ativa), permitindo direcionar abordagens comerciais para oferta de serviços de desenvolvimento e migração de e-commerce (Shopify, WooCommerce, Nuvemshop, etc.).

### Nichos de Atuação Mapeados
O sistema prioriza segmentos do comércio varejista local que possuem aderência a vendas online:
* **4781-4/00:** Comércio varejista de artigos do vestuário e acessórios (Moda).
* **4772-5/00:** Comércio varejista de cosméticos, perfumaria e higiene pessoal (Beleza).
* **4782-2/01:** Comércio varejista de calçados e bolsas.

---

## 2. Pré-requisitos e Dependências

* **Python:** Versão 3.10 ou superior.
* **Sistema Operacional:** Linux, macOS ou Windows.
* **Dependências de Software:** O projeto foi projetado utilizando exclusivamente módulos da biblioteca padrão do Python, dispensando a instalação de pacotes externos pesados:
  * `sqlite3` (persistência relacional em disco)
  * `json` e `csv` (leitura e exportação de dados)
  * `urllib.request` (consumo de APIs públicas e requisições HTTP)
  * `argparse` (interface de linha de comando - CLI)
  * `re` (expressões regulares para validação de formatos cadastrais)
  * `unittest` (suíte de testes automatizados)
* **Conexão com a Internet:** Necessária apenas caso sejam executados os modos de consulta ao vivo via BrasilAPI ou a inspeção HTTP da camada 3 de enriquecimento. Para execução com dados locais (`local`), a operação é totalmente offline.

---

## 3. Instalação e Configuração

### 3.1. Clone ou Download do Projeto
Acesse o diretório do projeto:
```bash
git clone https://github.com/dggameiro/cnpj-lead-pipeline-open-source.git
cd cnpj-lead-pipeline-open-source
```

### 3.2. Configuração do Ambiente Virtual
Recomenda-se a criação e ativação de um ambiente virtual isolado:
```bash
python3 -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate
pip install -r requirements.txt  # Confirma a ausência de dependências externas
```

### 3.3. Configuração de Parâmetros (`config.json`)
Os parâmetros operacionais do sistema estão centralizados no arquivo [`config.json`](config.json). Não é necessário alterar o código-fonte para modificar a localidade ou os nichos monitorados:

```json
{
  "location": {
    "city": "LONDRINA",
    "state": "PR",
    "default_area_code": "43",
    "priority_neighborhoods": [
      "Centro",
      "Gleba Palhano",
      "Jardim Higienópolis",
      "Shangri-Lá",
      "Vila Ipiranga"
    ]
  },
  "registration_filters": {
    "status": "ACTIVE",
    "only_with_phone": false
  },
  "target_segments": [
    {
      "code": "4781400",
      "description": "Comércio varejista de artigos do vestuário e acessórios",
      "segment": "Moda e Vestuário"
    },
    {
      "code": "4772500",
      "description": "Comércio varejista de cosméticos e perfumaria",
      "segment": "Beleza e Cosméticos"
    },
    {
      "code": "4782201",
      "description": "Comércio varejista de calçados",
      "segment": "Calçados e Bolsas"
    }
  ],
  "sales_funnel": {
    "allowed_statuses": [
      "NEW",
      "CONTACTED",
      "MEETING_SCHEDULED",
      "PROPOSAL_SENT",
      "CONTRACT_SIGNED",
      "NOT_INTERESTED"
    ],
    "outreach_channels": [
      "WhatsApp",
      "Telefone",
      "E-mail",
      "Visita Presencial"
    ]
  }
}
```

Para inspecionar a configuração carregada via linha de comando:
```bash
python main.py config
```

---

## 4. Instruções de Execução

Todas as rotinas do projeto são executadas através do ponto de entrada único [`main.py`](main.py).

### 4.1. Execução do Pipeline ETL
O pipeline executa o ciclo: **Ingestão → Higienização → Enriquecimento Digital → Persistência SQLite → Exportação CSV**.

A execução é acionada pelo comando unificado `run`:

* **Modo Padrão / Local (Offline):** Processa o conjunto de dados amostrais estruturados ([`data/seeds_sample.json`](data/seeds_sample.json)):
  ```bash
  python main.py run
  # ou explicitando a fonte:
  python main.py run local
  ```

* **Modo Radar (Dados Abertos):** Processa dados extraídos de buscas em lote via utilitários abertos da Receita Federal ([`data/export_radar_sample.json`](data/export_radar_sample.json)):
  ```bash
  python main.py run radar
  ```

* **Modo BrasilAPI (Ao Vivo):** Realiza a consulta e o enriquecimento em tempo real de empresas através de endpoints públicos da BrasilAPI:
  ```bash
  python main.py run brasilapi
  # Ou consultar diretamente um CNPJ específico:
  python main.py run brasilapi --cnpj 56032902000164
  ```

* **Modo Completo:** Executa a consolidação sequencial de todas as fontes disponíveis:
  ```bash
  python main.py run full
  ```

---

### 4.2. Consulta de Leads e Gestão de Prospecção
A CLI oferece comandos objetivos para filtragem de leads, visualização cadastral e registro de histórico comercial:

#### Listagem e Filtros
```bash
# Listar todos os registros de Londrina
python main.py list

# Filtrar por nível de maturidade digital
python main.py list --maturity NO_DIGITAL_PRESENCE
python main.py list --maturity INSTITUTIONAL_WEBSITE
python main.py list --maturity BASIC_ECOMMERCE
python main.py list --maturity ADVANCED_ECOMMERCE

# Filtrar por bairro ou código CNAE
python main.py list --neighborhood Centro
python main.py list --cnae 4781400
```

#### Detalhes Cadastrais
Exibe a ficha completa de uma empresa, incluindo endereço, canais de contato, indicadores de e-commerce e estágio no funil:
```bash
python main.py details 52513049000155
```

#### Registro de Abordagem Comercial
Registra um evento de contato na tabela relacional `outreach_history` e atualiza o status do lead:
```bash
python main.py outreach 52513049000155 --channel WhatsApp --result MEETING_SCHEDULED --notes "Agendada demonstração de loja virtual"
```

#### Atualização de Status
```bash
python main.py status 52513049000155 MEETING_SCHEDULED
```

#### Relatório e Métricas Consolidadas
Exibe no terminal a distribuição estatística da base por segmento, presença digital, bairros e status do funil:
```bash
python main.py metrics
```

#### Exportação de Dados
Gera um arquivo CSV compatível com softwares de planilha eletrônica contendo todas as colunas normalizadas:
```bash
python main.py export --output data/leads_londrina.csv
```

#### Visualização em Painel Web Interativo (Dashboard HTML)
Gera uma interface gráfica interativa (arquivo local independente de servidor web ou dependências externas) com indicadores gerais (KPIs), busca em tempo real, filtros dinâmicos por maturidade/segmento/bairro e atalho para contato imediato via WhatsApp:
```bash
python main.py dashboard
# Para gerar o arquivo sem abrir o navegador automaticamente:
python main.py dashboard --no-open
```

---

## 5. Arquitetura e Modelagem dos Dados

O projeto adota o padrão de **fronteira limpa (clean boundary)**:
1. **Domínio interno e persistência:** 100% padronizados em inglês (tabelas, colunas, variáveis e enums).
2. **Entrada e Apresentação:** Módulos adaptadores mapeiam as fontes públicas brasileiras para o schema canônico, e a CLI formata as saídas em linguagem compreensível para o usuário final.

### Estrutura do Banco de Dados SQLite (`database/prospeccao_comercial.db`)

* **`cnaes`:** Catálogo de códigos econômicos monitorados, suas descrições e o segmento de mercado atribuído.
* **`companies`:** Cadastro das empresas com dados cadastrais higienizados e indicadores de presença digital:
  * `cnpj`, `legal_name`, `trade_name`, `registration_status`, `primary_cnae`
  * `street`, `number`, `neighborhood`, `city`, `state`, `zip_code`
  * `phone`, `email`
  * `has_ecommerce_cnae` (1 ou 0 para presença do CNAE 4791-2/01)
  * `website_domain` (domínio corporativo identificado)
  * `detected_platform` (Shopify, WooCommerce, Nuvemshop, Tray, Loja Integrada, etc.)
  * `digital_maturity` (`NO_DIGITAL_PRESENCE`, `INSTITUTIONAL_WEBSITE`, `BASIC_ECOMMERCE`, `ADVANCED_ECOMMERCE`)
  * `prospecting_status` (`NEW`, `CONTACTED`, `MEETING_SCHEDULED`, etc.)
* **`outreach_history`:** Histórico de abordagens e interações comerciais registradas por CNPJ.

---

## 6. Módulo de Qualificação de Maturidade Digital

A classificação de presença digital ([`src/digital_checker.py`](src/digital_checker.py)) opera em 3 camadas sucessivas:

1. **Camada 1 (Filtro Cadastral Offline):**
   * Avalia a existência do CNAE secundário `4791-2/01` (comércio varejista via internet).
   * Analisa o provedor de e-mail cadastrado na Receita Federal. Provedores genéricos gratuitos (`@gmail.com`, `@hotmail.com`, etc.) apontam baixa probabilidade de infraestrutura digital própria. E-mails com domínio próprio são extraídos para verificação.
2. **Camada 2 (Verificação de Domínio):**
   * Checa a sintaxe e a existência de domínio web associado. Casos com ausência de domínio e e-mail gratuito recebem a classificação inicial de `NO_DIGITAL_PRESENCE`.
3. **Camada 3 (Inspeção HTTP & Fingerprint):**
   * Para domínios identificados, realiza requisições HTTP leves no HTML da página inicial.
   * Analisa assinaturas de código para detectar plataformas de e-commerce (`cdn.shopify.com`, `woocommerce`, `nuvemshop`, `tray`, etc.), elementos de carrinho/checkout e tags de mensuração de tráfego (Meta Pixel, Google Tag Manager).
   * Classifica o registro como `INSTITUTIONAL_WEBSITE`, `BASIC_ECOMMERCE` ou `ADVANCED_ECOMMERCE`.

---

## 7. Testes Automatizados

O repositório inclui testes unitários que validam isoladamente cada etapa do pipeline (leitura de configurações, higienização, banco de dados, mocks de inspeção HTTP e execução completa do fluxo):

```bash
python -m unittest tests/test_pipeline.py
```

---

## 8. Estrutura de Diretórios

```
├── config.json                            # Parâmetros de localidade, filtros e nichos
├── main.py                                # Ponto de entrada CLI e orquestração
├── requirements.txt                       # Declaração de dependências e módulos nativos
├── LICENSE                                # Termos da licença de uso (MIT)
├── README.md                              # Documentação técnica do projeto
├── data/
│   ├── cnaes_alvo.json                    # Definição dos CNAEs prioritários
│   ├── seeds_sample.json                  # Conjunto amostral estruturado de dados (offline)
│   └── export_radar_sample.json           # Amostra estruturada de extração via Receita Federal
├── database/                              # Diretório para persistência do banco SQLite
├── src/
│   ├── cleaner.py                         # Validação e higienização de CNPJ, telefones e textos
│   ├── config.py                          # Leitura e validação dos arquivos de configuração
│   ├── dashboard.py                       # Gerador de painel interativo HTML/CSS/JS (zero dependências)
│   ├── database.py                        # Persistência, operações CRUD e consultas analíticas
│   ├── digital_checker.py                 # Funil de qualificação de presença digital em 3 camadas
│   ├── extractor.py                       # Adaptadores de ingestão para diferentes fontes de dados
│   └── pipeline.py                        # Orquestração do ciclo ETL e exibição de métricas
└── tests/
    └── test_pipeline.py                   # Bateria de testes unitários automatizados
```

---

## 9. Autoria e Contato

Projeto desenvolvido por:

* **Danielle Gameiro**
* **Atuação:** Engenharia de Dados & Inteligência Comercial
* **Localidade:** Londrina, Paraná, Brasil
* **Contato:** [GitHub](https://github.com/dggameiro) | [LinkedIn](https://br.linkedin.com/in/danielle-gutschow-gameiro)

---

## 10. Licença

Este projeto é distribuído sob a licença **MIT**. Para detalhes completos sobre permissões e isenção de responsabilidade, consulte o arquivo [`LICENSE`](LICENSE).


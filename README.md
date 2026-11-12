# Divar MCP Server 🔍

An intelligent **Model Context Protocol (MCP)** server and REST API for searching, evaluating, and extracting advertisements from **[Divar](https://divar.ir)** (Iran's largest classified ads platform) using AI models.

With this server, LLMs (such as Antigravity, Claude, ChatGPT, Cursor, and custom agents) can interactively browse ads, inspect full specifications and seller descriptions, compare prices in Tomans, and apply category-specific deep filters.

---

## 🚀 Available MCP Tools

| Tool | Description |
| :--- | :--- |
| `search_divar` | Interactive multi-turn search with automatic category detection, related category suggestions, and dynamic filters (year, mileage, color, size, rent, credit, RAM, price range, etc.). |
| `get_post_details` | Retrieves complete advertisement specifications, full seller description, price, technical feature matrix, image URLs, and chat status using post token or URL. |
| `list_cities` | Search and retrieve the list of 1,177+ supported Iranian cities on Divar with their English slug and Persian name. |
| `list_categories` | Get common category slugs (vehicles, real-estate, electronic-devices, laptops, etc.) for query filtering. |

---

### 🎯 Category-Specific Filter Support

The `search_divar` tool supports deep filtering across various categories:

* **Vehicles (`light`, `cars`):**
  * `min_year` / `max_year`: Solar calendar model year (e.g. `1398` to `1402`)
  * `max_mileage`: Mileage ceiling in km (e.g. `80000`)
  * `color`: Vehicle color (white, black, silver, etc.)
  * `gearbox`: Transmission type (`manual` / `automatic`)
* **Real Estate (`residential-rent`, `residential-sell`):**
  * `min_size` / `max_size`: Area in square meters (e.g. `80`, `120`)
  * `min_credit` / `max_credit`: Deposit / Mortgage (Rahn) in Tomans
  * `min_rent` / `max_rent`: Monthly rent in Tomans
  * `has_elevator`: Elevator availability (`true` / `false`)
  * `has_parking`: Parking spot availability (`true` / `false`)
* **Electronics & Laptops (`laptops`, `mobile-phones`):**
  * `min_ram`: Minimum RAM in GB (e.g. `16` or `32`)
  * `min_storage`: Minimum storage capacity in GB (e.g. `512`)
  * `cpu`: Processor family / model

---

## 🛠️ Project Structure

```
divar-mcp/
├── src/
│   ├── __init__.py
│   ├── divar_client.py    # Direct client for Divar API + smart filtering & normalization
│   ├── mcp_server.py      # MCP tool definitions and stdio server runner
│   ├── models.py          # Pydantic data schemas
│   └── web_server.py      # FastAPI server providing REST API, OpenAPI, and SSE MCP
├── tests/
│   └── test_mcp.py        # Automated test suite for tools and filters
├── Dockerfile             # Container definition
├── docker-compose.yml     # Docker Compose service setup
├── pyproject.toml         # Package definition and entry points
├── requirements.txt       # Dependencies
├── run_server.py          # Stdio server launch script
└── README.md
```

---

## ⚙️ Installation & Quick Start

### 1. Local Environment Setup

```bash
git clone https://github.com/mjavadhm/divar-mcp.git
cd divar-mcp

python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Running Tests

```bash
pytest tests/
```

### 3. Running MCP Server (Stdio)

```bash
python3 run_server.py
```

### 4. Running Web Server (REST API + SSE MCP)

```bash
python3 -m src.web_server
```
Interactive API documentation will be available at:
* Swagger UI: `http://localhost:8000/docs`
* OpenAPI Schema: `http://localhost:8000/openapi.json`
* MCP SSE endpoint: `http://localhost:8000/mcp/sse`

---

## 🔌 Connecting to MCP Clients

### Antigravity & Claude Desktop

Add the server to your MCP configuration file (e.g. `~/.gemini/config/mcp_config.json` or `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "divar": {
      "command": "python3",
      "args": ["/root/projects/divar-mcp/run_server.py"]
    }
  }
}
```

### Cursor / Remote MCP (SSE)

When running the web server (`docker-compose up` or `python3 -m src.web_server`), configure Cursor or external MCP clients to point to:
```
http://localhost:8000/mcp/sse
```

---

## 🐳 Docker Deployment

To run containerized with Docker Compose:

```bash
docker compose up -d --build
```

---

## 📄 License

MIT License.

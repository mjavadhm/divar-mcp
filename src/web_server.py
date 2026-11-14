"""
Unified Server for Divar:
1. REST API + OpenAPI Schema for ChatGPT Custom GPT Actions
2. MCP (Streamable HTTP & SSE) for Gemini, Antigravity, Claude Desktop, Cursor, and other MCP clients
"""

import os
import sys
import contextlib
from pathlib import Path
from typing import Optional, List, Dict, Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Clean proxy environment variables to ensure direct local connection
for proxy_var in [
    "ALL_PROXY", "all_proxy",
    "HTTP_PROXY", "http_proxy",
    "HTTPS_PROXY", "https_proxy",
    "FTP_PROXY", "ftp_proxy",
]:
    os.environ.pop(proxy_var, None)

from fastapi import FastAPI, Query, HTTPException, Header, Security, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from mcp.server.transport_security import TransportSecuritySettings

from src.divar_client import DivarClient, COMMON_CATEGORIES
from src.mcp_server import mcp
from src.models import SearchResult, DivarPostDetail, CityInfo

API_KEY = os.getenv("DIVAR_API_KEY", "")  # Optional API Key protection
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: Optional[str] = Security(api_key_header)):
    if API_KEY:
        if not api_key or api_key != API_KEY:
            raise HTTPException(status_code=403, detail="Invalid or missing API Key")
    return api_key


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Run the MCP Streamable HTTP session manager lifecycle
    if hasattr(mcp, "session_manager"):
        async with mcp.session_manager.run():
            yield
    else:
        yield


app = FastAPI(
    title="Divar Assistant API & MCP",
    description=(
        "Divar (Iran) advertisement integration for AI models (Gemini Developer Mode, Antigravity, ChatGPT Actions, and MCP Clients). "
        "Search vehicles, real estate, electronics, check prices, and fetch full post details."
    ),
    version="1.3.0",
    lifespan=lifespan,
    servers=[{"url": os.getenv("SERVER_URL", "/"), "description": "Current Server"}],
)

# Enable CORS for Gemini, ChatGPT, and web apps
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rewrite_mcp_path(request, call_next):
    # Normalize /mcp without trailing slash to /mcp/ to prevent 307 redirects for POST clients
    if request.url.path == "/mcp":
        request.scope["path"] = "/mcp/"
    return await call_next(request)


client = DivarClient()


# ---------------- REST ENDPOINTS (For ChatGPT Custom Actions) ----------------

@app.get("/health", tags=["System"], summary="Health check")
async def health():
    return {"status": "ok", "service": "divar-assistant"}


@app.get(
    "/api/search",
    response_model=SearchResult,
    tags=["Divar"],
    summary="Search ads on Divar",
    description="Search Divar ads with city, category, and price range filtering in Tomans.",
    dependencies=[Depends(verify_api_key)],
)
async def search_ads(
    query: str = Query(..., description="Search keyword, e.g. 'Peugeot 206', 'MacBook', 'Saadat Abad Apartment'"),
    city: str = Query("tehran", description="City name or slug, e.g. 'tehran', 'mashhad', 'isfahan'"),
    category: Optional[str] = Query(None, description="Category slug, e.g. 'light', 'laptops', 'residential-rent'"),
    min_price: Optional[int] = Query(None, description="Minimum price in Tomans"),
    max_price: Optional[int] = Query(None, description="Maximum price in Tomans"),
    limit: int = Query(15, ge=1, le=30, description="Maximum number of results"),
):
    try:
        return await client.search(
            query=query,
            city=city,
            category=category,
            min_price=min_price,
            max_price=max_price,
            limit=limit,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get(
    "/api/posts/{token}",
    response_model=DivarPostDetail,
    tags=["Divar"],
    summary="Get ad details",
    description="Retrieve all technical specifications, seller description, images, and price using post token.",
    dependencies=[Depends(verify_api_key)],
)
async def get_post(token: str):
    try:
        return await client.get_post_details(token)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/cities",
    tags=["Metadata"],
    summary="List supported cities",
    dependencies=[Depends(verify_api_key)],
)
async def list_cities(query: Optional[str] = Query(None, description="Filter by city name or slug")):
    cities = await client.fetch_cities()
    if query:
        q = query.strip().lower()
        cities = [c for c in cities if q in c.name.lower() or q in c.slug.lower()]
    return {"cities": [c.model_dump() for c in cities[:50]]}


@app.get(
    "/api/categories",
    tags=["Metadata"],
    summary="List common categories",
    dependencies=[Depends(verify_api_key)],
)
async def list_categories():
    return {"categories": COMMON_CATEGORIES}


# ---------------- MCP MOUNT (Streamable HTTP for Gemini, Antigravity, and Claude) ----------------
try:
    # Disable DNS rebinding checks to allow reverse proxies, tunnels, and remote hosts
    security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    mcp_streamable_app = mcp.streamable_http_app(streamable_http_path="/", transport_security=security)
    app.mount("/mcp", mcp_streamable_app)
except Exception as mcp_err:
    print(f"Warning: Failed to mount MCP Streamable HTTP app: {mcp_err}")


def main():
    import uvicorn
    port = int(os.getenv("PORT", 8765))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"Starting Divar Unified Server on http://{host}:{port}")
    print(f"Swagger Docs / OpenAPI: http://{host}:{port}/docs")
    print(f"OpenAPI Schema for ChatGPT: http://{host}:{port}/openapi.json")
    print(f"MCP Streamable HTTP Endpoint (Gemini & Antigravity): http://{host}:{port}/mcp")
    uvicorn.run("src.web_server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()

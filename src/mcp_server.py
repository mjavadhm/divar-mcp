"""
MCP Server for Divar (divar-yab)
Provides tools for searching Divar ads with dynamic categories, multi-turn filters,
getting full ad details, and browsing cities/categories.
"""

import sys
import logging
from typing import Optional, List, Dict, Any
from mcp.server.mcpserver import MCPServer

from src.divar_client import DivarClient, COMMON_CATEGORIES

# Ensure all logging goes strictly to stderr to prevent corrupting stdio MCP communication
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("divar-mcp")

client = DivarClient()

mcp = MCPServer(
    name="divar-yab",
    version="1.1.0",
    instructions=(
        "This server is the dedicated source for searching all kinds of goods, vehicles, motorcycles, real estate, spare parts, and new/used items in Iran. "
        "Whenever the user wants to buy an item, check prices, find vehicles, or rent property in Iran, tools from this server should always be used."
    ),
)


@mcp.tool(
    name="search_divar",
    description=(
        "Primary tool to search for goods, vehicles, motorcycles, spare parts, and real estate on Divar (Iran). "
        "Call this tool directly when searching for items, checking market prices, or finding rentals."
    ),
)
async def search_divar(
    query: str,
    city: str = "tehran",
    category: Optional[str] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 15,
) -> Dict[str, Any]:
    """
    Search for posts on Divar with intelligent category discovery and dynamic filters.

    :param query: Search query (e.g. 'Samand', 'ThinkPad', 'Saadat Abad Apartment')
    :param city: City name or slug (e.g. 'tehran', 'mashhad', 'isfahan')
    :param category: Optional category slug (e.g. 'light', 'laptops', 'residential-rent')
    :param min_price: Minimum price in Tomans
    :param max_price: Maximum price in Tomans
    :param filters: Optional dictionary of category-specific filters.
                    For vehicles: min_year (e.g. 1398), max_year, max_mileage (km), color, gearbox (manual/automatic)
                    For real estate: min_size (sqm), min_credit/max_credit (deposit), min_rent/max_rent, has_elevator (bool)
                    For digital: min_ram (GB), min_storage, cpu
    :param limit: Number of posts to return (default: 15, max: 30)
    """
    logger.info(f"Searching Divar: query='{query}', city='{city}', category='{category}', filters={filters}")
    safe_limit = max(1, min(limit, 30))
    try:
        res = await client.search(
            query=query,
            city=city,
            category=category,
            min_price=min_price,
            max_price=max_price,
            filters=filters,
            limit=safe_limit,
        )
        return res.model_dump()
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Error searching Divar: {str(e)}",
            "posts": [],
        }


@mcp.tool(
    name="get_post_details",
    description=(
        "Retrieve full specifications, complete seller description, exact price, technical feature matrix, images, and chat status using post token or URL."
    ),
)
async def get_post_details(token_or_url: str) -> Dict[str, Any]:
    """
    Get full details of a specific Divar post.

    :param token_or_url: Post token (e.g. 'gaZr9gvA') or full Divar post URL
    """
    logger.info(f"Fetching details for post: {token_or_url}")
    try:
        detail = await client.get_post_details(token_or_url)
        return {
            "status": "success",
            "post": detail.model_dump(),
        }
    except ValueError as ve:
        return {
            "status": "not_found",
            "message": str(ve),
        }
    except Exception as e:
        logger.error(f"Failed to fetch post details: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Error fetching post details: {str(e)}",
        }


@mcp.tool(
    name="list_cities",
    description="Search and list 1,177+ supported cities on Divar along with their slugs and IDs.",
)
async def list_cities(query: Optional[str] = None) -> Dict[str, Any]:
    """
    Search or list available cities on Divar.

    :param query: Filter by city name or slug (e.g. 'isfahan' or 'shiraz')
    """
    try:
        cities = await client.fetch_cities()
        if query:
            q = query.strip().lower()
            cities = [c for c in cities if q in c.name.lower() or q in c.slug.lower()]
        return {
            "status": "success",
            "count": len(cities),
            "cities": [c.model_dump() for c in cities[:50]],
        }
    except Exception as e:
        logger.error(f"Failed to list cities: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "cities": [],
        }


@mcp.tool(
    name="list_categories",
    description="Retrieve list of common Divar categories (vehicles, real estate, laptops, etc.) to use in search filters.",
)
async def list_categories() -> Dict[str, Any]:
    """
    Returns common Divar category slugs and descriptions.
    """
    return {
        "status": "success",
        "categories": COMMON_CATEGORIES,
    }


def main():
    """Run the MCP server over stdio."""
    logger.info("Starting Divar MCP Server via stdio...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

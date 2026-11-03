"""
MCP Server for Divar (divar-yab)
Provides tools for searching Divar ads, getting full ad details, and browsing cities/categories.
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
    version="1.0.0",
    instructions=(
        "این سرور امکان جستجو در میان صدها هزار آگهی دیوار (Divar.ir)، "
        "بررسی قیمت‌ها، خواندن توضیحات کامل آگهی‌ها و مشخصات فنی آن‌ها را فراهم می‌کند. "
        "می‌توانید برای کاربران آگهی‌ها را پیدا کرده، کیفیت و ارزش خرید آن‌ها را مقایسه کنید."
    ),
)


@mcp.tool(
    name="search_divar",
    description=(
        "جستجو در آگهی‌های دیوار بر اساس عنوان، شهر، دسته‌بندی و بازه قیمت. "
        "خروجی شامل لیستی از آگهی‌ها به همراه عنوان، قیمت، محله، توکن آگهی و لینک مستقیم است."
    ),
)
async def search_divar(
    query: str,
    city: str = "tehran",
    category: Optional[str] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    limit: int = 15,
) -> Dict[str, Any]:
    """
    Search for posts on Divar.

    :param query: متن جستجو (مثلاً 'مک بوک m1'، 'پراید ۹۵'، 'آپارتمان دو خوابه')
    :param city: نام یا اسلاگ شهر (مثلاً 'tehran', 'تهران', 'mashhad', 'مشهد', 'shiraz')
    :param category: اسلاگ دسته‌بندی اختیاری (مثلاً 'laptops', 'auto', 'electronic-devices')
    :param min_price: حداقل قیمت به تومان
    :param max_price: حداکثر قیمت به تومان
    :param limit: تعداد آگهی‌های بازگشتی (پیش‌فرض ۱۵، حداکثر ۳۰)
    """
    logger.info(f"Searching Divar: query='{query}', city='{city}', category='{category}'")
    safe_limit = max(1, min(limit, 30))
    try:
        posts = await client.search(
            query=query,
            city=city,
            category=category,
            min_price=min_price,
            max_price=max_price,
            limit=safe_limit,
        )
        return {
            "status": "success",
            "query": query,
            "city": city,
            "count": len(posts),
            "posts": [post.model_dump() for post in posts],
        }
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"خطا در جستجوی دیوار: {str(e)}",
            "posts": [],
        }


@mcp.tool(
    name="get_post_details",
    description=(
        "دریافت تمام مشخصات، توضیحات کامل فروشنده، قیمت دقیق و ویژگی‌های یک آگهی دیوار با استفاده از توکن یا لینک آگهی."
    ),
)
async def get_post_details(token_or_url: str) -> Dict[str, Any]:
    """
    Get full details of a specific Divar post.

    :param token_or_url: توکن آگهی (مانند 'gaZr9gvA') یا آدرس کامل آگهی در دیوار
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
            "message": f"خطا در دریافت مشخصات آگهی: {str(e)}",
        }


@mcp.tool(
    name="list_cities",
    description="جستجو و دریافت لیست شهرهای پشتیبانی‌شده در دیوار همراه با اسلاگ و شناسه آن‌ها.",
)
async def list_cities(query: Optional[str] = None) -> Dict[str, Any]:
    """
    Search or list available cities in Divar.

    :param query: فیلتر کردن بر اساس نام شهر یا اسلاگ (مثلاً 'اصفهان' یا 'shiraz')
    """
    try:
        cities = await client.fetch_cities()
        if query:
            q = query.strip().lower()
            cities = [c for c in cities if q in c.name.lower() or q in c.slug.lower()]
        return {
            "status": "success",
            "count": len(cities),
            "cities": [c.model_dump() for c in cities[:50]],  # cap to top 50
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
    description="دریافت لیست دسته‌بندی‌های متداول دیوار (مانند لپ‌تاپ، خودرو، املاک) جهت استفاده در فیلتر جستجو.",
)
async def list_categories() -> Dict[str, Any]:
    """
    Returns common Divar category slugs and their Persian descriptions.
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

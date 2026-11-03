"""
Tests for Divar Client and MCP Server
"""

import pytest
import asyncio
from src.divar_client import DivarClient, normalize_persian_numbers, parse_price_to_toman, parse_number
from src.mcp_server import mcp, search_divar, get_post_details, list_cities, list_categories


def test_persian_number_utils():
    assert normalize_persian_numbers("۱۲۳۴۵") == "12345"
    assert parse_price_to_toman("۳۵,۰۰۰,۰۰۰ تومان") == 35000000
    assert parse_number("۱۲۰,۰۰۰ کیلومتر") == 120000
    assert parse_number("۱۳۹۸") == 1398
    assert parse_price_to_toman(None) is None


@pytest.mark.asyncio
async def test_divar_client_city_resolution():
    client = DivarClient()
    tehran = await client.resolve_city("تهران")
    assert tehran.id == 1
    assert tehran.slug == "tehran"

    shiraz = await client.resolve_city("shiraz")
    assert shiraz.slug == "shiraz"


@pytest.mark.asyncio
async def test_mcp_list_categories():
    res = await list_categories()
    assert res["status"] == "success"
    assert "laptops" in res["categories"]
    assert "light" in res["categories"]


@pytest.mark.asyncio
async def test_mcp_list_cities():
    res = await list_cities(query="تبریز")
    assert res["status"] == "success"
    assert any(c["name"] == "تبریز" for c in res["cities"])


@pytest.mark.asyncio
async def test_mcp_search_category_detection_samand():
    # Test that searching 'سمند' auto-detects 'light' and suggests related categories (parts-accessories)
    res = await search_divar(query="سمند", city="tehran", limit=5)
    assert res["status"] == "success"
    assert res["active_category"] is not None
    assert res["active_category"]["slug"] in ("light", "cars", "vehicles")
    assert len(res["available_filters"]) > 0
    # Related categories should include parts / services
    related_slugs = [rc["slug"] for rc in res["related_categories"]]
    assert any("parts" in s or "car" in s or "transport" in s for s in related_slugs)


@pytest.mark.asyncio
async def test_mcp_search_with_deep_filters():
    # Test car search with year filter
    res = await search_divar(
        query="پژو 206",
        city="tehran",
        filters={"min_year": 1395, "max_year": 1402},
        limit=5
    )
    assert res["status"] == "success"
    assert "posts" in res


@pytest.mark.asyncio
async def test_mcp_get_post_details():
    search_res = await search_divar(query="کتاب", city="tehran", limit=1)
    if search_res["posts"]:
        token = search_res["posts"][0]["token"]
        detail_res = await get_post_details(token)
        assert detail_res["status"] == "success"
        assert "post" in detail_res
        assert detail_res["post"]["token"] == token
        assert "title" in detail_res["post"]

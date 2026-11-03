"""
Tests for Divar Client and MCP Server
"""

import pytest
import asyncio
from src.divar_client import DivarClient, normalize_persian_numbers, parse_price_to_toman
from src.mcp_server import mcp, search_divar, get_post_details, list_cities, list_categories


def test_persian_number_utils():
    assert normalize_persian_numbers("۱۲۳۴۵") == "12345"
    assert parse_price_to_toman("۳۵,۰۰۰,۰۰۰ تومان") == 35000000
    assert parse_price_to_toman(None) is None
    assert parse_price_to_toman("توافقی") is None


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
    assert "auto" in res["categories"]


@pytest.mark.asyncio
async def test_mcp_list_cities():
    res = await list_cities(query="تبریز")
    assert res["status"] == "success"
    assert any(c["name"] == "تبریز" for c in res["cities"])


@pytest.mark.asyncio
async def test_mcp_search_divar():
    res = await search_divar(query="مانیتور", city="tehran", limit=5)
    assert res["status"] == "success"
    assert len(res["posts"]) > 0
    first_post = res["posts"][0]
    assert "token" in first_post
    assert "url" in first_post
    assert "title" in first_post


@pytest.mark.asyncio
async def test_mcp_get_post_details():
    # First search for a live post to test detail fetching
    search_res = await search_divar(query="کتاب", city="tehran", limit=1)
    if search_res["posts"]:
        token = search_res["posts"][0]["token"]
        detail_res = await get_post_details(token)
        assert detail_res["status"] == "success"
        assert "post" in detail_res
        assert detail_res["post"]["token"] == token
        assert "title" in detail_res["post"]

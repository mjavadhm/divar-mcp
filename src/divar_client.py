"""
Divar HTTP Client for searching posts, fetching details, and querying metadata.
"""

import re
import json
import logging
from typing import Optional, List, Dict, Any, Tuple
import httpx

from src.models import CityInfo, DivarPostSummary, DivarPostDetail

logger = logging.getLogger(__name__)

DIVAR_BASE_URL = "https://api.divar.ir"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# Common categories map for convenience
COMMON_CATEGORIES = {
    "laptops": {"name": "رایانه همراه (لپ‌تاپ)", "slug": "laptops", "parent": "electronic-devices"},
    "mobile-phones": {"name": "گوشی موبایل", "slug": "mobile-phones", "parent": "electronic-devices"},
    "electronic-devices": {"name": "کالای دیجیتال", "slug": "electronic-devices"},
    "computers": {"name": "رایانه و قطعات", "slug": "computers", "parent": "electronic-devices"},
    "auto": {"name": "خودرو سواری", "slug": "auto", "parent": "vehicles"},
    "vehicles": {"name": "وسایل نقلیه", "slug": "vehicles"},
    "motorcycles": {"name": "موتورسیکلت", "slug": "motorcycles", "parent": "vehicles"},
    "buy-residential": {"name": "خرید و فروش خانه و آپارتمان", "slug": "buy-residential", "parent": "real-estate"},
    "rent-residential": {"name": "رهن و اجاره خانه و آپارتمان", "slug": "rent-residential", "parent": "real-estate"},
    "real-estate": {"name": "املاک", "slug": "real-estate"},
    "home-kitchen": {"name": "لوازم خانگی", "slug": "home-kitchen"},
    "appliances": {"name": "وسایل برقی خانگی", "slug": "appliances", "parent": "home-kitchen"},
}

PERSIAN_TO_ENGLISH_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalize_persian_numbers(text: str) -> str:
    """Converts Persian/Arabic numerals to standard digits."""
    return text.translate(PERSIAN_TO_ENGLISH_DIGITS)


def parse_price_to_toman(price_str: Optional[str]) -> Optional[int]:
    """
    Tries to extract a numeric price in Tomans from a string like '۵۰,۰۰۰,۰۰۰ تومان'.
    """
    if not price_str:
        return None
    normalized = normalize_persian_numbers(price_str)
    # Remove all non-digit characters except for digit sequences
    digits = re.sub(r"[^\d]", "", normalized)
    if digits:
        try:
            return int(digits)
        except ValueError:
            return None
    return None


class DivarClient:
    """Asynchronous client for Divar Web API."""

    def __init__(self, timeout: float = 12.0):
        self.timeout = timeout
        self.headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self._cities_cache: Optional[List[CityInfo]] = None
        self._city_lookup: Optional[Dict[str, CityInfo]] = None

    async def _get_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.timeout, headers=self.headers)

    async def fetch_cities(self) -> List[CityInfo]:
        """Fetches and caches the list of all cities from Divar API."""
        if self._cities_cache:
            return self._cities_cache

        url = f"{DIVAR_BASE_URL}/v8/places/cities"
        async with await self._get_client() as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
                cities_raw = data.get("cities", [])
                cities = [
                    CityInfo(
                        id=c["id"],
                        name=c["name"],
                        slug=c["slug"]
                    )
                    for c in cities_raw if "id" in c and "name" in c and "slug" in c
                ]
                self._cities_cache = cities
                self._city_lookup = {}
                for c in cities:
                    self._city_lookup[c.slug.lower()] = c
                    self._city_lookup[c.name.strip()] = c
                return cities
            except Exception as e:
                logger.warning(f"Failed to fetch cities from API: {e}. Falling back to default list.")
                # Fallback to major cities
                fallback = [
                    CityInfo(id=1, name="تهران", slug="tehran"),
                    CityInfo(id=2, name="مشهد", slug="mashhad"),
                    CityInfo(id=3, name="کرج", slug="karaj"),
                    CityInfo(id=4, name="اصفهان", slug="isfahan"),
                    CityInfo(id=5, name="تبریز", slug="tabriz"),
                    CityInfo(id=6, name="شیراز", slug="shiraz"),
                    CityInfo(id=7, name="اهواز", slug="ahvaz"),
                    CityInfo(id=8, name="قم", slug="qom"),
                    CityInfo(id=9, name="کرمانشاه", slug="kermanshah"),
                    CityInfo(id=12, name="رشت", slug="rasht"),
                    CityInfo(id=16, name="یزد", slug="yazd"),
                ]
                self._cities_cache = fallback
                self._city_lookup = {c.slug.lower(): c for c in fallback}
                self._city_lookup.update({c.name.strip(): c for c in fallback})
                return fallback

    async def resolve_city(self, city_name_or_slug: str) -> CityInfo:
        """Resolves city identifier (Persian name or slug) to a CityInfo object."""
        if not self._city_lookup:
            await self.fetch_cities()

        cleaned = city_name_or_slug.strip().lower()
        if cleaned in self._city_lookup:
            return self._city_lookup[cleaned]

        # Partial matching if not exact match
        for key, city in self._city_lookup.items():
            if cleaned in key or key in cleaned:
                return city

        # Default fallback to Tehran
        return CityInfo(id=1, name="تهران", slug="tehran")

    async def search(
        self,
        query: str,
        city: str = "tehran",
        category: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        limit: int = 20,
    ) -> List[DivarPostSummary]:
        """
        Search posts on Divar.

        Args:
            query: Keyword to search for (e.g. 'مک بوک m1')
            city: City name or slug (e.g. 'tehran', 'تهران')
            category: Optional category slug (e.g. 'laptops', 'auto', 'electronic-devices')
            min_price: Minimum price in Tomans
            max_price: Maximum price in Tomans
            limit: Maximum items to return
        """
        city_info = await self.resolve_city(city)

        form_data: Dict[str, Any] = {}
        if category:
            form_data["category"] = {"str": {"value": category}}

        if min_price or max_price:
            price_range: Dict[str, int] = {}
            if min_price is not None:
                price_range["minimum"] = int(min_price)
            if max_price is not None:
                price_range["maximum"] = int(max_price)
            form_data["price"] = {"number_range": price_range}

        payload: Dict[str, Any] = {
            "city_ids": [str(city_info.id)],
            "search_data": {
                "query": query,
                "form_data": {"data": form_data} if form_data else {},
            },
        }

        url = f"{DIVAR_BASE_URL}/v8/postlist/w/search"
        async with await self._get_client() as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        # Build token -> offers price mapping from seo_details if available
        seo_prices: Dict[str, int] = {}
        linked_data = data.get("seo_details", {}).get("linked_data", [])
        for item in linked_data:
            item_url = item.get("url", "")
            token_match = re.search(r"/([a-zA-Z0-9_\-]+)$", item_url)
            if token_match:
                token = token_match.group(1)
                offers = item.get("offers", {})
                price_val = offers.get("price")
                if price_val and str(price_val).isdigit():
                    # Divar schema.org price is in Rials -> divide by 10 for Tomans
                    seo_prices[token] = int(price_val) // 10

        results: List[DivarPostSummary] = []
        widgets = data.get("list_widgets", [])

        for w in widgets:
            if w.get("widget_type") != "POST_ROW":
                continue

            w_data = w.get("data", {})
            action = w_data.get("action", {}) or w.get("action", {})
            token = action.get("payload", {}).get("token") or w_data.get("token")
            if not token:
                continue

            title = w_data.get("title") or "بدون عنوان"
            middle_desc = w_data.get("middle_description_text")  # usually price
            top_desc = w_data.get("top_description_text")        # condition / spec
            bottom_desc = w_data.get("bottom_description_text")  # time & district

            # Try to get numeric price
            price_toman = seo_prices.get(token) or parse_price_to_toman(middle_desc)

            # Client-side price filter verification
            if min_price is not None and price_toman is not None and price_toman < min_price:
                continue
            if max_price is not None and price_toman is not None and price_toman > max_price:
                continue

            # Extract image
            img_url = w_data.get("image_url")
            if not img_url and w_data.get("image_urls"):
                img_url = w_data["image_urls"][0]

            # Parse district from bottom_desc (e.g. "در سعادت‌آباد" or "نیم ساعت پیش در جردن")
            district = None
            time_text = bottom_desc
            if bottom_desc and " در " in bottom_desc:
                parts = bottom_desc.split(" در ")
                time_text = parts[0].strip()
                district = parts[1].strip()

            post = DivarPostSummary(
                token=token,
                title=title,
                price=middle_desc,
                price_toman=price_toman,
                district=district,
                city=city_info.name,
                time_text=time_text,
                image_url=img_url,
                url=f"https://divar.ir/v/{token}"
            )
            results.append(post)

            if len(results) >= limit:
                break

        return results

    async def get_post_details(self, token_or_url: str) -> DivarPostDetail:
        """
        Fetches full details of a specific Divar post.

        Args:
            token_or_url: Either a post token (e.g. 'gaZr9gvA') or a full Divar URL.
        """
        # Extract token if a full URL was passed
        token = token_or_url.strip()
        url_match = re.search(r"/([a-zA-Z0-9_\-]+)/?$", token)
        if "/" in token and url_match:
            token = url_match.group(1)

        url = f"{DIVAR_BASE_URL}/v8/posts-v2/web/{token}"
        async with await self._get_client() as client:
            resp = await client.get(url)
            if resp.status_code == 404:
                raise ValueError(f"آگهی با توکن '{token}' در دیوار پیدا نشد (احتمالاً حذف یا منقضی شده است).")
            resp.raise_for_status()
            data = resp.json()

        title = ""
        description = ""
        specs: Dict[str, str] = {}
        images: List[str] = []
        price_str: Optional[str] = None
        district: Optional[str] = None
        published_time: Optional[str] = None
        city = data.get("city", {}).get("name") if isinstance(data.get("city"), dict) else None

        sections = data.get("sections", [])
        for sec in sections:
            widgets = sec.get("widgets", [])
            for w in widgets:
                w_type = w.get("widget_type")
                w_data = w.get("data", {})

                if w_type == "LEGEND_TITLE_ROW":
                    title = w_data.get("title") or title
                    subtitle = w_data.get("subtitle")
                    if subtitle:
                        published_time = subtitle

                elif w_type == "DESCRIPTION_ROW":
                    text = w_data.get("text")
                    if text:
                        description = (description + "\n\n" + text).strip() if description else text

                elif w_type in ("UNEXPANDABLE_ROW", "GROUP_INFO_ROW"):
                    prop_title = w_data.get("title")
                    prop_val = w_data.get("value")
                    if prop_title and prop_val:
                        specs[prop_title.strip()] = str(prop_val).strip()
                        if "قیمت" in prop_title:
                            price_str = str(prop_val).strip()

                elif w_type == "IMAGE_CAROUSEL":
                    items = w_data.get("items", [])
                    for img in items:
                        img_url = img.get("image", {}).get("url")
                        if img_url:
                            images.append(img_url)

                elif w_type == "LOCATION_ROW":
                    district = w_data.get("district")

        # Fallback for title from SEO if not parsed
        if not title:
            title = data.get("seo", {}).get("title") or "بدون عنوان"

        # Check contact chat availability
        chat_enabled = False
        contact_info = data.get("contact", {})
        if contact_info.get("chat_enabled"):
            chat_enabled = True

        price_toman = parse_price_to_toman(price_str)

        return DivarPostDetail(
            token=token,
            title=title,
            url=f"https://divar.ir/v/{token}",
            city=city,
            district=district,
            price=price_str,
            price_toman=price_toman,
            description=description,
            specifications=specs,
            images=images,
            published_time=published_time,
            chat_enabled=chat_enabled,
            raw_data=None  # Can be populated if needed
        )

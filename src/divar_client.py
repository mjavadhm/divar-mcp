"""
Divar HTTP Client for searching posts, fetching details, and querying metadata.
"""

import re
import json
import asyncio
import logging
from typing import Optional, List, Dict, Any, Tuple
import httpx

from src.models import CityInfo, CategoryMeta, DivarPostSummary, DivarPostDetail, SearchResult

logger = logging.getLogger(__name__)

DIVAR_BASE_URL = "https://api.divar.ir"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# Common categories map for convenience
COMMON_CATEGORIES = {
    "light": {"name": "خودرو سواری و وانت", "slug": "light", "parent": "vehicles"},
    "cars": {"name": "خودرو سواری", "slug": "cars", "parent": "vehicles"},
    "parts-accessories": {"name": "قطعات یدکی و لوازم جانبی خودرو", "slug": "parts-accessories", "parent": "vehicles"},
    "laptops": {"name": "رایانه همراه (لپ‌تاپ)", "slug": "laptops", "parent": "electronic-devices"},
    "mobile-phones": {"name": "گوشی موبایل", "slug": "mobile-phones", "parent": "electronic-devices"},
    "electronic-devices": {"name": "کالای دیجیتال", "slug": "electronic-devices"},
    "residential-rent": {"name": "رهن و اجاره آپارتمان", "slug": "residential-rent", "parent": "real-estate"},
    "residential-sell": {"name": "خرید و فروش آپارتمان", "slug": "residential-sell", "parent": "real-estate"},
    "real-estate": {"name": "املاک", "slug": "real-estate"},
    "home-kitchen": {"name": "لوازم خانگی", "slug": "home-kitchen"},
}

PERSIAN_TO_ENGLISH_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalize_persian_numbers(text: str) -> str:
    """Converts Persian/Arabic numerals to standard digits."""
    return text.translate(PERSIAN_TO_ENGLISH_DIGITS)


def parse_number(val: Any) -> Optional[int]:
    """Extracts integer value from a string containing numbers."""
    if val is None:
        return None
    normalized = normalize_persian_numbers(str(val))
    digits = re.sub(r"[^\d]", "", normalized)
    return int(digits) if digits else None


def parse_price_to_toman(price_str: Optional[str]) -> Optional[int]:
    """Tries to extract a numeric price in Tomans from a string like '۵۰,۰۰۰,۰۰۰ تومان'."""
    return parse_number(price_str)


def get_available_filters_for_category(category_slug: Optional[str]) -> List[str]:
    """Returns list of applicable human-readable filter keys for a category."""
    if not category_slug:
        return [
            "حداقل قیمت تومان (min_price)",
            "حداکثر قیمت تومان (max_price)",
        ]
    cat = category_slug.lower()
    if any(k in cat for k in ("cars", "light", "auto", "vehicles")):
        return [
            "حداقل سال ساخت شمسی (min_year: مثلاً 1398)",
            "حداکثر سال ساخت شمسی (max_year: مثلاً 1402)",
            "سقف کارکرد کیلومتر (max_mileage: مثلاً 80000)",
            "رنگ (color: سفید، مشکی، نقره‌ای، خاکستری و...)",
            "گیربکس (gearbox: دنده‌ای یا اتوماتیک)",
            "وضعیت بدنه (body_status: بدون رنگ، دوررنگ، خط و خش جزئی)",
            "حداقل قیمت تومان (min_price)",
            "حداکثر قیمت تومان (max_price)",
        ]
    elif any(r in cat for r in ("residential", "commercial", "real-estate", "rent", "sell")):
        return [
            "حداقل متراژ به متر (min_size: مثلاً 80)",
            "حداکثر متراژ به متر (max_size: مثلاً 120)",
            "ودیعه یا رهن به تومان (min_credit / max_credit)",
            "اجاره ماهیانه به تومان (min_rent / max_rent)",
            "تعداد اتاق (rooms: 1, 2, 3)",
            "آسانسور (has_elevator: true/false)",
            "پارکینگ (has_parking: true/false)",
            "انباری (has_warehouse: true/false)",
        ]
    elif any(d in cat for d in ("laptops", "mobile", "tablet", "computer", "electronic")):
        return [
            "حداقل رم گیگابایت (min_ram: مثلاً 16 یا 32)",
            "حداقل حافظه داخلی گیگابایت (min_storage: مثلاً 256 یا 512)",
            "پردازنده (cpu: مثلاً Ryzen 7 یا Core i7)",
            "وضعیت دستگاه (condition: نو، در حد نو، کارکرده)",
            "حداقل قیمت تومان (min_price)",
            "حداکثر قیمت تومان (max_price)",
        ]
    else:
        return [
            "حداقل قیمت تومان (min_price)",
            "حداکثر قیمت تومان (max_price)",
            "وضعیت کالا (condition: نو، در حد نو، کارکرده)",
        ]


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
        # trust_env=False ensures direct connection to Divar, completely bypassing system VPN/proxy
        return httpx.AsyncClient(timeout=self.timeout, headers=self.headers, trust_env=False)

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

        for key, city in self._city_lookup.items():
            if cleaned in key or key in cleaned:
                return city

        return CityInfo(id=1, name="تهران", slug="tehran")

    async def search(
        self,
        query: str,
        city: str = "tehran",
        category: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 15,
    ) -> SearchResult:
        """
        Search posts on Divar with dynamic categories and filters.

        Args:
            query: Keyword to search for (e.g. 'سمند', 'مک بوک m1')
            city: City name or slug (e.g. 'tehran', 'تهران')
            category: Optional category slug (e.g. 'light', 'laptops')
            min_price: Minimum price in Tomans
            max_price: Maximum price in Tomans
            filters: Optional dict of category-specific filters (min_year, max_mileage, color, etc.)
            limit: Maximum items to return
        """
        city_info = await self.resolve_city(city)
        active_filters = filters or {}

        form_data: Dict[str, Any] = {}
        if category:
            form_data["category"] = {"str": {"value": category}}

        # Price range filter
        effective_min_price = min_price if min_price is not None else active_filters.get("min_price")
        effective_max_price = max_price if max_price is not None else active_filters.get("max_price")

        if effective_min_price or effective_max_price:
            price_range: Dict[str, int] = {}
            if effective_min_price is not None:
                price_range["minimum"] = int(effective_min_price)
            if effective_max_price is not None:
                price_range["maximum"] = int(effective_max_price)
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

        # 1. Detect Active Category
        active_cat_slug = data.get("search_data", {}).get("form_data", {}).get("data", {}).get("category", {}).get("str", {}).get("value")
        active_cat_name = "عمومی"
        bread_crumb = data.get("seo_details", {}).get("bread_crumb", [])
        if bread_crumb:
            active_cat_name = bread_crumb[0].get("name", active_cat_name)

        active_category = CategoryMeta(
            slug=active_cat_slug or category or "ROOT",
            name=active_cat_name
        ) if (active_cat_slug or category) else None

        # 2. Extract Related Categories Suggestions (نکته طلایی اسکرین‌شات کاربر)
        related_categories: List[CategoryMeta] = []
        widgets = data.get("list_widgets", [])
        for w in widgets:
            if w.get("widget_type") == "POST_LIST_SUGGESTION_CARD":
                card_data = w.get("data", {})
                card_title = card_data.get("title", "")
                if "دیگر" in card_title or "مرتبط" in card_title:
                    for s in card_data.get("suggestions", []):
                        cat_name = s.get("category", "").replace("در ", "").strip()
                        action = s.get("action", {})
                        s_data = action.get("payload", {}).get("search_data", {})
                        s_slug = s_data.get("form_data", {}).get("data", {}).get("category", {}).get("str", {}).get("value")
                        if cat_name and s_slug:
                            related_categories.append(CategoryMeta(name=cat_name, slug=s_slug))

        # 3. Build token -> price mapping from seo_details
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
                    seo_prices[token] = int(price_val) // 10

        # 4. Extract Post Summaries
        initial_posts: List[DivarPostSummary] = []
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

            price_toman = seo_prices.get(token) or parse_price_to_toman(middle_desc)

            # Basic price filter check
            if effective_min_price is not None and price_toman is not None and price_toman < effective_min_price:
                continue
            if effective_max_price is not None and price_toman is not None and price_toman > effective_max_price:
                continue

            img_url = w_data.get("image_url")
            if not img_url and w_data.get("image_urls"):
                img_url = w_data["image_urls"][0]

            district = None
            time_text = bottom_desc
            if bottom_desc and " در " in bottom_desc:
                parts = bottom_desc.split(" در ")
                time_text = parts[0].strip()
                district = parts[1].strip()

            initial_posts.append(DivarPostSummary(
                token=token,
                title=title,
                price=middle_desc,
                price_toman=price_toman,
                district=district,
                city=city_info.name,
                time_text=time_text,
                image_url=img_url,
                url=f"https://divar.ir/v/{token}"
            ))

        # 5. Advanced Category-Specific Filtering (If filters requested)
        final_posts = initial_posts
        has_deep_filters = any(
            k in active_filters
            for k in ("min_year", "max_year", "max_mileage", "color", "gearbox", "has_elevator", "min_size", "max_size", "min_ram")
        )

        if has_deep_filters and initial_posts:
            # Concurrently inspect first candidate posts to match deep specs
            candidates = initial_posts[:max(limit * 2, 20)]
            sem = asyncio.Semaphore(6)
            matching_posts = []

            async def check_post(p: DivarPostSummary):
                async with sem:
                    try:
                        det = await self.get_post_details(p.token)
                        specs = det.specifications
                        text_to_check = f"{det.title} {det.description} " + " ".join(f"{k}:{v}" for k, v in specs.items())

                        # Check Car filters
                        if "min_year" in active_filters or "max_year" in active_filters:
                            year_val = parse_number(specs.get("مدل (سال ساخت)") or specs.get("سال ساخت"))
                            if year_val:
                                if "min_year" in active_filters and year_val < int(active_filters["min_year"]):
                                    return
                                if "max_year" in active_filters and year_val > int(active_filters["max_year"]):
                                    return

                        if "max_mileage" in active_filters:
                            mileage_val = parse_number(specs.get("کارکرد"))
                            if mileage_val and mileage_val > int(active_filters["max_mileage"]):
                                return

                        if "color" in active_filters:
                            req_color = str(active_filters["color"]).strip().lower()
                            post_color = str(specs.get("رنگ", "")).lower()
                            if req_color not in post_color and req_color not in text_to_check.lower():
                                return

                        if "gearbox" in active_filters:
                            req_gb = str(active_filters["gearbox"]).strip().lower()
                            post_gb = str(specs.get("گیربکس", "")).lower()
                            if req_gb not in post_gb:
                                return

                        # Check Real Estate filters
                        if "min_size" in active_filters:
                            size_val = parse_number(specs.get("متراژ"))
                            if size_val and size_val < int(active_filters["min_size"]):
                                return

                        if "has_elevator" in active_filters and active_filters["has_elevator"]:
                            elev = specs.get("آسانسور", "")
                            if "ندارد" in elev or ("دارد" not in elev and "آسانسور" not in text_to_check):
                                return

                        # Check Laptop/Digital filters
                        if "min_ram" in active_filters:
                            ram_val = parse_number(specs.get("مقدار رم"))
                            if ram_val and ram_val < int(active_filters["min_ram"]):
                                return

                        matching_posts.append(p)
                    except Exception:
                        # On inspection failure, keep post to be safe
                        matching_posts.append(p)

            await asyncio.gather(*(check_post(p) for p in candidates))
            final_posts = matching_posts

        resolved_cat_slug = active_cat_slug or category
        available_filters = get_available_filters_for_category(resolved_cat_slug)

        return SearchResult(
            status="success",
            query=query,
            city=city_info.name,
            active_category=active_category,
            related_categories=related_categories,
            available_filters=available_filters,
            count=len(final_posts[:limit]),
            posts=final_posts[:limit],
        )

    async def get_post_details(self, token_or_url: str) -> DivarPostDetail:
        """Fetches full details of a specific Divar post."""
        token = token_or_url.strip()
        url_match = re.search(r"/([a-zA-Z0-9_\-]+)/?$", token)
        if "/" in token and url_match:
            token = url_match.group(1)

        url = f"{DIVAR_BASE_URL}/v8/posts-v2/web/{token}"
        async with await self._get_client() as client:
            resp = await client.get(url)
            if resp.status_code == 404:
                raise ValueError(f"آگهی با توکن '{token}' در دیوار پیدا نشد.")
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

        if not title:
            title = data.get("seo", {}).get("title") or "بدون عنوان"

        chat_enabled = bool(data.get("contact", {}).get("chat_enabled"))
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
            raw_data=None,
        )

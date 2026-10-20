"""Async client for the Tandoor Recipes REST API.

Kept free of Home Assistant imports so it can be exercised on its own.
Endpoints and parameters follow Tandoor's OpenAPI schema (``/openapi/``, 2.x).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any
from urllib.parse import urljoin

import aiohttp

REQUEST_TIMEOUT = 15
PAGE_SIZE = 100
MAX_PAGES = 10


class TandoorError(Exception):
    """Base error talking to Tandoor."""


class TandoorConnectionError(TandoorError):
    """Tandoor could not be reached or timed out."""


class TandoorAuthError(TandoorError):
    """The API token was rejected."""


def normalize_url(url: str) -> str:
    """Return the instance base URL without a trailing slash, with a scheme."""
    url = url.strip().rstrip("/")
    if "://" not in url:
        url = f"http://{url}"
    return url


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        try:
            return datetime.combine(date.fromisoformat(value[:10]), time.min)
        except ValueError:
            return None


def _parse_time(value: str | None) -> time | None:
    if not value:
        return None
    try:
        return time.fromisoformat(value)
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class MealType:
    """A Tandoor meal type (Breakfast, Lunch, Dinner, ...)."""

    id: int
    name: str
    time: time | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> MealType:
        return cls(
            id=data["id"],
            name=data.get("name") or "",
            time=_parse_time(data.get("time")),
        )


@dataclass(frozen=True, slots=True)
class Recipe:
    """The parts of a Tandoor recipe the integration shows."""

    id: int
    name: str
    url: str
    description: str | None = None
    image: str | None = None
    working_time: int = 0
    waiting_time: int = 0
    servings: float | None = None
    servings_text: str | None = None
    rating: float | None = None
    keywords: list[str] = field(default_factory=list)

    @property
    def total_time(self) -> int:
        return (self.working_time or 0) + (self.waiting_time or 0)

    @classmethod
    def from_api(cls, data: dict[str, Any], base_url: str) -> Recipe:
        image = data.get("image")
        if image and not image.startswith(("http://", "https://")):
            image = urljoin(f"{base_url}/", image.lstrip("/"))
        keywords = [
            kw.get("label") or kw.get("name")
            for kw in data.get("keywords") or []
            if isinstance(kw, dict) and (kw.get("label") or kw.get("name"))
        ]
        return cls(
            id=data["id"],
            name=data.get("name") or "",
            url=f"{base_url}/recipe/{data['id']}",
            description=data.get("description") or None,
            image=image or None,
            working_time=data.get("working_time") or 0,
            waiting_time=data.get("waiting_time") or 0,
            servings=data.get("servings"),
            servings_text=data.get("servings_text") or None,
            rating=data.get("rating"),
            keywords=keywords,
        )


@dataclass(frozen=True, slots=True)
class MealPlanEntry:
    """One entry on the Tandoor meal plan."""

    id: int
    title: str
    start: datetime
    end: datetime | None
    meal_type: MealType | None
    recipe: Recipe | None
    servings: float | None = None
    note: str | None = None

    @property
    def name(self) -> str:
        """Recipe name, falling back to the entry's own title."""
        if self.recipe and self.recipe.name:
            return self.recipe.name
        return self.title or (self.meal_type.name if self.meal_type else "Meal")

    @classmethod
    def from_api(cls, data: dict[str, Any], base_url: str) -> MealPlanEntry | None:
        start = _parse_datetime(data.get("from_date"))
        if start is None:
            return None
        recipe = data.get("recipe")
        meal_type = data.get("meal_type")
        return cls(
            id=data["id"],
            title=data.get("title") or "",
            start=start,
            end=_parse_datetime(data.get("to_date")),
            meal_type=MealType.from_api(meal_type) if isinstance(meal_type, dict) else None,
            recipe=Recipe.from_api(recipe, base_url) if isinstance(recipe, dict) else None,
            servings=data.get("servings"),
            note=data.get("note") or None,
        )


class TandoorClient:
    """Minimal read-only Tandoor API client."""

    def __init__(self, session: aiohttp.ClientSession, base_url: str, token: str) -> None:
        self._session = session
        self.base_url = normalize_url(base_url)
        token = token.strip()
        self._auth = token if token.lower().startswith("bearer ") else f"Bearer {token}"

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                resp = await self._session.get(
                    url,
                    params=params,
                    headers={"Authorization": self._auth, "Accept": "application/json"},
                    allow_redirects=False,
                )
                async with resp:
                    if resp.status in (401, 403):
                        raise TandoorAuthError(f"Tandoor rejected the API token ({resp.status})")
                    if resp.status in (301, 302):
                        # Tandoor redirects unauthenticated browser-style requests to its login page.
                        raise TandoorAuthError("Tandoor redirected to its login page; check the API token")
                    if resp.status != 200:
                        raise TandoorError(f"Tandoor returned HTTP {resp.status} for {path}")
                    return await resp.json(content_type=None)
        except TimeoutError as err:
            raise TandoorConnectionError(f"Timed out talking to {self.base_url}") from err
        except aiohttp.ClientError as err:
            raise TandoorConnectionError(f"Cannot reach {self.base_url}: {err}") from err

    async def _get_all(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Follow Tandoor's paginated results (or accept a plain list)."""
        data = await self._get(path, {**params, "page_size": PAGE_SIZE})
        if isinstance(data, list):
            return data
        results: list[dict[str, Any]] = list(data.get("results") or [])
        next_url = data.get("next")
        pages = 1
        while next_url and pages < MAX_PAGES:
            data = await self._get(next_url)
            results.extend(data.get("results") or [])
            next_url = data.get("next")
            pages += 1
        return results

    async def async_get_meal_types(self) -> list[MealType]:
        """Return all meal types. Also used to validate the token."""
        return [MealType.from_api(item) for item in await self._get_all("/api/meal-type/", {})]

    async def async_get_meal_plan(self, start: date, end: date) -> list[MealPlanEntry]:
        """Return meal plan entries between two dates (inclusive)."""
        items = await self._get_all(
            "/api/meal-plan/",
            {"from_date": start.isoformat(), "to_date": end.isoformat()},
        )
        entries = [MealPlanEntry.from_api(item, self.base_url) for item in items]
        return sorted((e for e in entries if e is not None), key=lambda e: e.start)

    async def async_get_random_recipe(self) -> Recipe | None:
        """Return one random recipe from the library, or None if it is empty."""
        data = await self._get("/api/recipe/", {"random": "true", "page_size": 1})
        results = data.get("results") if isinstance(data, dict) else data
        if not results:
            return None
        return Recipe.from_api(results[0], self.base_url)

from __future__ import annotations

import json
import re
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from dillon_finances.models import Category


SYSTEM_CATEGORIES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("income", "Income", ()),
    ("housing", "Housing", ()),
    ("utilities", "Utilities", ()),
    ("groceries", "Groceries", ("Food", "Staples")),
    ("dining", "Dining", ("Restaurants",)),
    ("transportation", "Transportation", ("Fuel", "Gas")),
    ("health", "Health", ("Medical",)),
    ("insurance", "Insurance", ()),
    ("debt", "Debt", ()),
    ("savings_investments", "Savings & Investments", ("Investments", "Savings")),
    ("household", "Household", ()),
    ("family_care", "Family Care", ("Childcare",)),
    ("education", "Education", ()),
    ("entertainment", "Entertainment", ()),
    ("travel", "Travel", ()),
    ("gifts_charity", "Gifts & Charity", ("Charity", "Gifts")),
    ("taxes", "Taxes", ()),
    ("business", "Business", ()),
    ("reimbursements", "Reimbursements", ()),
    ("transfers", "Transfers", ()),
    ("fees", "Fees", ()),
    ("uncategorized", "Uncategorized", ("Unknown",)),
)


class CategoryError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class CategoryCreateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    aliases: list[str] = Field(default_factory=list)
    actor: str = Field(min_length=1)
    note: Optional[str] = None


class CategoryPatchRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    aliases: Optional[list[str]] = None
    sort_order: Optional[int] = None
    active: Optional[bool] = None
    actor: str = Field(min_length=1)
    note: Optional[str] = None


def _dump_aliases(aliases: list[str] | tuple[str, ...]) -> str:
    cleaned = []
    for alias in aliases:
        normalized = alias.strip()
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
    return json.dumps(cleaned, sort_keys=True)


def _load_aliases(value_json: str) -> list[str]:
    return list(json.loads(value_json or "[]"))


def _normalize_lookup(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.strip().casefold())
    return slug.strip("_")


def seed_default_categories(session: Session) -> None:
    for index, (category_key, display_name, aliases) in enumerate(SYSTEM_CATEGORIES, start=10):
        existing = session.scalar(select(Category).where(Category.category_key == category_key))
        if existing is None:
            session.add(
                Category(
                    category_key=category_key,
                    display_name=display_name,
                    category_type="system",
                    aliases_json=_dump_aliases(aliases),
                    sort_order=index * 10,
                    active=True,
                    created_by="system",
                )
            )
    session.commit()


def serialize_category(category: Category) -> dict[str, Any]:
    return {
        "id": category.id,
        "category_key": category.category_key,
        "display_name": category.display_name,
        "category_type": category.category_type,
        "aliases": _load_aliases(category.aliases_json),
        "sort_order": category.sort_order,
        "active": category.active,
        "created_by": category.created_by,
        "created_note": category.created_note,
        "updated_by": category.updated_by,
        "updated_note": category.updated_note,
        "created_at": category.created_at,
        "updated_at": category.updated_at,
    }


def list_categories(session: Session, *, include_inactive: bool = True) -> list[dict[str, Any]]:
    seed_default_categories(session)
    statement = select(Category).order_by(Category.sort_order, Category.display_name, Category.category_key)
    if not include_inactive:
        statement = statement.where(Category.active.is_(True))
    return [serialize_category(category) for category in session.scalars(statement).all()]


def _category_records(session: Session) -> list[Category]:
    seed_default_categories(session)
    return session.scalars(select(Category).order_by(Category.sort_order, Category.display_name)).all()


def resolve_category_key(session: Session, value: Any) -> Optional[str]:
    if value is None:
        return None
    normalized = _normalize_lookup(str(value))
    if not normalized:
        return None
    for category in _category_records(session):
        if not category.active:
            continue
        candidates = [category.category_key, category.display_name, *_load_aliases(category.aliases_json)]
        if any(_normalize_lookup(candidate) == normalized for candidate in candidates):
            return category.category_key
    return None


def category_display_name(session: Session, category_key: Optional[str]) -> Optional[str]:
    if not category_key:
        return None
    category = session.scalar(select(Category).where(Category.category_key == category_key))
    if category is None:
        return None
    return category.display_name


def category_identity_for_value(session: Session, value: Any) -> dict[str, Optional[str]]:
    if value is None:
        return {"category_key": None, "display_name": None}
    raw_value = str(value).strip()
    if not raw_value:
        return {"category_key": None, "display_name": None}
    category_key = resolve_category_key(session, raw_value)
    if category_key:
        return {"category_key": category_key, "display_name": category_display_name(session, category_key)}
    return {"category_key": None, "display_name": raw_value}


def create_custom_category(session: Session, request: CategoryCreateRequest) -> dict[str, Any]:
    if not (request.note and request.note.strip()):
        raise CategoryError("category_note_required", "Custom categories require an owner note.")
    base_key = _slug(request.display_name)
    if not base_key:
        raise CategoryError("invalid_category_key", "Category display name must produce a stable key.")
    existing_key = resolve_category_key(session, request.display_name)
    if existing_key:
        raise CategoryError("category_already_exists", "A category with this name or alias already exists.", status_code=409)

    category_key = base_key
    suffix = 2
    while session.scalar(select(Category).where(Category.category_key == category_key)) is not None:
        category_key = f"{base_key}_{suffix}"
        suffix += 1

    max_sort = max((category.sort_order for category in _category_records(session)), default=0)
    category = Category(
        category_key=category_key,
        display_name=request.display_name.strip(),
        category_type="custom",
        aliases_json=_dump_aliases(request.aliases),
        sort_order=max_sort + 10,
        active=True,
        created_by=request.actor,
        created_note=request.note.strip(),
    )
    session.add(category)
    session.commit()
    session.refresh(category)
    return serialize_category(category)


def update_category(session: Session, category_key: str, request: CategoryPatchRequest) -> dict[str, Any]:
    category = session.scalar(select(Category).where(Category.category_key == category_key))
    if category is None:
        raise CategoryError("category_not_found", "Category was not found.", status_code=404)
    if request.display_name is not None:
        category.display_name = request.display_name.strip()
    if request.aliases is not None:
        category.aliases_json = _dump_aliases(request.aliases)
    if request.sort_order is not None:
        category.sort_order = request.sort_order
    if request.active is not None:
        category.active = request.active
    category.updated_by = request.actor
    category.updated_note = request.note.strip() if request.note else None
    session.commit()
    session.refresh(category)
    return serialize_category(category)

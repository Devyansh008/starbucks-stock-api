"""
Starbucks Store Stock Snapshot API
Snapshot date/time: 7 March 2025, 06:45
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SNAPSHOT_TIMESTAMP = "2025-03-07T06:45:00-08:00"

# The CSV lives one directory above this file (repo root)
_HERE = Path(__file__).parent
DATA_FILE = _HERE.parent / "starbucks_store_stock_snapshot_2025-03-07.csv"


# ---------------------------------------------------------------------------
# Data loading  (cached — CSV is read once at startup)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def load_snapshot() -> pd.DataFrame:
    """Load the stock snapshot CSV into memory."""
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Snapshot file not found: {DATA_FILE}")

    df = pd.read_csv(
        DATA_FILE,
        dtype={
            "store_id": str,
            "store_name": str,
            "store_open": bool,
            "component_id": str,
            "component_name": str,
            "component_type": str,
            "quantity_on_hand": int,
            "reserved_quantity": int,
            "last_updated_at": str,
        },
    )
    df["store_id"] = df["store_id"].str.strip()
    return df


# ---------------------------------------------------------------------------
# Availability rule
# ---------------------------------------------------------------------------

# A milk (or any component) is available when:
#   quantity_on_hand - reserved_quantity > 0
# Reserved stock is already committed to in-progress orders and cannot
# be used for new ones, so we subtract it before deciding availability.
AVAILABILITY_RULE = "on_hand_minus_reserved"


def _is_sold_out(on_hand: int, reserved: int) -> bool:
    """Return True when available stock (on_hand - reserved) is zero or less."""
    return (on_hand - reserved) <= 0


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------

class StockItem(BaseModel):
    component_id: str
    component_name: str
    component_type: str
    quantity_on_hand: int
    reserved_quantity: int
    available_quantity: int   # quantity_on_hand - reserved_quantity
    last_updated_at: str


class StoreStockResponse(BaseModel):
    snapshot_timestamp: str
    store_id: str
    store_name: str
    store_open: bool
    stock: List[StockItem]


class StoreListItem(BaseModel):
    store_id: str
    store_name: str
    store_open: bool


class StoresListResponse(BaseModel):
    snapshot_timestamp: str
    stores: List[StoreListItem]


class ComponentListItem(BaseModel):
    component_id: str
    component_name: str
    component_type: str


class ComponentsListResponse(BaseModel):
    snapshot_timestamp: str
    components: List[ComponentListItem]


class ComponentStoreStock(BaseModel):
    store_id: str
    store_name: str
    store_open: bool
    quantity_on_hand: int
    reserved_quantity: int
    available_quantity: int
    last_updated_at: str


class ComponentStockResponse(BaseModel):
    snapshot_timestamp: str
    component_id: str
    component_name: str
    component_type: str
    stores: List[ComponentStoreStock]


class HealthResponse(BaseModel):
    status: str
    snapshot_timestamp: str
    stores_loaded: int
    rows_loaded: int


class SoldOutItem(BaseModel):
    store_id: str
    store_name: str
    store_open: bool
    component_id: str
    component_name: str
    component_type: str
    quantity_on_hand: int
    reserved_quantity: int
    available_quantity: int
    last_updated_at: str


class SoldOutResponse(BaseModel):
    snapshot_timestamp: str
    availability_rule: str
    rule_description: str
    total_sold_out: int
    items: List[SoldOutItem]

# ---------------------------------------------------------------------------
# App + lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _lifespan(_app: "FastAPI"):
    """Pre-load the snapshot at startup so the first request is instant."""
    load_snapshot()
    yield


app = FastAPI(
    title="Starbucks Store Stock API",
    description=(
        "Returns component stock levels from the Store Stock Snapshot "
        "taken on **7 March 2025 at 06:45 PT**.\n\n"
        "| Path | Description |\n"
        "|------|-------------|\n"
        "| `GET /health` | Liveness probe |\n"
        "| `GET /stores` | List all stores |\n"
        "| `GET /stores/{store_id}/stock` | All stock for a store |\n"
        "| `GET /stores/{store_id}/stock/{component_id}` | Single component |\n"
        "| `GET /components` | Component catalogue |\n"
        "| `GET /components/{component_id}/stock` | Component across all stores |\n"
        "| `GET /alerts/sold-out` | Sold-out items by availability rule |\n"
    ),
    version="1.0.0",
    lifespan=_lifespan,
)


# ---------------------------------------------------------------------------
# Endpoints — stores
# ---------------------------------------------------------------------------

@app.get(
    "/stores",
    response_model=StoresListResponse,
    summary="List all stores in the snapshot",
)
def list_stores() -> StoresListResponse:
    """Return every store present in the snapshot."""
    df = load_snapshot()
    stores_df = (
        df[["store_id", "store_name", "store_open"]]
        .drop_duplicates()
        .sort_values("store_id")
    )
    return StoresListResponse(
        snapshot_timestamp=SNAPSHOT_TIMESTAMP,
        stores=[
            StoreListItem(
                store_id=row["store_id"],
                store_name=row["store_name"],
                store_open=bool(row["store_open"]),
            )
            for _, row in stores_df.iterrows()
        ],
    )


@app.get(
    "/stores/{store_id}/stock",
    response_model=StoreStockResponse,
    summary="Get the full stock for a specific store",
)
def get_store_stock(
    store_id: str,
    component_type: Optional[str] = Query(
        default=None,
        description="Filter by component type (`drink_base` or `add_in`)",
    ),
) -> StoreStockResponse:
    """
    Return all stock items for the given **store_id**.

    - Optionally filter by `component_type`.
    - Returns **404** when the store ID is not in the snapshot.
    """
    df = load_snapshot()
    store_df = df[df["store_id"] == store_id.strip()]

    if store_df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Store '{store_id}' not found. Use GET /stores to see available IDs.",
        )

    if component_type:
        store_df = store_df[store_df["component_type"] == component_type]
        if store_df.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No components of type '{component_type}' for store '{store_id}'.",
            )

    store_row = store_df.iloc[0]
    return StoreStockResponse(
        snapshot_timestamp=SNAPSHOT_TIMESTAMP,
        store_id=store_id.strip(),
        store_name=store_row["store_name"],
        store_open=bool(store_row["store_open"]),
        stock=[
            StockItem(
                component_id=row["component_id"],
                component_name=row["component_name"],
                component_type=row["component_type"],
                quantity_on_hand=int(row["quantity_on_hand"]),
                reserved_quantity=int(row["reserved_quantity"]),
                available_quantity=int(row["quantity_on_hand"]) - int(row["reserved_quantity"]),
                last_updated_at=row["last_updated_at"],
            )
            for _, row in store_df.iterrows()
        ],
    )


@app.get(
    "/stores/{store_id}/stock/{component_id}",
    response_model=StockItem,
    summary="Get a single component's stock for a specific store",
)
def get_store_component_stock(store_id: str, component_id: str) -> StockItem:
    """
    Return the stock level for one **component** at one **store**.

    Returns **404** if either the store or component is not in the snapshot.
    """
    df = load_snapshot()
    store_df = df[df["store_id"] == store_id.strip()]
    if store_df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Store '{store_id}' not found. Use GET /stores to see available IDs.",
        )

    row_df = store_df[store_df["component_id"] == component_id.strip()]
    if row_df.empty:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Component '{component_id}' not found for store '{store_id}'. "
                f"Use GET /components to see available component IDs."
            ),
        )

    row = row_df.iloc[0]
    return StockItem(
        component_id=row["component_id"],
        component_name=row["component_name"],
        component_type=row["component_type"],
        quantity_on_hand=int(row["quantity_on_hand"]),
        reserved_quantity=int(row["reserved_quantity"]),
        available_quantity=int(row["quantity_on_hand"]) - int(row["reserved_quantity"]),
        last_updated_at=row["last_updated_at"],
    )


# ---------------------------------------------------------------------------
# Endpoints — components
# ---------------------------------------------------------------------------

@app.get(
    "/components",
    response_model=ComponentsListResponse,
    summary="List all components in the snapshot",
)
def list_components(
    component_type: Optional[str] = Query(
        default=None,
        description="Filter by component type (`drink_base` or `add_in`)",
    ),
) -> ComponentsListResponse:
    """Return the unique catalogue of components across all stores."""
    df = load_snapshot()
    comp_df = (
        df[["component_id", "component_name", "component_type"]]
        .drop_duplicates()
        .sort_values("component_id")
    )
    if component_type:
        comp_df = comp_df[comp_df["component_type"] == component_type]

    return ComponentsListResponse(
        snapshot_timestamp=SNAPSHOT_TIMESTAMP,
        components=[
            ComponentListItem(
                component_id=row["component_id"],
                component_name=row["component_name"],
                component_type=row["component_type"],
            )
            for _, row in comp_df.iterrows()
        ],
    )


@app.get(
    "/components/{component_id}/stock",
    response_model=ComponentStockResponse,
    summary="Get a component's stock across all stores",
)
def get_component_stock(component_id: str) -> ComponentStockResponse:
    """
    Return the stock level for one **component** across **every store**.

    Returns **404** if the component ID is not in the snapshot.
    """
    df = load_snapshot()
    comp_df = df[df["component_id"] == component_id.strip()]
    if comp_df.empty:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Component '{component_id}' not found. "
                f"Use GET /components to see available IDs."
            ),
        )

    first = comp_df.iloc[0]
    return ComponentStockResponse(
        snapshot_timestamp=SNAPSHOT_TIMESTAMP,
        component_id=component_id.strip(),
        component_name=first["component_name"],
        component_type=first["component_type"],
        stores=[
            ComponentStoreStock(
                store_id=row["store_id"],
                store_name=row["store_name"],
                store_open=bool(row["store_open"]),
                quantity_on_hand=int(row["quantity_on_hand"]),
                reserved_quantity=int(row["reserved_quantity"]),
                available_quantity=int(row["quantity_on_hand"]) - int(row["reserved_quantity"]),
                last_updated_at=row["last_updated_at"],
            )
            for _, row in comp_df.iterrows()
        ],
    )


# ---------------------------------------------------------------------------
# Endpoints — alerts
# ---------------------------------------------------------------------------

@app.get(
    "/alerts/sold-out",
    response_model=SoldOutResponse,
    summary="List sold-out components (quantity_on_hand − reserved_quantity ≤ 0)",
    tags=["alerts"],
)
def get_sold_out(
    store_id: Optional[str] = Query(default=None, description="Limit to one store ID."),
    component_type: Optional[str] = Query(default=None, description="Limit to a component type."),
) -> SoldOutResponse:
    """
    Return every component that is **sold out** at snapshot time.

    **Availability rule (hardcoded):** `quantity_on_hand − reserved_quantity ≤ 0`
    Reserved stock is already committed to in-progress orders and cannot be
    used for new ones, so we subtract it before deciding availability.
    """
    df = load_snapshot()

    if store_id:
        df = df[df["store_id"] == store_id.strip()]
        if df.empty:
            raise HTTPException(
                status_code=404,
                detail=f"Store '{store_id}' not found. Use GET /stores to see available IDs.",
            )

    if component_type:
        df = df[df["component_type"] == component_type]

    items = [
        SoldOutItem(
            store_id=row["store_id"],
            store_name=row["store_name"],
            store_open=bool(row["store_open"]),
            component_id=row["component_id"],
            component_name=row["component_name"],
            component_type=row["component_type"],
            quantity_on_hand=int(row["quantity_on_hand"]),
            reserved_quantity=int(row["reserved_quantity"]),
            available_quantity=int(row["quantity_on_hand"]) - int(row["reserved_quantity"]),
            last_updated_at=row["last_updated_at"],
        )
        for _, row in df.iterrows()
        if _is_sold_out(int(row["quantity_on_hand"]), int(row["reserved_quantity"]))
    ]

    return SoldOutResponse(
        snapshot_timestamp=SNAPSHOT_TIMESTAMP,
        availability_rule=AVAILABILITY_RULE,
        rule_description="quantity_on_hand − reserved_quantity ≤ 0",
        total_sold_out=len(items),
        items=items,
    )


# ---------------------------------------------------------------------------
# Endpoints — meta
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    response_model=HealthResponse,
    summary="API liveness probe",
    tags=["meta"],
)
def health() -> HealthResponse:
    """Returns 200 OK when the snapshot is loaded and the service is healthy."""
    df = load_snapshot()
    return HealthResponse(
        status="ok",
        snapshot_timestamp=SNAPSHOT_TIMESTAMP,
        stores_loaded=int(df["store_id"].nunique()),
        rows_loaded=len(df),
    )

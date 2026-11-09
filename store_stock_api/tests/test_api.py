"""
Tests for the Starbucks Store Stock Snapshot API.
Run with:  pytest tests/ -v
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app, SNAPSHOT_TIMESTAMP, AVAILABILITY_RULE

client = TestClient(app)


# ── Helpers ──────────────────────────────────────────────────────────────────

KNOWN_STORE_ID = "10482"
KNOWN_STORE_NAME = "First Hill - Madison & Boylston"
CLOSED_STORE_ID = "09815"
KNOWN_COMPONENT_ID = "oat_milk"
UNKNOWN_STORE = "99999"
UNKNOWN_COMPONENT = "unicorn_syrup"


# ── /health ───────────────────────────────────────────────────────────────────

class TestHealth:
    def test_returns_200(self):
        r = client.get("/health")
        assert r.status_code == 200

    def test_status_ok(self):
        body = client.get("/health").json()
        assert body["status"] == "ok"

    def test_snapshot_timestamp(self):
        body = client.get("/health").json()
        assert body["snapshot_timestamp"] == SNAPSHOT_TIMESTAMP

    def test_stores_loaded(self):
        body = client.get("/health").json()
        assert body["stores_loaded"] == 3

    def test_rows_loaded(self):
        body = client.get("/health").json()
        assert body["rows_loaded"] == 30


# ── /stores ───────────────────────────────────────────────────────────────────

class TestListStores:
    def test_returns_200(self):
        r = client.get("/stores")
        assert r.status_code == 200

    def test_snapshot_timestamp_present(self):
        body = client.get("/stores").json()
        assert body["snapshot_timestamp"] == SNAPSHOT_TIMESTAMP

    def test_three_stores(self):
        body = client.get("/stores").json()
        assert len(body["stores"]) == 3

    def test_store_fields(self):
        store = client.get("/stores").json()["stores"][0]
        assert "store_id" in store
        assert "store_name" in store
        assert "store_open" in store

    def test_closed_store_included(self):
        ids = [s["store_id"] for s in client.get("/stores").json()["stores"]]
        assert CLOSED_STORE_ID in ids

    def test_closed_store_open_false(self):
        stores = {s["store_id"]: s for s in client.get("/stores").json()["stores"]}
        assert stores[CLOSED_STORE_ID]["store_open"] is False


# ── /stores/{store_id}/stock ──────────────────────────────────────────────────

class TestGetStoreStock:
    def test_known_store_200(self):
        r = client.get(f"/stores/{KNOWN_STORE_ID}/stock")
        assert r.status_code == 200

    def test_unknown_store_404(self):
        r = client.get(f"/stores/{UNKNOWN_STORE}/stock")
        assert r.status_code == 404

    def test_404_message_mentions_stores_endpoint(self):
        body = client.get(f"/stores/{UNKNOWN_STORE}/stock").json()
        assert "/stores" in body["detail"]

    def test_store_name_correct(self):
        body = client.get(f"/stores/{KNOWN_STORE_ID}/stock").json()
        assert body["store_name"] == KNOWN_STORE_NAME

    def test_ten_stock_items(self):
        body = client.get(f"/stores/{KNOWN_STORE_ID}/stock").json()
        assert len(body["stock"]) == 10

    def test_stock_item_fields(self):
        item = client.get(f"/stores/{KNOWN_STORE_ID}/stock").json()["stock"][0]
        for field in [
            "component_id", "component_name", "component_type",
            "quantity_on_hand", "reserved_quantity", "available_quantity",
            "last_updated_at",
        ]:
            assert field in item, f"Missing field: {field}"

    def test_available_quantity_derived(self):
        for item in client.get(f"/stores/{KNOWN_STORE_ID}/stock").json()["stock"]:
            expected = item["quantity_on_hand"] - item["reserved_quantity"]
            assert item["available_quantity"] == expected

    def test_filter_drink_base(self):
        body = client.get(f"/stores/{KNOWN_STORE_ID}/stock?component_type=drink_base").json()
        assert all(i["component_type"] == "drink_base" for i in body["stock"])

    def test_filter_add_in(self):
        body = client.get(f"/stores/{KNOWN_STORE_ID}/stock?component_type=add_in").json()
        assert all(i["component_type"] == "add_in" for i in body["stock"])

    def test_filter_unknown_type_404(self):
        r = client.get(f"/stores/{KNOWN_STORE_ID}/stock?component_type=mystery")
        assert r.status_code == 404


# ── /stores/{store_id}/stock/{component_id} ───────────────────────────────────

class TestGetStoreComponentStock:
    def test_known_200(self):
        r = client.get(f"/stores/{KNOWN_STORE_ID}/stock/{KNOWN_COMPONENT_ID}")
        assert r.status_code == 200

    def test_unknown_store_404(self):
        r = client.get(f"/stores/{UNKNOWN_STORE}/stock/{KNOWN_COMPONENT_ID}")
        assert r.status_code == 404

    def test_unknown_component_404(self):
        r = client.get(f"/stores/{KNOWN_STORE_ID}/stock/{UNKNOWN_COMPONENT}")
        assert r.status_code == 404

    def test_correct_component_returned(self):
        body = client.get(f"/stores/{KNOWN_STORE_ID}/stock/{KNOWN_COMPONENT_ID}").json()
        assert body["component_id"] == KNOWN_COMPONENT_ID

    def test_available_quantity_derived(self):
        body = client.get(f"/stores/{KNOWN_STORE_ID}/stock/{KNOWN_COMPONENT_ID}").json()
        assert body["available_quantity"] == body["quantity_on_hand"] - body["reserved_quantity"]


# ── /components ───────────────────────────────────────────────────────────────

class TestListComponents:
    def test_returns_200(self):
        r = client.get("/components")
        assert r.status_code == 200

    def test_ten_components(self):
        body = client.get("/components").json()
        assert len(body["components"]) == 10

    def test_component_fields(self):
        comp = client.get("/components").json()["components"][0]
        assert "component_id" in comp
        assert "component_name" in comp
        assert "component_type" in comp

    def test_filter_drink_base(self):
        body = client.get("/components?component_type=drink_base").json()
        assert all(c["component_type"] == "drink_base" for c in body["components"])

    def test_filter_add_in(self):
        body = client.get("/components?component_type=add_in").json()
        assert all(c["component_type"] == "add_in" for c in body["components"])


# ── /components/{component_id}/stock ─────────────────────────────────────────

class TestGetComponentStock:
    def test_known_200(self):
        r = client.get(f"/components/{KNOWN_COMPONENT_ID}/stock")
        assert r.status_code == 200

    def test_unknown_component_404(self):
        r = client.get(f"/components/{UNKNOWN_COMPONENT}/stock")
        assert r.status_code == 404

    def test_three_stores_returned(self):
        body = client.get(f"/components/{KNOWN_COMPONENT_ID}/stock").json()
        assert len(body["stores"]) == 3

    def test_component_name_present(self):
        body = client.get(f"/components/{KNOWN_COMPONENT_ID}/stock").json()
        assert body["component_name"]

    def test_store_fields(self):
        store = client.get(f"/components/{KNOWN_COMPONENT_ID}/stock").json()["stores"][0]
        for field in [
            "store_id", "store_name", "store_open",
            "quantity_on_hand", "reserved_quantity", "available_quantity",
            "last_updated_at",
        ]:
            assert field in store, f"Missing field: {field}"

    def test_available_quantity_derived(self):
        for store in client.get(f"/components/{KNOWN_COMPONENT_ID}/stock").json()["stores"]:
            assert store["available_quantity"] == store["quantity_on_hand"] - store["reserved_quantity"]


# ── /alerts/sold-out ──────────────────────────────────────────────────────────

class TestSoldOut:
    def test_returns_200(self):
        r = client.get("/alerts/sold-out")
        assert r.status_code == 200

    def test_rule_is_on_hand_minus_reserved(self):
        body = client.get("/alerts/sold-out").json()
        # The hardcoded rule must be on_hand_minus_reserved
        assert body["availability_rule"] == AVAILABILITY_RULE
        assert body["availability_rule"] == "on_hand_minus_reserved"

    def test_rule_description_present(self):
        body = client.get("/alerts/sold-out").json()
        assert "reserved" in body["rule_description"].lower()

    def test_two_sold_out_in_snapshot(self):
        # oat_milk @ First Hill (0,0) and almond_milk @ Capitol Hill (0,0)
        body = client.get("/alerts/sold-out").json()
        assert body["total_sold_out"] == 2

    def test_sold_out_item_fields(self):
        item = client.get("/alerts/sold-out").json()["items"][0]
        for field in [
            "store_id", "store_name", "store_open",
            "component_id", "component_name", "component_type",
            "quantity_on_hand", "reserved_quantity", "available_quantity",
            "last_updated_at",
        ]:
            assert field in item, f"Missing field: {field}"

    def test_sold_out_items_have_zero_or_negative_available(self):
        for item in client.get("/alerts/sold-out").json()["items"]:
            assert item["available_quantity"] <= 0

    def test_filter_by_store(self):
        body = client.get(f"/alerts/sold-out?store_id={KNOWN_STORE_ID}").json()
        # First Hill: only oat_milk is sold out
        assert body["total_sold_out"] == 1
        assert body["items"][0]["component_id"] == "oat_milk"

    def test_filter_unknown_store_404(self):
        r = client.get(f"/alerts/sold-out?store_id={UNKNOWN_STORE}")
        assert r.status_code == 404

    def test_filter_by_component_type(self):
        body = client.get("/alerts/sold-out?component_type=drink_base").json()
        assert all(i["component_type"] == "drink_base" for i in body["items"])

    def test_snapshot_timestamp_present(self):
        body = client.get("/alerts/sold-out").json()
        assert body["snapshot_timestamp"] == SNAPSHOT_TIMESTAMP


# ── First Hill Milk Availability Check ───────────────────────────────────────

class TestFirstHillMilkAvailability:
    def test_first_hill_oat_milk_sold_out_and_other_milks_available(self):
        """
        Requests store 10482 (First Hill - Madison & Boylston),
        asserts oat milk is sold out (available_quantity <= 0),
        and asserts that at least one First Hill milk that should be available
        (almond milk and 2% milk) reads as available (available_quantity > 0).
        """
        response = client.get("/stores/10482/stock")
        assert response.status_code == 200
        data = response.json()

        assert data["store_id"] == "10482"
        assert data["store_name"] == "First Hill - Madison & Boylston"

        stock_map = {item["component_id"]: item for item in data["stock"]}

        # 1. Assert Oat Milk is sold out
        assert "oat_milk" in stock_map
        oat_milk = stock_map["oat_milk"]
        assert oat_milk["quantity_on_hand"] == 0
        assert oat_milk["available_quantity"] <= 0

        # 2. Assert one First Hill milk that should be available reads as available
        # Almondmilk: 38 on hand, 1 reserved -> 37 available
        assert "almond_milk" in stock_map
        almond_milk = stock_map["almond_milk"]
        assert almond_milk["available_quantity"] > 0
        assert almond_milk["available_quantity"] == 37

        # 2% Milk: 96 on hand, 3 reserved -> 93 available
        assert "two_pct_milk" in stock_map
        two_pct_milk = stock_map["two_pct_milk"]
        assert two_pct_milk["available_quantity"] > 0
        assert two_pct_milk["available_quantity"] == 93

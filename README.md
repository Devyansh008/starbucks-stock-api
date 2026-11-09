# Starbucks Store Stock API

A **FastAPI** service that exposes the **Store Stock Snapshot (7 March 2025, 06:45 PT)** and evaluates component availability.

## Availability Rule

A component (milk, drink base, syrup) is **available** when:
$$\text{available\_quantity} = \text{quantity\_on\_hand} - \text{reserved\_quantity} > 0$$

Otherwise, it is **sold out**. Reserved stock is already held for in-progress orders and cannot be allocated to new ones.

### First Hill (Store 10482) Milk Snapshot Verification

| Milk Component | `quantity_on_hand` (CSV) | `reserved_quantity` (CSV) | `available` (Service) | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Oatmilk** | `0` | `0` | **`0`** | 🔴 **Sold Out** |
| **Almondmilk** | `38` | `1` | **`37`** | 🟢 **In Stock** |
| **2% Milk** | `96` | `3` | **`93`** | 🟢 **In Stock** |

---

## Setup & Running

```bash
cd "store_stock_api"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run the API
uvicorn main:app --reload

# Run tests
pytest -v
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | API health check & snapshot row count |
| `GET` | `/stores` | List all stores in the snapshot |
| `GET` | `/stores/{store_id}/stock` | Full stock for a given store |
| `GET` | `/stores/{store_id}/stock/{component_id}` | Single component lookup |
| `GET` | `/components` | Catalogue of all components |
| `GET` | `/components/{component_id}/stock` | Stock across all stores |
| `GET` | `/alerts/sold-out` | List sold-out components (`quantity_on_hand - reserved_quantity <= 0`) |
| `GET` | `/docs` | Interactive Swagger UI |

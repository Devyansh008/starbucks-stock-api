# Starbucks Store Stock API

A lightweight **FastAPI** service that exposes the **Store Stock Snapshot (7 March 2025, 06:45 PT)** via a REST API.

## Project layout

```
Starbucks/
├── starbucks_store_stock_snapshot_2025-03-07.csv   ← snapshot data
└── store_stock_api/
    ├── main.py           ← FastAPI application
    ├── requirements.txt  ← Python dependencies
    └── README.md
```

## Setup

```bash
cd "store_stock_api"

# Create & activate a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Run

```bash
uvicorn main:app --reload
```

The API is now live at **http://127.0.0.1:8000**.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/stores` | List all stores in the snapshot |
| `GET` | `/stores/{store_id}/stock` | Full stock for a store |
| `GET` | `/stores/{store_id}/stock?component_type=drink_base` | Filtered by component type |
| `GET` | `/docs` | Interactive Swagger UI |
| `GET` | `/redoc` | ReDoc documentation |

### Example requests

```bash
# List stores
curl http://127.0.0.1:8000/stores

# Get all stock for store 10482
curl http://127.0.0.1:8000/stores/10482/stock

# Only drink bases for store 11307
curl "http://127.0.0.1:8000/stores/11307/stock?component_type=drink_base"
```

### Example response — `GET /stores/10482/stock`

```json
{
  "snapshot_timestamp": "2025-03-07T06:45:00-08:00",
  "store_id": "10482",
  "store_name": "First Hill - Madison & Boylston",
  "store_open": true,
  "stock": [
    {
      "component_id": "espresso_signature",
      "component_name": "Signature Espresso Roast",
      "component_type": "drink_base",
      "quantity_on_hand": 142,
      "reserved_quantity": 4,
      "available_quantity": 138,
      "last_updated_at": "2025-03-07T06:42:18-08:00"
    },
    ...
  ]
}
```


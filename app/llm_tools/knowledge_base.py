import os
import csv
import json
from typing import Dict, List, Any

from app.database.db_crud import db_get, db_patch

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CSV_FILE = f"{BASE_DIR}/llm_kb/ngos.txt"
NOTIFICATION_FILE = f"{BASE_DIR}/llm_kb/notification.txt"

NOTIFICATION_FIELDS = [
    "request_id",
    "session_id",
    "timestamp",
    "restaurant_name",
    "contact_number",
    "food_items_json",
    "pickup_time",
    "expiry_time",
    "location",
    "ngo_id",
    "ngo_name",
    "distance_km",
    "ngo_status",
    "accepted_ngo_id",
]


def _read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def _ensure_notification_csv() -> None:
    os.makedirs(os.path.dirname(NOTIFICATION_FILE), exist_ok=True)

    raw = _read_text(NOTIFICATION_FILE).lstrip()
    if not raw:
        with open(NOTIFICATION_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=NOTIFICATION_FIELDS)
            writer.writeheader()
        return

    first_char = raw[0]
    if first_char in ("{", "["):
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        rows = []
        for ln in lines:
            try:
                entry = json.loads(ln)
            except Exception:
                continue

            matched = entry.get("matched_ngos") or []
            for m in matched:
                rows.append({
                    "request_id": entry.get("session_id"),
                    "session_id": entry.get("session_id"),
                    "timestamp": entry.get("timestamp"),
                    "restaurant_name": entry.get("restaurant_name"),
                    "contact_number": entry.get("contact_number"),
                    "food_items_json": json.dumps(entry.get("food_items", []), ensure_ascii=False),
                    "pickup_time": entry.get("pickup_time"),
                    "expiry_time": entry.get("expiry_time"),
                    "location": entry.get("location"),
                    "ngo_id": m.get("id"),
                    "ngo_name": m.get("name"),
                    "distance_km": m.get("distance_km"),
                    "ngo_status": "pending",
                    "accepted_ngo_id": "",
                })

        with open(NOTIFICATION_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=NOTIFICATION_FIELDS)
            writer.writeheader()
            for r in rows:
                writer.writerow(r)


def append_session_notifications(
    *,
    session_id: str,
    timestamp: str,
    donation: Dict[str, Any],
    matched_ngos: List[Dict[str, Any]],
) -> bool:
    try:
        _ensure_notification_csv()

        request_id = session_id
        rows = []
        for ngo in matched_ngos:
            rows.append({
                "request_id": request_id,
                "session_id": session_id,
                "timestamp": timestamp,
                "restaurant_name": donation.get("restaurant_name"),
                "contact_number": donation.get("contact_number"),
                "food_items_json": json.dumps(donation.get("food_items", []), ensure_ascii=False),
                "pickup_time": donation.get("pickup_time"),
                "expiry_time": donation.get("expiry_time"),
                "location": donation.get("location"),
                "ngo_id": ngo.get("id"),
                "ngo_name": ngo.get("name"),
                "distance_km": ngo.get("distance_km", "N/A"),
                "ngo_status": "pending",
                "accepted_ngo_id": "",
            })

        with open(NOTIFICATION_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=NOTIFICATION_FIELDS)
            for r in rows:
                writer.writerow(r)

        return True
    except Exception as e:
        print(f"Error writing notification: {e}")
        return False


def load_notification_rows() -> List[Dict[str, Any]]:
    _ensure_notification_csv()

    rows: List[Dict[str, Any]] = []
    with open(NOTIFICATION_FILE, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row:
                continue
            rows.append(dict(row))
    return rows


def get_pending_requests_for_ngo(ngo_id: str) -> List[Dict[str, Any]]:
    rows = load_notification_rows()
    out = []

    for r in rows:
        if (r.get("ngo_id") or "") != ngo_id:
            continue
        if (r.get("ngo_status") or "pending") != "pending":
            continue

        try:
            food_items = json.loads(r.get("food_items_json") or "[]")
        except Exception:
            food_items = []

        out.append({
            "id": r.get("request_id") or r.get("session_id"),
            "request_id": r.get("request_id") or r.get("session_id"),
            "session_id": r.get("session_id"),
            "created_at": r.get("timestamp"),
            "restaurant_name": r.get("restaurant_name"),
            "contact_number": r.get("contact_number"),
            "food_items": food_items,
            "pickup_time": r.get("pickup_time"),
            "expiry_time": r.get("expiry_time"),
            "location": r.get("location"),
            "distance_km": r.get("distance_km"),
            "ngo_status": r.get("ngo_status"),
        })

    out.sort(key=lambda x: (x.get("created_at") or ""), reverse=True)
    return out


def set_request_decision(*, request_id: str, ngo_id: str, decision: str) -> Dict[str, Any]:
    decision = (decision or "").strip().lower()
    if decision not in ("accept", "reject"):
        return {"status": "error", "message": "Invalid decision."}

    rows = load_notification_rows()

    accepted_ngo_id = ""
    for r in rows:
        if (r.get("request_id") or r.get("session_id")) != request_id:
            continue
        if (r.get("ngo_status") or "pending") == "accept":
            accepted_ngo_id = r.get("ngo_id") or ""
            break

    if decision == "accept" and accepted_ngo_id and accepted_ngo_id != ngo_id:
        for r in rows:
            if (r.get("request_id") or r.get("session_id")) != request_id:
                continue
            if (r.get("ngo_id") or "") == ngo_id and (r.get("ngo_status") or "pending") == "pending":
                r["ngo_status"] = "reject"
                r["accepted_ngo_id"] = accepted_ngo_id
        with open(NOTIFICATION_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=NOTIFICATION_FIELDS)
            writer.writeheader()
            for r in rows:
                writer.writerow(r)

        return {"status": "conflict", "message": "Already accepted by another NGO."}

    if decision == "reject":
        for r in rows:
            if (r.get("request_id") or r.get("session_id")) != request_id:
                continue
            if (r.get("ngo_id") or "") != ngo_id:
                continue
            r["ngo_status"] = "reject"

        with open(NOTIFICATION_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=NOTIFICATION_FIELDS)
            writer.writeheader()
            for r in rows:
                writer.writerow(r)

        return {"status": "ok"}

    for r in rows:
        if (r.get("request_id") or r.get("session_id")) != request_id:
            continue

        if (r.get("ngo_id") or "") == ngo_id:
            r["ngo_status"] = "accept"
            r["accepted_ngo_id"] = ngo_id
        else:
            r["ngo_status"] = "reject"
            r["accepted_ngo_id"] = ngo_id

    with open(NOTIFICATION_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=NOTIFICATION_FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    return {"status": "ok"}


def create_sample_ngos() -> List[Dict[str, Any]]:
    """Create sample NGO data if no CSV file exists"""
    sample_ngos = [
        {
            "id": "NGO_001",
            "name": "Jayden BKT Kitchen",
            "contact_person": "Jayden Sea",
            "phone": "016-1234567",
            "email": "info@jayden.com",
            "address": "No. 1, Jalan PJS 1/25, Taman Petaling Utama, 46150 Petaling Jaya, Selangor",
            "latitude": 3.0732,
            "longitude": 101.6072,
            "distance_km": 3.97,
            "type": "Soup Kitchen",
            "capacity_daily": 500,
            "capacity_current": 320,
            "operating_hours": "10:00 AM - 8:00 PM",
            "food_preferences": "cooked_meal; packaged; bakery",
            "special_requirements": "Halal certified only"
        },
        {
            "id": "NGO_002",
            "name": "The Lost Food Project",
            "contact_person": "Vincent Foo",
            "phone": "017-2345678",
            "email": "info@lostfoodproject.org",
            "address": "Lot 634, Batu 5, Jalan Ipoh, 51200 Kuala Lumpur",
            "latitude": 3.2000,
            "longitude": 101.6830,
            "distance_km": 4.74,
            "type": "Food Bank",
            "capacity_daily": 1000,
            "capacity_current": 450,
            "operating_hours": "9:00 AM - 6:00 PM",
            "food_preferences": "cooked_meal; raw; packaged; bakery; beverage",
            "special_requirements": ""
        },
        {
            "id": "NGO_003",
            "name": "Food Aid Foundation",
            "contact_person": "Elvan Teo",
            "phone": "018-3456789",
            "email": "admin@foodaidfoundation.com",
            "address": "33, Jalan Utama 1/7, Taman Perindustrian Puchong Utama, 47100 Puchong, Selangor",
            "latitude": 3.0325,
            "longitude": 101.6190,
            "distance_km": 1.02,
            "type": "Food Bank",
            "capacity_daily": 2000,
            "capacity_current": 1200,
            "operating_hours": "8:00 AM - 8:00 PM",
            "food_preferences": "cooked_meal; packaged; beverage",
            "special_requirements": "Must be within expiry date"
        },
        {
            "id": "NGO_004",
            "name": "Pertubuhan Kebajikan Anak-Anak Yatim",
            "contact_person": "Sarah Abdullah",
            "phone": "019-4567890",
            "email": "yatim@orphancare.my",
            "address": "No. 45, Jalan SS2/55, 47300 Petaling Jaya, Selangor",
            "latitude": 3.1175,
            "longitude": 101.6190,
            "distance_km": 7.23,
            "type": "Orphanage",
            "capacity_daily": 150,
            "capacity_current": 120,
            "operating_hours": "7:00 AM - 9:00 PM",
            "food_preferences": "cooked_meal; bakery; beverage",
            "special_requirements": "Nut-free meals"
        },
        {
            "id": "NGO_005",
            "name": "Rumah Charis",
            "contact_person": "Mary Ting",
            "phone": "012-5678901",
            "email": "admin@rumahcharis.org",
            "address": "No. 16, Jalan 14/46, 46100 Petaling Jaya, Selangor",
            "latitude": 3.0890,
            "longitude": 101.6400,
            "distance_km": 2.52,
            "type": "Elderly Home",
            "capacity_daily": 80,
            "capacity_current": 65,
            "operating_hours": "8:00 AM - 8:00 PM",
            "food_preferences": "cooked_meal; soft_food",
            "special_requirements": "Soft food only; Low salt diet"
        },
        {
            "id": "NGO_006",
            "name": "MERCY Malaysia",
            "contact_person": "Ahmad Mohamad",
            "phone": "013-6789012",
            "email": "food@mercy.org.my",
            "address": "No. 2, Jalan P4/10, Seksyen 4, 43650 Bandar Baru Bangi, Selangor",
            "latitude": 2.9630,
            "longitude": 101.7630,
            "type": "Humanitarian Aid",
            "capacity_daily": 1000,
            "capacity_current": 600,
            "operating_hours": "9:00 AM - 5:00 PM",
            "food_preferences": "packaged; beverage; cooked_meal",
            "special_requirements": ""
        }
    ]
    return sample_ngos


def save_to_csv(ngos_list: List[Dict[str, Any]], file_path: str):
    """Save NGOs to CSV file"""
    try:
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                "id", "name", "type", "contact_person", "phone", "email",
                "address", "latitude", "longitude", "distance_km", "capacity_daily",
                "capacity_current", "operating_hours", "food_preferences",
                "special_requirements"
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            # Write header
            writer.writeheader()

            # Write data
            for ngo in ngos_list:
                row = {
                    "id": ngo.get("id", ""),
                    "name": ngo.get("name", ""),
                    "type": ngo.get("type", ""),
                    "contact_person": ngo.get("contact_person", ""),
                    "phone": ngo.get("phone", ""),
                    "email": ngo.get("email", ""),
                    "address": ngo.get("address", ""),
                    "latitude": ngo.get("latitude", ""),
                    "longitude": ngo.get("longitude", ""),
                    "distance_km": ngo.get("distance_km", 0),
                    "capacity_daily": ngo.get("capacity_daily", 0),
                    "capacity_current": ngo.get("capacity_current", 0),
                    "operating_hours": ngo.get("operating_hours", ""),
                    "food_preferences": ngo.get("food_preferences", ""),
                    "special_requirements": ngo.get("special_requirements", "")
                }
                writer.writerow(row)

        return True
    except Exception as e:
        print(f"Error saving CSV: {e}")
        return False


def load_from_csv(file_path: str) -> List[Dict[str, Any]]:
    """Load NGOs from CSV file"""
    ngos = []

    try:
        with open(file_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Parse food preferences (semicolon separated)
                food_preferences = row.get('food_preferences', '')
                special_requirements = row.get('special_requirements', '')

                ngo = {
                    "id": row.get('id', ''),
                    "name": row.get('name', ''),
                    "type": row.get('type', ''),
                    "contact_person": row.get('contact_person', ''),
                    "phone": row.get('phone', ''),
                    "email": row.get('email', ''),
                    "address": row.get('address', ''),
                    "latitude": float(row['latitude']) if row.get('latitude') else 0,
                    "longitude": float(row['longitude']) if row.get('longitude') else 0,
                    "distance_km": float(row['distance_km']) if row.get('distance_km') else 0,
                    "capacity_daily": int(row.get('capacity_daily', 0)) if row.get('capacity_daily') else 0,
                    "capacity_current": int(row.get('capacity_current', 0)) if row.get('capacity_current') else 0,
                    "operating_hours": row.get('operating_hours', ''),
                    "food_preferences": food_preferences,
                    "special_requirements": special_requirements
                }
                ngos.append(ngo)

        return ngos

    except FileNotFoundError:
        print(f"File {file_path} not found")
        return []
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return []


def load_ngos() -> Dict[str, Dict[str, Any]]:
    """
    Main function to load NGOs from CSV file.
    If CSV doesn't exist, create sample data and save to CSV.
    """
    ngos_list = []

    # Try to load from CSV
    if os.path.exists(CSV_FILE):
        ngos_list = load_from_csv(CSV_FILE)

    # If no file exists or load failed, create sample data
    if not ngos_list:
        print("No existing NGO data found. Creating sample data...")
        ngos_list = create_sample_ngos()
        # Save sample data to CSV
        save_to_csv(ngos_list, CSV_FILE)

    # Convert list to dictionary with id as key (for easy lookup)
    # Also store coordinates as dict for compatibility
    ngos_dict = {}
    for ngo in ngos_list:
        ngo_id = ngo["id"]
        # Add coordinates as dict for compatibility with existing code
        ngo["coordinates"] = {
            "lat": ngo.get("latitude", 0),
            "lng": ngo.get("longitude", 0)
        }
        ngos_dict[ngo_id] = ngo

    return ngos_dict


NGO_KNOWLEDGE_BASE: Dict[str, Dict[str, Any]] = {}


def get_all_ngos() -> List[Dict[str, Any]]:
    res = db_get("ngos")
    if not res or not getattr(res, "ok", False):
        return []
    data = res.json()
    return data if isinstance(data, list) else []


def get_ngo_by_id(ngo_id: str) -> Dict[str, Any]:
    res = db_get("ngos", id=ngo_id)
    if not res or not getattr(res, "ok", False):
        return None
    data = res.json()
    if isinstance(data, list) and data:
        return data[0]
    return None


def get_ngos_by_type(ngo_type: str) -> List[Dict[str, Any]]:
    ngos = get_all_ngos()
    return [ngo for ngo in ngos if ngo.get("type") == ngo_type]


def get_available_ngos(food_category: str = None) -> List[Dict[str, Any]]:
    ngos = get_all_ngos()
    available = []

    for ngo in ngos:
        try:
            current = int(ngo.get("capacity_current", 0) or 0)
            daily = int(ngo.get("capacity_daily", 0) or 0)
        except Exception:
            current = ngo.get("capacity_current", 0) or 0
            daily = ngo.get("capacity_daily", 0) or 0

        if daily and current >= daily:
            continue

        if food_category:
            food_prefs = ngo.get("food_preferences", "") or ""
            if food_category not in food_prefs:
                continue

        available.append(ngo)

    return available


def update_ngo_capacity(ngo_id: str, food_quantity: int) -> bool:
    ngo = get_ngo_by_id(ngo_id)
    if not ngo:
        return False

    try:
        current = int(ngo.get("capacity_current", 0) or 0)
    except Exception:
        current = 0

    new_value = current + int(food_quantity or 0)

    res = db_patch("ngos", {"id": ngo_id}, capacity_current=new_value)
    return bool(res and getattr(res, "ok", False))
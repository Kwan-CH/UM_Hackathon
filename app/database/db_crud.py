import os
from types import SimpleNamespace
from typing import Any, Dict
import requests
from dotenv import load_dotenv


load_dotenv()

# only fixed the port and ip, dynamic link with table name as function parameter
base_url = f"http://{os.getenv('POSTGREST_IP')}:{os.getenv('POSTGREST_PORT')}"

headers = {
    "Authorization": f"Bearer {os.getenv('POSTGREST_TOKEN')}",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Prefer": "return=representation",
}

def db_create(table_name, **payload):
    unpacked = SimpleNamespace(**payload)
    data = {k: getattr(unpacked, k) for k in payload.keys()}

    create_url = f"{base_url}/{table_name}"
    response = db_action(
        request_method="POST",
        request_url=create_url,
        request_headers=headers,
        request_data=data,
    )
    return response

# **kwargs only accept ngo_status
def db_update_accept(table_name, ngo_id, request_id, **kwargs):
    patch_url = f"{base_url}/{table_name}?request_id=eq.{request_id}&ngo_id=eq.{ngo_id}"
    response = db_action(request_method="PATCH", request_url=patch_url, request_headers=headers, request_data=kwargs)
    return response

def db_update_reject(table_name, ngo_id, request_id, **kwargs):
    patch_url = f"{base_url}/{table_name}?request_id=eq.{request_id}&ngo_id=neq.{ngo_id}"
    response = db_action(request_method="PATCH", request_url=patch_url, request_headers=headers, request_data=kwargs)
    return response


def db_patch(table_name, filters: Dict[str, Any], **kwargs):
    parts = []
    for k, v in (filters or {}).items():
        if v is None:
            continue
        parts.append(f"{k}=eq.{v}")

    patch_url = f"{base_url}/{table_name}"
    if parts:
        patch_url = patch_url + "?" + "&".join(parts)

    response = db_action(request_method="PATCH", request_url=patch_url, request_headers=headers, request_data=kwargs)
    return response

# does not require table name since rpc function is bound to a specific table only
def db_update_journey_status(task_type_c, uuid_x, **kwargs):
    """
    only use this function when you want to duplicate the entry but with different value
    by providing the correspond task type
    """
    rpc_function_name = None

    # dynamic populate the rpc function name based on task type
    if task_type_c == "document":
        rpc_function_name = "update_journey_status"
    elif task_type_c == "email":
        rpc_function_name = ""
    elif task_type_c == "notice":
        rpc_function_name = ""
    elif task_type_c == "notice":
        rpc_function_name = ""

    insert_select_url = f"{base_url}/rpc/{rpc_function_name}"

    # construct placeholder for optional param in postgresSQL for rpc
    # optional param can refer to db.sql at .\report-queue\docker_services\postgresql\db.sql
    new_keys = ["new_" + i for i in kwargs.keys()]
    new_mapping = dict(zip(new_keys, kwargs.values()))
    new_mapping["match_uuid_x"] = uuid_x

    response = db_action(request_method="POST", request_url=insert_select_url, request_headers=headers, request_data=new_mapping)
    return response

def db_get(table_name, **filters):
    parts = []
    for k, v in (filters or {}).items():
        if v is None:
            continue
        parts.append(f"{k}=eq.{v}")

    get_url = f"{base_url}/{table_name}"
    if parts:
        get_url = get_url + "?" + "&".join(parts)

    response = db_action(request_method="GET", request_url=get_url, request_headers=headers)
    return response

# plain delete based on uuid ONLY
# if were multiple entry shared the same UUID, regardless of any condition you wanted to add will not be considered
# thus those rows will be deleted
def db_delete(table_name, uuid_x):
    delete_url = f"{base_url}/{table_name}?uuid_x=eq.{uuid_x}"
    response = db_action(request_method="DELETE", request_url=delete_url, request_headers=headers)
    return

def db_action(request_method, request_url, request_headers, request_data=None):
    try:
        response = requests.request(
            method=request_method,
            url=request_url,
            headers=request_headers,
            json=request_data,
            timeout=30,
        )
        return response
    except Exception:
        print("Both PostgresSQL database and postgREST service are down, the journey status will not be recorded down")
        return None

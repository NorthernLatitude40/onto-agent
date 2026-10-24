"""SQL for the scraper_configs table. No FastAPI imports here."""
import json
from typing import Optional, List

from ..db import get_cursor

_COLS = "id, name, target_url, headers, timeout, is_active, mode, group_id, created_at, updated_at"
_UPDATABLE = {"name", "target_url", "headers", "timeout", "is_active", "mode", "group_id"}


def _parse_headers(raw):
    if raw and isinstance(raw, str) and raw != "null":
        return json.loads(raw)
    return raw


def _to_detail(row) -> dict:
    return {
        "id": row[0],
        "name": row[1],
        "target_url": row[2],
        "headers": _parse_headers(row[3]),
        "timeout": row[4],
        "is_active": row[5],
        "mode": str(row[6]),
        "created_at": str(row[7]) if row[7] is not None else None,
        "updated_at": str(row[8]) if row[8] is not None else None,
    }


# Cache for list_active results
_last_cache = []
_last_updated = 0
_CACHE_TTL = 5  # 5 seconds cache duration

def list_active() -> list:
    """Get all active scraper configs with caching for better performance."""
    import time
    global _last_cache, _last_updated
    
    # Return cached data if still valid and not empty
    if time.time() - _last_updated < _CACHE_TTL and _last_cache:
        return _last_cache.copy()
    
    # Query database for fresh data
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, name, target_url, is_active, mode, created_at
            FROM scraper_configs WHERE is_active = TRUE ORDER BY name;
            """
        )
        _last_cache = [
            {
                "id": r[0], "name": r[1], "target_url": r[2],
                "is_active": r[3], "mode": str(r[4]),
                "created_at": str(r[5]) if r[5] is not None else None,
            }
            for r in cur.fetchall()
        ]
        _last_updated = time.time()
    return _last_cache.copy()


def get_by_group_id(config_id: int) -> List[dict]:
    with get_cursor() as cur:
        cur.execute(f"SELECT {_COLS} FROM scraper_configs WHERE group_id = %s;", (config_id,))
        rows = cur.fetchall()
        details = [_to_detail(row) for row in rows]
        return details

def get_by_id(config_id: int) -> Optional[dict]:
    with get_cursor() as cur:
        cur.execute(f"SELECT {_COLS} FROM scraper_configs WHERE id = %s;", (config_id,))
        row = cur.fetchone()
        return _to_detail(row) if row else None


def create(name, target_url, headers, timeout, mode, group_id) -> dict:
    headers_json = json.dumps(headers) if headers else None
    with get_cursor(commit=True) as cur:
        cur.execute(
            f"""
            INSERT INTO scraper_configs (name, target_url, headers, timeout, mode, group_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING {_COLS};
            """,
            (name, target_url, headers_json, timeout, mode, group_id),
        )
        return _to_detail(cur.fetchone())


def update(config_id: int, fields: dict) -> Optional[dict]:
    """fields: only keys in _UPDATABLE with non-None values. Returns None if not found."""
    fields = {k: v for k, v in fields.items() if k in _UPDATABLE and v is not None}
    if "headers" in fields:
        fields["headers"] = json.dumps(fields["headers"])
    set_clause = ", ".join(f"{k} = %s" for k in fields) + ", updated_at = NOW()"
    with get_cursor(commit=True) as cur:
        cur.execute(
            f"UPDATE scraper_configs SET {set_clause} WHERE id = %s RETURNING {_COLS};",
            (*fields.values(), config_id),
        )
        row = cur.fetchone()
        return _to_detail(row) if row else None


def soft_delete(config_id: int) -> bool:
    with get_cursor(commit=True) as cur:
        cur.execute(
            "UPDATE scraper_configs SET is_active = FALSE, updated_at = NOW() "
            "WHERE id = %s RETURNING id;",
            (config_id,),
        )
        return cur.fetchone() is not None


def get_steps_by_config_id(config_id: int) -> list:
    """Get all crawler steps for a specific scraper config."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, scraper_config_id, name, target_type, target_url, config, enabled
            FROM crawler_steps
            WHERE scraper_config_id = %s AND enabled = TRUE
            ORDER BY created_at;
            """,
            (config_id,),
        )
        steps = []
        for row in cur.fetchall():
            step_data = {
                "id": str(row[0]),
                "scraper_config_id": row[1],
                "name": row[2],
                "target_type": row[3],
                "target_url": row[4],
                "config": row[5] if row[5] else {},
                "enabled": row[6],
            }
            steps.append(step_data)
    return steps


import json

def create_steps(config_id: int, steps_data) -> list:
    """Create multiple crawler steps for a scraper config."""
    if not steps_data:
        return []
    
    created_steps = []
    with get_cursor(commit=True) as cur:
        for step in steps_data:
            # 兼容处理：将 Pydantic 模型转换为字典，防止 .get() 报错
            if hasattr(step, "model_dump"):
                step_dict = step.model_dump()
            elif hasattr(step, "dict"):
                step_dict = step.dict()
            elif isinstance(step, dict):
                step_dict = step
            else:
                step_dict = dict(step)
            
            # 提取 step 字段
            name = step_dict.get("name", "")
            target_type = step_dict.get("mode", "api")  # Map mode to target_type
            target_url = step_dict.get("target_url", "")
            
            # 处理 parsing_rules 内部可能存在的 Pydantic 对象
            parsing_rules = step_dict.get("parsing_rules", [])
            jsonpath = parsing_rules.get("jsonpath", None)  # Add jsonpath if present

            # Build config JSON from step data
            config_dict = {
                "method": step_dict.get("method", "GET"),
                "params": step_dict.get("params"),
                "headers": step_dict.get("headers"),
                "parsing_rules": parsing_rules,
                "delay": step_dict.get("delay"),
                "retry_count": step_dict.get("retry_count"),
            }
            config_json = json.dumps(config_dict)
            
            # Insert the step
            cur.execute(
                """
                INSERT INTO crawler_steps
                    (scraper_config_id, name, target_type, target_url, config)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, scraper_config_id, name, target_type, target_url, enabled;
                """,
                (config_id, name, target_type, target_url, config_json),
            )
            result = cur.fetchone()
            if result:
                created_steps.append({
                    "id": result[0],
                    "scraper_config_id": result[1],
                    "name": result[2],
                    "target_type": result[3],
                    "target_url": result[4],
                    "enabled": result[5],
                })
    
    return created_steps
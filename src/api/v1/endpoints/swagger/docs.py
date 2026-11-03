"""OpenAPI response examples, kept out of the route files."""

_DB_ERROR = {
    "description": "数据库查询失败",
    "content": {"application/json": {"example": {"detail": "数据库查询失败: connection error"}}},
}

LIST_CONFIGS_RESPONSES = {
    200: {
        "description": "成功返回爬虫配置列表",
        "content": {"application/json": {"example": [
            {"id": 1, "name": "GetLost NZ Campervan Scraper",
             "target_url": "https://getlostinnz.co.nz/", "is_active": True,
             "mode": "api", "created_at": "2024-01-15T10:30:00.000Z"},
            {"id": 2, "name": "Spaceships Campervans Scraper",
             "target_url": "https://spaceships.co.nz/", "is_active": True,
             "mode": "html", "created_at": "2024-01-16T14:20:00.000Z"},
        ]}},
    },
    500: _DB_ERROR,
}

CREATE_CONFIG_EXAMPLE = {
    "name": "範例爬蟲任務",
    "target_url": "http://localhost:5173/scraper-config",
    "headers": {"User-Agent": "Mozilla/5.0"},
    "timeout": 10,
    "mode": "api",
    "steps": [{
        "name": "初始請求", "mode": "api",
        "url": "http://localhost:5173/scraper-config", "method": "GET",
        "params_json": "{}", "headers_json": "{}", "parsing_rules": [],
    }],
}

UPDATE_CONFIG_EXAMPLE = {
    "name": "Updated Campervan Scraper",
    "target_url": "https://updated-url.com/",
    "headers": {"User-Agent": "Mozilla/5.0"},
    "timeout": 20,
    "is_active": True,
}

GET_CONFIG_RESPONSES = {
    200: {
        "description": "成功返回爬虫配置详情",
        "content": {"application/json": {"example": {
            "id": 1, "name": "GetLost NZ Campervan Scraper",
            "target_url": "https://getlostinnz.co.nz/",
            "headers": {"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            "timeout": 10, "is_active": True, "mode": "api",
            "steps": [{
                "id": "step-1", "name": "获取车型列表", "mode": "api",
                "url": "https://getlostinnz.co.nz/wp-json/getlost/v1/rcm/step2",
                "method": "POST",
                "params_json": "{\"pickupdate\": \"2026-11-10\"}",
                "headers_json": "{\"Content-Type\": \"application/json\"}",
                "parsing_rules": [{
                    "id": "rule-1", "name": "解析车型列表",
                    "jsonpath": "$.cars[*].vehiclecategory",
                    "output_field": "model_name", "required": True,
                }],
                "delay": 1000, "retry_count": 3,
            }],
            "created_at": "2024-01-15T10:30:00.000Z",
            "updated_at": "2024-01-16T14:20:00.000Z",
        }}},
    },
    404: {
        "description": "爬虫配置不存在",
        "content": {"application/json": {"example": {"detail": "爬虫配置 ID 123 不存在"}}},
    },
    500: _DB_ERROR,
}

EXECUTE_EXAMPLE = {"config_id": 1, "pickup_date": "2026-11-10", "return_date": "2026-11-15"}

VEHICLES_RESPONSES = {
    200: {
        "description": "成功返回车型列表",
        "content": {"application/json": {"example": [
            {"model_name": "4WD Campervan", "berths": 3, "transmission": "Manual",
             "specs": {"solar": True, "battery": "100Ah LiFePO4", "heater": "Diesel", "bed": "Double bed"},
             "price_nzd": 125.0, "pickup_date": "2026-11-10", "return_date": "2026-11-15"},
        ]}},
    },
    500: _DB_ERROR,
}

from fastapi import APIRouter, Request
from typing import Dict, Any

router = APIRouter()

@router.post("/test-step-request")
async def test_step_request(request: Request):
    """
    Test endpoint that simulates API responses from step 1 (first scraping step)
    for frontend manual JSON input feature.

    Accepts POST requests with URL, method, headers, params, and body.
    Returns mock JSON data that resembles real API responses.
    """

    # Get request data
    request_data = await request.json()

    # Validate required fields
    if not all(key in request_data for key in ["url", "method"]):
        return {
            "code": 400,
            "message": "Missing required fields: url and method are required",
            "data": None
        }

    # Create mock response data based on the request
    mock_response_data = {
        "data": [
            {"name": "user_id", "type": "string", "value": "12345"},
            {"name": "username", "type": "string", "value": "john_doe"},
            {"name": "email", "type": "string", "value": "john@example.com"},
            {"name": "created_at", "type": "datetime", "value": "2023-01-15T10:30:00Z"}
        ],
        "metadata": {
            "status_code": 200,
            "headers": request_data.get("headers", {}),
            "timestamp": "2024-01-15T10:30:00Z"
        }
    }

    # Return success response
    return {
        "code": 200,
        "message": "Test step request completed successfully",
        "data": mock_response_data
    }
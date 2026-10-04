#!/usr/bin/env python3
"""
Simple test server for registration API
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

app = FastAPI()

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str

class ApiResponse(BaseModel):
    success: bool
    message: str
    data: dict | None = None

# In-memory database for testing
users_db = []

@app.post("/api/v1/auth/register", response_model=ApiResponse)
def register_user(request: RegisterRequest):
    """Test registration endpoint"""
    
    # Check if user already exists
    for user in users_db:
        if user["username"] == request.username or user["email"] == request.email:
            return ApiResponse(
                success=False,
                message="Username or email already exists"
            )
    
    # Create new user
    new_user = {
        "id": len(users_db) + 1,
        "username": request.username,
        "email": request.email
    }
    
    users_db.append(new_user)
    
    return ApiResponse(
        success=True,
        message="User registered successfully",
        data=new_user
    )

@app.get("/api/v1/auth/users")
def get_users():
    """Get all registered users (for testing)"""
    return {"users": users_db}

if __name__ == "__main__":
    print("🚀 Starting test server on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
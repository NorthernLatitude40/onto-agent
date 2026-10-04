# User Registration API Documentation

## Overview
This document describes the user registration API endpoint that allows users to create new accounts.

## Base URL
```
http://localhost:8000/api/v1/auth/register
```

## Endpoint

### POST /api/v1/auth/register

Creates a new user account.

#### Request Body

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| username | string | Yes | Username | Minimum 3 characters |
| email | string | Yes | Email address | Valid email format |
| password | string | Yes | Password | Minimum 6 characters |

#### Request Example
```json
{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "secure123"
}
```

#### Response

**Success (200 OK)**
```json
{
  "code": 200,
  "message": "User registered successfully",
  "data": {
    "user_id": 1,
    "username": "john_doe",
    "email": "john@example.com"
  }
}
```

**Error (400 Bad Request)**
```json
{
  "code": 400,
  "message": "Username must be at least 3 characters long"
}
```

## Error Codes

| Code | Message |
|------|---------|
| 400 | Username must be at least 3 characters long |
| 400 | Invalid email format |
| 400 | Password must be at least 6 characters long |
| 400 | Username already exists |
| 400 | Email already exists |

## Frontend Integration

The frontend Vue.js component connects to this API as follows:

```javascript
const onRegister = async () => {
  const { username, email, password } = registerForm.value;
  
  try {
    const response = await fetch('http://localhost:8000/api/v1/auth/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        username,
        email,
        password
      })
    });
    
    const data = await response.json();
    
    if (response.ok && data.success) {
      alert('Registration successful!');
      // Reset form and close modal
    } else {
      alert(`Registration failed: ${data.message || 'Unknown error'}`);
    }
  } catch (error) {
    console.error('Registration error:', error);
    alert('Network error during registration');
  }
};
```

## Testing

Run the test server:
```bash
python test_server.py
```

Test with curl:
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "email": "test@example.com", "password": "password123"}'
```

## Database Schema

The user data is stored in the `sys_user` table:
- `id`: BigInteger (primary key, autoincrement)
- `openid`: String(64) (unique, nullable=False) - used for username
- `email`: String (nullable=True) - email address
- `default_shop_id`: Integer (nullable=True)
- `default_staff_id`: Integer (nullable=True)
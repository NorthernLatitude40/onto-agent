# Playwright Mode Examples

This document provides practical examples of Playwright configuration for various scraping scenarios.

## Table of Contents
- [Basic Page Scraping](#basic-page-scraping)
- [JavaScript Data Extraction](#javascript-data-extraction)
- [API with Authentication](#api-with-authentication)
- [Form Submission](#form-submission)
- [Pagination Scraping](#pagination-scraping)
- [Complex Sequential Workflow](#complex-sequential-workflow)

## Basic Page Scraping

Scrape content from a simple webpage and extract HTML:

```json
{
  "mode": "playwright",
  "steps": [
    {
      "type": "playwright",
      "url": "https://example.com/products",
      "wait_selector": "#product-list",
      "timeout": 15000
    }
  ]
}
```

**Use case**: Scraping static content that loads with the initial page HTML.

---

## JavaScript Data Extraction

Extract data from a Single Page Application (SPA) using JavaScript:

```json
{
  "mode": "playwright",
  "steps": [
    {
      "type": "playwright",
      "url": "https://example.com/dashboard",
      "wait_selector": "#app",
      "execute_javascript": "return JSON.parse(document.getElementById('app').dataset.content);"
    }
  ]
}
```

**Use case**: Websites that load data via JavaScript after the initial page load.

---

## API with Authentication

Scrape an API endpoint with custom headers and authentication:

```json
{
  "mode": "playwright",
  "steps": [
    {
      "type": "playwright",
      "url": "https://api.example.com/vehicles",
      "headers": {
        "Authorization": "Bearer your_access_token_here",
        "Content-Type": "application/json",
        "Accept": "application/json"
      },
      "wait_selector": "pre",
      "timeout": 30000
    }
  ]
}
```

**Use case**: Protected API endpoints that require authentication headers.

---

## Form Submission

Submit a login form and scrape the resulting page:

```json
{
  "mode": "playwright",
  "steps": [
    {
      "type": "playwright",
      "url": "https://example.com/login",
      "execute_javascript": "
        document.querySelector('#username').value = 'your_username';
        document.querySelector('#password').value = 'your_password';
        document.querySelector('form').submit();
        return true;
      "
    },
    {
      "type": "playwright",
      "url": "https://example.com/dashboard",
      "wait_selector": "#user-profile"
    }
  ]
}
```

**Use case**: Websites that require form submission for authentication.

---

## Pagination Scraping

Scrape multiple pages by clicking "Next" buttons:

```json
{
  "mode": "playwright",
  "steps": [
    {
      "type": "playwright",
      "url": "https://example.com/products?page=1",
      "wait_selector": "#product-grid"
    },
    {
      "type": "playwright",
      "execute_javascript": "
        const nextButton = document.querySelector('a[rel=\"next\"]');
        if (nextButton) {
          nextButton.click();
          return true;
        }
        return false;
      "
    },
    {
      "type": "playwright",
      "wait_selector": "#product-grid"
    }
  ]
}
```

**Use case**: Websites with pagination that load content via AJAX.

---

## Complex Sequential Workflow

A complete workflow with multiple steps and context passing:

```json
{
  "mode": "playwright",
  "steps": [
    {
      "type": "playwright",
      "url": "https://example.com/api/auth",
      "headers": {
        "Content-Type": "application/json"
      },
      "execute_javascript": "
        const response = await fetch('https://example.com/api/auth', {
          method: 'POST',
          body: JSON.stringify({username: 'user', password: 'pass'})
        });
        const data = await response.json();
        return data.token;
      "
    },
    {
      "type": "playwright",
      "url": "https://example.com/api/vehicles?token={token}",
      "params": {},
      "headers": {
        "Authorization": "Bearer {token}"
      },
      "wait_selector": "pre"
    },
    {
      "type": "playwright",
      "url": "https://example.com/api/vehicles/{vehicle_id}/details",
      "params": {
        "vehicle_id": "12345"
      }
    }
  ]
}
```

**Use case**: Multi-step workflows where data from one step is used in subsequent steps.

---

## Vehicle Scraper Specific Examples

### Example 1: Scraping Vehicle Listings from a Dealership Site

```json
{
  "mode": "playwright",
  "steps": [
    {
      "type": "playwright",
      "url": "https://dealership.com/vehicles?make=Toyota&model=Camry",
      "wait_selector": "#vehicle-list",
      "viewport": {
        "width": 1920,
        "height": 1080
      },
      "timeout": 20000
    }
  ]
}
```

### Example 2: Scraping Vehicle Details with JavaScript Rendering

```json
{
  "mode": "playwright",
  "steps": [
    {
      "type": "playwright",
      "url": "https://dealership.com/vehicle/{vin}",
      "params": {
        "vin": "JT2BF12E0W1000000"
      },
      "wait_selector": "#vehicle-details",
      "execute_javascript": "
        return {
          make: document.querySelector('[data-testid=\"make\"]').textContent,
          model: document.querySelector('[data-testid=\"model\"]').textContent,
          year: document.querySelector('[data-testid=\"year\"]').textContent,
          price: document.querySelector('[data-testid=\"price\"]').textContent
        };
      "
    }
  ]
}
```

### Example 3: Scraping with Proxy for Anti-Scraping Protection

```json
{
  "mode": "playwright",
  "steps": [
    {
      "type": "playwright",
      "url": "https://protected-dealership.com/inventory",
      "wait_selector": "#inventory-grid",
      "proxy": {
        "server": "http://proxy-server:8080"
      },
      "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
      "timeout": 30000
    }
  ]
}
```

---

## Complete Configuration with Parsing Rules

Here's a complete example including parsing rules:

```json
{
  "mode": "playwright",
  "steps": [
    {
      "type": "playwright",
      "url": "https://dealership.com/search?location=NewZealand&radius=100",
      "wait_selector": "#results-container",
      "timeout": 25000
    }
  ],
  "parsing_rules": [
    {
      "field": "make",
      "selector": "div.vehicle-make",
      "type": "text"
    },
    {
      "field": "model",
      "selector": "div.vehicle-model",
      "type": "text"
    },
    {
      "field": "year",
      "selector": "div.vehicle-year",
      "type": "number"
    },
    {
      "field": "price",
      "selector": "div.vehicle-price",
      "type": "currency",
      "currency": "NZD"
    }
  ]
}
```

---

## API Documentation

### Execute Scrape Endpoint

**URL**: `POST /api/v1/scraper/execute`

**Request Body**:
```json
{
  "config_id": 1,
  "parsing_rules": [
    {
      "field": "make",
      "selector": "div.make",
      "type": "text"
    }
  ]
}
```

**Response**:
```json
{
  "success": true,
  "data": [
    {
      "make": "Toyota",
      "model": "Camry",
      "year": 2023,
      "price": 45000
    }
  ],
  "timestamp": "2023-11-07T10:36:53.256Z"
}
```

**Parameters**:
- `config_id` (required): The ID of the scraper configuration to execute
- `parsing_rules` (optional): Custom parsing rules to override those in the configuration

---

### Preview Step Data Endpoint

**URL**: `POST /api/v1/scraper/preview-step-data`

**Request Body**:
```json
{
  "step": {
    "type": "playwright",
    "url": "https://example.com/test",
    "wait_selector": "#content"
  }
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "html": "<div id='content'>Test Content</div>",
    "url": "https://example.com/test",
    "status": "completed"
  }
}
```

**Parameters**:
- `step` (required): A single step configuration to preview

---

## Testing Your Configuration

### Using curl to Test API Endpoints

Test the execute endpoint:

```bash
curl -X POST \
  https://your-api.example.com/api/v1/scraper/execute \
  -H 'Content-Type: application/json' \
  -d '{"config_id": 1}'
```

Test the preview endpoint:

```bash
curl -X POST \
  https://your-api.example.com/api/v1/scraper/preview-step-data \
  -H 'Content-Type: application/json' \
  -d '{"step": {"type": "playwright", "url": "https://example.com"}}'
```

### Using Python to Test

```python
import requests
import json

# Execute a scrape configuration
response = requests.post(
    "https://your-api.example.com/api/v1/scraper/execute",
    json={"config_id": 1},
    headers={"Content-Type": "application/json"}
)
print(response.json())

# Preview a single step
step_config = {
    "type": "playwright",
    "url": "https://example.com/test"
}
response = requests.post(
    "https://your-api.example.com/api/v1/scraper/preview-step-data",
    json={"step": step_config},
    headers={"Content-Type": "application/json"}
)
print(response.json())
```

---

## Error Handling and Status Codes

### Success Responses (2xx)
- `200 OK`: Request processed successfully
- `201 Created`: Resource created successfully

### Client Errors (4xx)
- `400 Bad Request`: Invalid request format or parameters
- `401 Unauthorized`: Authentication required or failed
- `404 Not Found`: Configuration or resource not found
- `422 Unprocessable Entity`: Configuration validation failed

### Server Errors (5xx)
- `500 Internal Server Error`: Unexpected server error
- `503 Service Unavailable`: Service temporarily unavailable
- `504 Gateway Timeout`: Request timed out

---

## Rate Limiting

The API has rate limiting in place:
- Default limit: 100 requests per minute
- Playwright mode: 20 requests per minute (due to resource intensity)

If you exceed the rate limit, you'll receive a `429 Too Many Requests` response with a `Retry-After` header indicating when you can make more requests.

---

## Webhook Notifications

You can configure webhooks to receive notifications when scrapes complete:

```json
{
  "mode": "playwright",
  "steps": [...],
  "webhook_url": "https://your-callback.example.com/webhook",
  "webhook_events": ["success", "failure"]
}
```

Webhook payload example:
```json
{
  "event": "scrape.success",
  "config_id": 1,
  "timestamp": "2023-11-07T10:36:53.256Z",
  "data": {
    "count": 42,
    "vehicles": [...]
  }
}
```

---

## Monitoring and Logging

All Playwright scrapes are logged with detailed information:
- Start time and end time
- Duration
- Number of steps executed
- Success/failure status for each step
- Any errors encountered

You can view logs through the admin interface or via API.

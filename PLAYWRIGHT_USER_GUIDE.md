# Playwright Mode User Guide

This guide explains how to use the Playwright mode for web scraping in the vehicle scraper system.

## Overview

Playwright mode allows you to scrape data from websites that require browser automation, such as:
- JavaScript-rendered pages
- Pages with anti-scraping measures
- Pages requiring user interaction
- Single Page Applications (SPAs)

## Configuration Structure

A Playwright step configuration has the following structure:

```json
{
  "type": "playwright",
  "url": "https://example.com/api",
  "wait_selector": "#content",
  "execute_javascript": "document.querySelector('#data').innerHTML",
  "headers": {
    "User-Agent": "CustomAgent/1.0"
  },
  "proxy": {
    "server": "http://proxy.example.com:8080"
  },
  "timeout": 30000,
  "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
  "viewport": {
    "width": 1280,
    "height": 720
  }
}
```

## Configuration Options

### Required Fields

- **`type`** (string): Must be `"playwright"` to use Playwright mode
- **`url`** (string): The URL to navigate to

### Optional Fields

- **`wait_selector`** (string): CSS selector to wait for before proceeding. Example: `#content`, `.class-name`
- **`execute_javascript`** (string): JavaScript code to execute on the page. Returns the result.
- **`headers`** (object): Custom HTTP headers to send with the request
- **`proxy`** (object): Proxy server configuration
  - `server`: Proxy URL (e.g., `http://proxy.example.com:8080`)
  - `username`: Optional proxy username
  - `password`: Optional proxy password
- **`timeout`** (number): Timeout in milliseconds for page operations (default: 10000)
- **`user_agent`** (string): Custom user agent string
- **`viewport`** (object): Browser viewport size
  - `width`: Viewport width in pixels
  - `height`: Viewport height in pixels

## Parameter Interpolation

You can use parameters with context variables using the `{variable}` syntax:

```json
{
  "type": "playwright",
  "url": "https://example.com/api?token={token}",
  "params": {
    "token": "your_token_here"
  }
}
```

The `{token}` in the URL will be replaced with the value from `params.token`.

## Example Configurations

### Basic Page Scraping

Scrape content from a simple webpage:

```json
{
  "type": "playwright",
  "url": "https://example.com/products",
  "wait_selector": "#product-list"
}
```

### JavaScript Data Extraction

Extract data using JavaScript:

```json
{
  "type": "playwright",
  "url": "https://example.com/api/data",
  "execute_javascript": "return JSON.parse(document.getElementById('app').dataset.content);"
}
```

### API with Authentication

Scrape an API endpoint with custom headers:

```json
{
  "type": "playwright",
  "url": "https://api.example.com/vehicles",
  "headers": {
    "Authorization": "Bearer your_token_here",
    "Content-Type": "application/json"
  },
  "wait_selector": "pre"
}
```

### Sequential Steps with Context Passing

Execute multiple Playwright steps where data from one step is used in the next:

```json
[
  {
    "type": "playwright",
    "url": "https://example.com/login",
    "execute_javascript": "document.querySelector('#username').value = 'user'; document.querySelector('#password').value = 'pass'; return true;"
  },
  {
    "type": "playwright",
    "url": "https://example.com/dashboard?session={session_id}",
    "params": {}
  }
]
```

## Best Practices

1. **Use Specific Selectors**: Always use specific CSS selectors to avoid waiting for unnecessary elements.

2. **Set Appropriate Timeouts**: Adjust timeouts based on page load times (default is 10 seconds).

3. **Handle Errors Gracefully**: Playwright mode handles errors gracefully and continues with the next step if one fails.

4. **Use Proxies for Anti-Scraping**: If websites block scrapers, use proxy servers to distribute requests.

5. **Custom User Agents**: Some sites check user agent strings - set a realistic browser user agent.

6. **Viewport Size**: Set viewport size to match common devices (e.g., 1280x720 for desktop).

## Troubleshooting

### Common Issues and Solutions

**Issue: Page not loading correctly**
- Check if the URL is correct
- Increase the timeout value
- Verify network connectivity

**Issue: Selector not found**
- Verify the CSS selector exists on the page
- Use browser developer tools to inspect elements
- Add a longer wait time

**Issue: JavaScript execution fails**
- Check for syntax errors in your JavaScript code
- Ensure the page is fully loaded before executing JS
- Wrap return statements properly

**Issue: Proxy connection failed**
- Verify proxy server is running
- Check proxy credentials if authentication is required
- Test proxy connectivity manually

## API Endpoints

### Execute Scrape

```bash
POST /api/v1/scraper/execute
Content-Type: application/json

{
  "config_id": 1,
  "parsing_rules": [...]
}
```

### Preview Step Data

```bash
POST /api/v1/scraper/preview-step-data
Content-Type: application/json

{
  "step": {
    "type": "playwright",
    "url": "https://example.com"
  }
}
```

## Testing Your Configuration

Before running a full scrape, test your configuration:

1. Use the **Preview Step Data** API endpoint to test individual steps
2. Check the response for errors or unexpected results
3. Adjust selectors, timeouts, or JavaScript as needed
4. Test with multiple steps to ensure context is passed correctly

## Performance Considerations

- Playwright mode is slower than direct HTTP requests due to browser overhead
- Each step creates a new page instance by default
- For sequential steps on the same domain, consider reusing the same browser context
- Monitor resource usage when running multiple Playwright scrapes concurrently

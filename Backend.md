# ATIP API v2.0 - Frontend Integration Guide

A comprehensive REST API for accessing academic talent and research data. This API provides normalized access to authors, papers, citations, and academic metrics through a clean, well-documented interface.

## 🚀 Quick Start for Frontend Developers

### API Base URL
```
http://18.143.177.82/          # Production (via nginx, remote access)
http://18.143.177.82:8000/     # Development (direct FastAPI, remote access)
```
> **Note:** If you are running the frontend on a different machine or network, always use the public IP address of your AWS server (e.g., `18.143.177.82`) instead of `localhost`.

### Health Check
```bash
curl http://localhost/health
# Returns: "healthy"
```

### Interactive Documentation
Visit `http://localhost/docs` for the complete Swagger UI documentation with live testing capabilities.

## 📊 Database Schema Overview

The API provides access to four main data entities:

| Entity | Description | Key Fields |
|--------|-------------|------------|
| **Authors** | Academic researchers | `author_id`, `first_name`, `last_name`, `affiliation`, `pqi`, `anci_frac`, `cagr` |
| **Papers** | Research publications | `paper_id`, `title`, `abstract`, `venue`, `year`, `citation_count` |
| **Authorships** | Author-paper relationships | `author_id`, `paper_id`, `is_first_author`, `is_last_author` |
| **Citations** | Paper citation details | `target_paper_id`, `citing_paper_id`, `year_cited`, `contexts` |

## 🔌 API Endpoints for Frontend Integration

### Core Endpoints
```javascript
// Health check
GET /health
Response: "healthy"

// API info
GET /
Response: { "message": "Welcome to the ATIP API v2.0" }

// OpenAPI schema (for code generation)
GET /openapi.json
```

### Author Endpoints
```javascript
// List all authors (paginated or search)
GET /authors/?skip=0&limit=20
GET /authors/?search=QUERY
Response: Array of author objects

// Get specific author
GET /authors/{author_id}
Response: Single author object

// Get all papers by an author
GET /authors/{author_id}/papers
Response: Array of paper objects

// Get author's publication history
GET /authors/{author_id}/authorships
Response: Array of authorship objects

// Get coauthor network for an author
GET /authors/{author_id}/coauthors
Response: Array of coauthor objects
```

### Paper Endpoints
```javascript
// List all papers (paginated)
GET /papers/?skip=0&limit=20
Response: Array of paper objects

// Get specific paper
GET /papers/{paper_id}
Response: Single paper object

// Get all authors of a paper
GET /papers/{paper_id}/authors
Response: Array of author objects

// Get paper's authorship details
GET /papers/{paper_id}/authorships
Response: Array of authorship objects

// Get paper's citations
GET /papers/{paper_id}/citations
Response: Array of citation objects
```

### Ranking Endpoints
```javascript
// Top authors by PQI score
GET /rankings/pqi?limit=100
Response: Array of ranked author objects

// Top authors by ANCI score
GET /rankings/anci?limit=100
Response: Array of ranked author objects

// Top authors by CAGR score
GET /rankings/cagr?limit=100
Response: Array of ranked author objects
```

### Stats Endpoints
```javascript
// Get database statistics for home page
GET /stats/overview
Response: Stats overview object
```

## 📋 Data Models

### Author Object
```json
{
  "author_id": 101597616,
  "first_name": "John",
  "last_name": "Doe",
  "affiliation": "Stanford University",
  "h_index": 25,
  "citations": 5000,
  "career_length": 10,
  "publication_count": 50,
  "anci_frac": 15.5,
  "anci_p_frac": 3.1,
  "adj_anci_frac": 2.5,
  "adj_anci_p_frac": 0.5,
  "cagr": 0.8,
  "ltsd": 0.2,
  "pqi": 3.2,
  "first_author_dominance": 0.6
}
```

### Paper Object
```json
{
  "paper_id": 12345,
  "s2_id": "abc123",
  "acl_id": "2023.acl-long.123",
  "doi": "10.18653/v1/2023.acl-long.123",
  "title": "Advanced Natural Language Processing",
  "abstract": "This paper presents...",
  "venue": "ACL",
  "year": 2023,
  "track": "TBD",
  "citation_count": 25,
  "awards": ["Best Paper", "Outstanding Paper"]
}
```

### Authorship Object
```json
{
  "author_id": 101597616,
  "paper_id": 12345,
  "author_name": "John Doe",
  "is_first_author": true,
  "is_last_author": false,
  "title": "Advanced Natural Language Processing"
}
```

### Citation Object
```json
{
  "target_paper_id": 12345,
  "citing_paper_id": 67890,
  "year_cited": 2024,
  "in_dataset": true,
  "contexts": "This work builds upon...",
  "intents": "comparison",
  "is_influential": true
}
```

### Coauthor Object
```json
[
  {
    "author_id": 123,
    "name": "Jane Smith",
    "joint_papers": 5
  },
  {
    "author_id": 456,
    "name": "Bob Lee",
    "joint_papers": 3
  }
]
```

### Stats Overview Object
```json
{
  "total_researchers": 2400000,
  "total_papers": 15700000,
  "total_venues": 450
}
```

## 🔧 Nginx Configuration Details

The API is served through nginx with the following configuration:

### Production Access
- **Base URL**: `http://localhost/` (port 80)
- **Health Check**: `http://localhost/health`
- **Documentation**: `http://localhost/docs`
- **API Schema**: `http://localhost/openapi.json`

### Caching Strategy
- **API Responses**: 5-minute cache for `/authors/`, `/papers/`, `/rankings/` endpoints
- **OpenAPI Schema**: 1-hour cache
- **Health Checks**: No caching

### Security Headers
The nginx configuration includes security headers:
- `X-Frame-Options: SAMEORIGIN`
- `X-Content-Type-Options: nosniff`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`

## 📱 Frontend Development Setup

### CORS Configuration
The API includes CORS middleware allowing requests from:
- `http://localhost:5173` (Vue 3 dev server)
- `http://localhost:8080` (Vue 2 dev server)
- `http://localhost:3000` (React dev server)

### Environment Variables
Set up your frontend environment:
```bash
# .env file
VITE_API_BASE_URL=http://18.143.177.82
REACT_APP_API_BASE_URL=http://18.143.177.82
```


## 🧪 Testing Your Integration

### Test Commands
```bash
# Test health endpoint
curl http://localhost/health

# Test author listing
curl -s http://localhost/authors/?limit=5 | jq .

# Test specific author
curl -s http://localhost/authors/101597616 | jq .

# Test rankings
curl -s http://localhost/rankings/pqi?limit=3 | jq .
```

### Common Test Scenarios
1. **Author Search**: Test pagination and filtering
2. **Paper Details**: Test paper-author relationships
3. **Rankings**: Test different ranking algorithms
4. **Error Handling**: Test with invalid IDs
5. **Performance**: Test with large datasets

## 🚨 Important Notes for Frontend Developers

### Rate Limiting
- The API includes optional rate limiting (currently disabled)
- Monitor response times for large datasets
- Implement client-side caching for frequently accessed data

### Data Types
- All IDs are integers (BIGINT in database)
- Scores (PQI, ANCI, CAGR) are floating-point numbers
- Dates are integers (years)
- Arrays (like `awards`) may be null

### Pagination
- Use `skip` and `limit` parameters for pagination
- Default limit is 100 items
- Maximum recommended limit is 1000 items

### Error Responses
```json
{
  "detail": "Author not found"
}
```

## 📞 Support

For API-related issues:
1. Check the interactive documentation at `http://localhost/docs`
2. Verify the health endpoint at `http://localhost/health`
3. Check service status: `sudo systemctl status atip-api`
4. View logs: `sudo journalctl -u atip-api -f`

## 🔄 API Versioning

- **Current Version**: v2.0
- **Base Path**: No version prefix (all endpoints are v2.0)
- **Backward Compatibility**: Not guaranteed between major versions
- **Migration Guide**: Available for v1.0 to v2.0 migration 
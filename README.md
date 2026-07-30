# Presenton MCP Multitenant Proxy Server

This repository contains a Model Context Protocol (MCP) server that acts
as a secure, multi-tenant proxy between an AI Assistant and the Presenton
backend API. It exposes **44 MCP tools** covering 7 resource domains
with full CRUD and AI-powered generation capabilities.

## ✨ Features

- **🔑 Identity Passthrough** — Extracts the `Authorization: Bearer <token>`
  header from incoming HTTP requests and forwards it to the Presenton API
  without server-side authentication.
- **👥 Multi-Tenancy** — Uses Python `contextvars` to maintain thread-safe
  user identity isolation, ensuring all AI-driven actions are scoped to
  the authenticated user's permissions.
- **📊 Full Presenton Coverage** — 44 tools mapped to Presenton API endpoints
  across 7 resource domains.
- **⚡ TOON Optimization** — Bulk list responses are automatically compressed
  using TOON (Token-Optimized Object Notation) to reduce token consumption
  and maximize context window efficiency.
- **🚀 Efficient Gets** — GET responses return only commonly used fields by
  default. Full objects are available via an `include_all_fields` flag.
- **🧪 Comprehensive Testing** — 55 automated tests covering all tool
  domains, run via the test runner pipeline.

## 🔧 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `PRESENTON_BASE_URL` | Yes | Docker-internal URL of the Presenton API (e.g. `http://presenton-app:80`). |
| `MCP_SERVER_PORT` | Yes | Port number the MCP server listens on |
| `ALLOW_ALL_AGGREGATE` | No | When `true`, aggregate listing tools honor the `include_all_fields` parameter. When `false` (default), the parameter is silently forced to `False` for aggregate list operations. |
| `IS_STATEFUL` | No | When `true`, uses stateful Streamable HTTP with session tracking. When `false` (default), uses stateless mode. |

## 📦 Installation & Local Development

1. Ensure you have Python 3.12+ installed.
2. Install dependencies:
    ```bash
    pip install fastmcp httpx pydantic uvicorn toon-mcp-server
    ```
3. Run the server:
    ```bash
    export PRESENTON_BASE_URL=http://presenton-app:80
    export MCP_SERVER_PORT=80
    python -m src.main
    ```

## 🐳 Docker Deployment

Build and run the server using Docker:

```bash
docker build -t presenton-mcp:latest .
docker run -d --name presenton-mcp \
    -e PRESENTON_BASE_URL="http://presenton-app:80" \
    -e MCP_SERVER_PORT=80 \
    -e IS_STATEFUL=false \
    presenton-mcp:latest

The MCP server serves at `http://presenton-mcp:80/mcp` (Streamable HTTP).
```

## ⚠️ Important Notes

- **📋 `include_all_fields`** — The `include_all_fields` parameter (available
  on all `get_*` and `list_*` tools) controls whether all available fields
  are included in responses. Defaults to `False` for performance; set to
  `True` only when additional fields are needed.
- **🔒 `ALLOW_ALL_AGGREGATE`** — Controls whether aggregate listing tools respect
  the `include_all_fields` parameter. When set to `false` (default), all aggregate
  list operations silently return only default fields regardless of the caller's request.
- **⚡ TOON Compression** — All bulk list responses are automatically
  compressed using TOON to reduce token consumption by 30–60%.
- **📝 Required Fields & Defaults** — Each `create_*` tool requires specific
  key fields. All other fields default to empty strings or reasonable values.

## 🛠️ API Tool Mapping

The server implements 44 MCP tools organized into the following categories:

### 📽️ Presentation Management (11 tools)

- `list_all_presentations` — List all presentation records
- `get_presentation_by_id` — Get a single presentation by ID
- `create_presentation` — Create a new presentation from markdown content
- `update_presentation` — Update an existing presentation
- `delete_presentation_by_id` — Delete a presentation by ID
- `duplicate_presentation` — Duplicate an existing presentation
- `generate_presentation_async` — Generate slides asynchronously
- `get_presentation_generation_status` — Check async generation status
- `edit_presentation` — Edit a presentation using an AI prompt
- `derive_presentation` — Derive a new presentation from an existing one
- `prepare_presentation` — Prepare a presentation by assigning layouts

### 📐 Template Management (9 tools)

- `list_all_templates` — List all template records
- `get_template_by_id` — Get a single template by ID
- `create_template_async` — Create a new template asynchronously
- `create_template_init` — Initialize a template from a PPTX file
- `create_template_layouts` — Create slide layouts for a template
- `generate_template_blocks` — Generate merged component blocks
- `update_template_layouts` — Update a slide layout within a template
- `update_template` — Update a template's metadata
- `delete_template_by_id` — Delete a template by ID

### 🎨 Theme Management (6 tools)

- `list_default_themes` — List default theme records
- `list_all_themes` — List all custom theme records
- `create_theme` — Create a new custom theme
- `update_theme` — Update an existing custom theme
- `delete_theme_by_id` — Delete a custom theme by ID
- `generate_theme` — Generate a color palette from a prompt

### 🖼️ Image & Icon Management (5 tools)

- `search_stock_images` — Search stock images from providers
- `generate_image` — Generate an image using AI
- `list_generated_images` — List all AI-generated images
- `list_uploaded_images` — List all uploaded images
- `search_icons` — Search icons from the Phosphor icon library

### 📁 Font & File Management (3 tools)

- `list_all_fonts` — List all font records
- `list_uploaded_fonts` — List uploaded font files
- `decompose_file` — Decompose files into text for content

### 📝 Slide & Outline Management (4 tools)

- `get_outline_by_id` — Get a presentation outline by ID
- `update_outline` — Update a presentation outline
- `edit_slide` — Edit a slide's content using AI
- `edit_slide_html` — Edit a slide's HTML using AI

### 💬 Chat & Async Operations (6 tools)

- `list_chat_conversations` — List chat conversations for a presentation
- `get_chat_history` — Get chat message history
- `delete_chat_conversation` — Delete a chat conversation
- `send_chat_message` — Send a chat message
- `list_async_tasks` — List all async task records
- `get_async_task_status` — Get the status of an async task

# Fix Testing — Presenton MCP Server

## Overview

Goal: ALL 45 tools have at least one TRUE POSITIVE test (no 404-acceptance, no fake data). 
Tools that fundamentally require LLM calls are gated under `RUN_LLM_TESTS=true`.

---

## Pre-Population (run once before test_runner)

Two assets must be created on the backend before the test runner executes:

### 1. Dummy file for `decompose_file`

```bash
docker exec presenton-app touch /tmp/presenton/test_decompose.txt
```

This creates `/tmp/presenton/test_decompose.txt` inside the presenton-app container. The `decompose_file` endpoint validates that file paths stay within `/tmp/presenton/`.

### 2. Custom template with `raw_layouts`

```python
import httpx, time
api_key = 'c2hiYWRtaW5fcHJlc2VudG9uOmNhdXRob2c2Z2FpNHVsOG9vN09oVGhpZWx1aVhhaVJh'
headers = {'Authorization': f'Basic {api_key}'}
base = 'http://localhost:7531'

# Use existing export PPTX + static image from default template
pptx = '/app_data/exports/Recent-Advances-in-Tech-and-AI-Overview_46998a3b-4336-4d9f-8d15-5d97e335436c.pptx'
img = '/app_data/templates/dd31ac17-b50a-4579-8aed-a5c7cad80f9c/static/image6-d77d5bd67ea3.png'

r = httpx.post(f'{base}/api/v1/ppt/templates/async', headers=headers, json={
    'pptx_url': pptx,
    'slide_image_urls': [img],
    'name': 'custom-template-for-test',
    'description': 'Custom template created for test runner'
}, timeout=15)
task_id = r.json()['id']

# Poll until completed
for _ in range(30):
    r = httpx.get(f'{base}/api/v1/async-tasks/status/{task_id}', headers=headers, timeout=10)
    status = r.json().get('status')
    if status == 'completed':
        print('Template ready')
        break
    time.sleep(2)
```

Store the resulting template ID — it will be used by `create_template_layouts`, `generate_template_blocks`, `update_template_layouts`, and `prepare_presentation` (which then enables `get_outline_by_id` + `update_outline`).

Additionally, for `delete_image_by_id`, fetch one existing generated image ID:

```python
r = httpx.get(f'{base}/api/v1/ppt/images/generated', headers=headers, timeout=5)
image_id = r.json()[0]['id']
```

---

## Test Runner Changes

### File: `src/test_runner.py`

#### Remove `run_test_accept_404`

Delete the entire function. Every test must produce a TRUE POSITIVE response from the backend — no 404/error acceptance.

#### Gating

The ONLY conditional in the entire file: `if RUN_LLM_TESTS:` for tools that cannot work without LLM. Gated tools:

| # | Tool | Reason |
|---|------|--------|
| 1 | `generate_presentation_async` | Direct LLM call |
| 2 | `edit_presentation` | Direct LLM call |
| 3 | `derive_presentation` | Direct LLM call |
| 4 | `generate_theme` | Direct LLM call |
| 5 | `generate_image` | Direct LLM call |
| 6 | `edit_slide` | Direct LLM call |
| 7 | `edit_slide_html` | Direct LLM call |
| 8 | `send_chat_message` | Direct LLM call |
| 9 | `get_presentation_generation_status` | Needs task from `generate_presentation_async` |
| 10 | `get_async_task_status` | Needs task from LLM async operation |
| 11 | `get_chat_history` | Needs conversation from `send_chat_message` |
| 12 | `delete_chat_conversation` | Needs conversation from `send_chat_message` |
| 13 | `delete_font_by_filename` | No uploaded fonts, no upload endpoint |

#### Pass-Through Fixes (tools that CAN work with real data)

| Tool | Fix |
|------|-----|
| `search_stock_images` | Already works — remove any accept_404 wrapper |
| `update_template_layouts` | Use pre-populated custom template ID + layout body: `{"id": "test", "description": "test layout " + "x"*20, "components": [{"id": "c1", "description": "test component"}]}` |
| `delete_image_by_id` | Use real image ID from pre-population step |
| `get_outline_by_id` | Use real outline ID returned by `prepare_presentation` (after custom template is created) |
| `update_outline` | Use real outline ID + valid slides array from `prepare_presentation` |
| `prepare_presentation` | Use pre-populated custom template ID to generate a valid layout JSON string. Pass `outlines=[{"title": "S1", "content": ["C1"]}]` and `layout` as a JSON string referencing the custom template's component IDs |
| `decompose_file` | Use `/tmp/presenton/test_decompose.txt` (file created in pre-population) |
| `create_template_async` | Already passes — store the result template ID for downstream template layout operations |
| `create_template_layouts` | Use pre-populated custom template ID + `index: 0` |
| `generate_template_blocks` | Use pre-populated custom template ID |
| `update_template` | Already works with `tmpl_id` from default template list |
| `delete_template_by_id` | Already works with `tmpl_id` from default template list |

#### Always-Run Tests (that pass without LLM, ~32 tests)

```
Phase 1: create_presentation, create_theme (2)
Phase 2: list_all_presentations, list_all_templates, list_all_themes, 
         list_default_themes, list_all_fonts, list_uploaded_fonts,
         list_uploaded_images, list_generated_images, list_async_tasks,
         search_stock_images, search_icons (11)
Phase 3: get_presentation_by_id, update_presentation, duplicate_presentation,
         delete_presentation_by_id(dupe) (4)
Phase 6: list_all_themes_full, update_theme, delete_theme_by_id,
         list_default_themes_full (4)
Phase 7: list_all_templates_full, get_template_by_id, create_template_async,
         create_template_layouts(custom_tmpl_id), generate_template_blocks(custom_tmpl_id),
         update_template_layouts(custom_tmpl_id), update_template(tmpl_id),
         delete_template_by_id(tmpl_id) (8)
Phase 8: list_generated_images_full, list_uploaded_images_full,
         delete_image_by_id(real_image_id) (3)
Phase 9: list_all_fonts_full, list_uploaded_fonts_full,
         decompose_file(/tmp/presenton/test_decompose.txt) (3)
Phase 10: get_outline_by_id(real_outline_id), update_outline(real_outline_id) (2)
Phase 11: list_chat_conversations(preso_id), prepare_presentation(preso_id) (2)
Phase 12: delete_original_presentation, verify_presentation_deleted (2)
Leak: 1
Total: ~41
```

Wait — if we can get `prepare_presentation` working with the custom template, it will return an outline ID. Then we can use that outline ID for `get_outline_by_id` and `update_outline`, AND the layout operations all work with the custom template. That means:

- 13 tools gated (pure LLM or LLM-dependent)
- 32 tools always-run and PASS

---

## Server Tool Change

### File: `src/main.py`

#### `prepare_presentation` tool

Add optional `outlines` and `layout` parameters so the test runner can pass valid data:

```python
@mcp.tool(tags={"write", "primary", "presenton"})
async def prepare_presentation(
    id: str,
    outlines: str = "[]",
    layout: str = "{}",
    ctx: Context = None,
) -> dict[str, Any]:
    try:
        outlines_list = json.loads(outlines)
    except (json.JSONDecodeError, TypeError):
        outlines_list = []
    try:
        layout_obj = json.loads(layout)
    except (json.JSONDecodeError, TypeError):
        layout_obj = {}
    payload = {"presentation_id": id, "outlines": outlines_list, "layout": layout_obj}
    return await get_client().prepare_presentation(payload, get_user_token())
```

This keeps backward compatibility (default empty outlines/layout) while allowing explicit data.

#### `update_outline` tool

Already fixed — sends `{"slides": [...]}` instead of `{"outline": "..."}`.

---

## Execution Order

1. Run pre-population script (creates dummy file, custom template, captures image ID + template ID + outline ID)
2. Run `src/test_runner.py`
3. All ~32 always-run tests PASS
4. When `RUN_LLM_TESTS=true`, all 45 tests PASS

---

## Files to Edit

- `src/test_runner.py` — Remove `run_test_accept_404`, update test data, gate 13 LLM-dependent tools
- `src/main.py` — Add `outlines` + `layout` params to `prepare_presentation`
- `QuickReference.md` — Already updated (presenton-app, no API_KEY in docker run, added RUN_LLM_TESTS to env table)

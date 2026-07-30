import datetime as dt
import os
import re
from typing import Any, Optional

import httpx


COMMON_FIELDS: dict[str, set[str]] = {
    "presentation": {"id", "version", "title", "n_slides", "language", "updated_at"},
    "template": {"id", "name", "description", "layout_count", "is_default", "thumbnail"},
    "theme": {"id", "name", "description", "user"},
    "font": {"id", "name", "family", "size", "postscript_name"},
    "image": {"id", "file_url", "created_at"},
    "chat_conversation": {"id", "presentation_id", "created_at"},
    "async_task": {"id", "type", "status", "message", "created_at"},
}


def _filter_fields(data: Any, common_set: set[str]) -> Any:
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if k in common_set}
    if isinstance(data, list):
        return [_filter_fields(item, common_set) for item in data]
    return data


def _normalize_datetime(value: str) -> str:
    if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$', value):
        parsed = dt.datetime.fromisoformat(value)
        parsed = parsed.astimezone(dt.timezone.utc)
        return parsed.strftime('%Y-%m-%d %H:%M:%S')
    if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', value):
        raise ValueError(
            f"Invalid datetime: {value}. Timezone offset is required. "
            "Must use format: 2026-06-22T15:00:00-04:00"
        )
    return value


def _denormalize_datetime(value: str) -> str:
    if re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$', value):
        parsed = dt.datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.strftime('%Y-%m-%dT%H:%M:%S+00:00')
    if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z$', value):
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.strftime('%Y-%m-%dT%H:%M:%S+00:00')
    return value


def _denormalize_response(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: _denormalize_response(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_denormalize_response(item) for item in data]
    if isinstance(data, str):
        return _denormalize_datetime(data)
    return data


class PresentonClient:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or os.getenv("PRESENTON_BASE_URL", "")).rstrip("/")
        if not self.base_url:
            raise ValueError(
                "Presenton URL required. Set PRESENTON_BASE_URL env var "
                "or pass base_url."
            )

    def _get_headers(self, api_key: Optional[str] = None) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    async def request(
        self,
        method: str,
        path: str,
        api_key: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        url = f"{self.base_url}{path}"
        headers = self._get_headers(api_key)
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.request(method, url, headers=headers, **kwargs)
            if response.status_code >= 400:
                body = response.text[:500]
                raise httpx.HTTPStatusError(
                    f"{response.status_code} {response.reason_phrase} for {method} {path}: {body}",
                    request=response.request, response=response,
                )
            if response.status_code == 204:
                return {}
            if response.headers.get("content-type", "").startswith("application/json"):
                return response.json()
            return {"text": response.text}

    async def get(self, path: str, api_key: Optional[str] = None, **kwargs: Any) -> Any:
        return await self.request("GET", path, api_key, **kwargs)

    async def post(self, path: str, api_key: Optional[str] = None, **kwargs: Any) -> Any:
        return await self.request("POST", path, api_key, **kwargs)

    async def put(self, path: str, api_key: Optional[str] = None, **kwargs: Any) -> Any:
        return await self.request("PUT", path, api_key, **kwargs)

    async def patch(self, path: str, api_key: Optional[str] = None, **kwargs: Any) -> Any:
        return await self.request("PATCH", path, api_key, **kwargs)

    async def delete(self, path: str, api_key: Optional[str] = None, **kwargs: Any) -> Any:
        return await self.request("DELETE", path, api_key, **kwargs)

    # =========================================================================
    # Presentations
    # =========================================================================

    async def get_all_presentations(self, api_key: Optional[str] = None, include_all_fields: bool = False) -> Any:
        data = await self.get("/api/v1/ppt/presentation/all", api_key)
        if not include_all_fields and isinstance(data, list):
            data = _filter_fields(data, COMMON_FIELDS["presentation"])
        return _denormalize_response(data)

    async def get_presentation_by_id(self, presentation_id: str, api_key: Optional[str] = None, include_all_fields: bool = False) -> Any:
        data = await self.get(f"/api/v1/ppt/presentation/{presentation_id}", api_key)
        if data is None:
            raise Exception("Resource not found")
        if not include_all_fields:
            data = _filter_fields(data, COMMON_FIELDS["presentation"])
        return _denormalize_response(data)

    async def create_presentation(self, payload: dict[str, Any], api_key: Optional[str] = None) -> Any:
        return _denormalize_response(await self.post("/api/v1/ppt/presentation/create", api_key, json=payload))

    async def update_presentation(self, payload: dict[str, Any], api_key: Optional[str] = None) -> Any:
        return _denormalize_response(await self.patch("/api/v1/ppt/presentation/update", api_key, json=payload))

    async def delete_presentation_by_id(self, presentation_id: str, api_key: Optional[str] = None) -> Any:
        return await self.delete(f"/api/v1/ppt/presentation/{presentation_id}", api_key)

    async def duplicate_presentation(self, presentation_id: str, api_key: Optional[str] = None) -> Any:
        return _denormalize_response(await self.post(f"/api/v1/ppt/presentation/{presentation_id}/duplicate", api_key))

    async def generate_presentation_async(self, payload: dict[str, Any], api_key: Optional[str] = None) -> Any:
        return _denormalize_response(await self.post("/api/v1/ppt/presentation/generate/async", api_key, json=payload))

    async def get_presentation_generation_status(self, task_id: str, api_key: Optional[str] = None) -> Any:
        return _denormalize_response(await self.get(f"/api/v1/ppt/presentation/status/{task_id}", api_key))

    async def edit_presentation(self, payload: dict[str, Any], api_key: Optional[str] = None) -> Any:
        return _denormalize_response(await self.post("/api/v1/ppt/presentation/edit", api_key, json=payload))

    async def derive_presentation(self, payload: dict[str, Any], api_key: Optional[str] = None) -> Any:
        return _denormalize_response(await self.post("/api/v1/ppt/presentation/derive", api_key, json=payload))

    async def prepare_presentation(self, payload: dict[str, Any], api_key: Optional[str] = None) -> Any:
        return _denormalize_response(await self.post("/api/v1/ppt/presentation/prepare", api_key, json=payload))

    # =========================================================================
    # Templates
    # =========================================================================

    async def get_all_templates(self, api_key: Optional[str] = None, include_all_fields: bool = False, page: int = 1, page_size: int = 20) -> Any:
        data = await self.get(f"/api/v1/ppt/template/all?page={page}&page_size={page_size}", api_key)
        if isinstance(data, dict):
            items = data.get("items", data)
            if not include_all_fields:
                items = _filter_fields(items, COMMON_FIELDS["template"])
            data = {"items": items, **{k: v for k, v in data.items() if k != "items"}}
        return _denormalize_response(data)

    async def get_template_by_id(self, template_id: str, api_key: Optional[str] = None, include_all_fields: bool = False) -> Any:
        data = await self.get(f"/api/v1/ppt/template/{template_id}", api_key)
        if data is None:
            raise Exception("Resource not found")
        if not include_all_fields:
            data = _filter_fields(data, COMMON_FIELDS["template"])
        return _denormalize_response(data)

    async def create_template_async(self, payload: dict[str, Any], api_key: Optional[str] = None) -> Any:
        return _denormalize_response(await self.post("/api/v1/ppt/template/async", api_key, json=payload))

    async def create_template_init(self, payload: dict[str, Any], api_key: Optional[str] = None) -> Any:
        return _denormalize_response(await self.post("/api/v1/ppt/template/init", api_key, json=payload))

    async def create_template_layouts(self, payload: dict[str, Any], api_key: Optional[str] = None) -> Any:
        return _denormalize_response(await self.post("/api/v1/ppt/template/layouts/create", api_key, json=payload))

    async def generate_template_blocks(self, payload: dict[str, Any], api_key: Optional[str] = None) -> Any:
        return _denormalize_response(await self.post("/api/v1/ppt/template/generate-blocks", api_key, json=payload))

    async def update_template_layouts(self, template_id: str, payload: dict[str, Any], api_key: Optional[str] = None) -> Any:
        return _denormalize_response(await self.patch(f"/api/v1/ppt/template/{template_id}/layouts", api_key, json=payload))

    async def update_template(self, template_id: str, payload: dict[str, Any], api_key: Optional[str] = None) -> Any:
        return _denormalize_response(await self.patch(f"/api/v1/ppt/template/{template_id}", api_key, json=payload))

    async def delete_template_by_id(self, template_id: str, api_key: Optional[str] = None) -> Any:
        return await self.delete(f"/api/v1/ppt/template/{template_id}", api_key)

    # =========================================================================
    # Themes
    # =========================================================================

    async def get_default_themes(self, api_key: Optional[str] = None, include_all_fields: bool = False) -> Any:
        data = await self.get("/api/v1/ppt/themes/default", api_key)
        if not include_all_fields and isinstance(data, list):
            data = _filter_fields(data, COMMON_FIELDS["theme"])
        return _denormalize_response(data)

    async def get_all_themes(self, api_key: Optional[str] = None, include_all_fields: bool = False) -> Any:
        data = await self.get("/api/v1/ppt/themes/all", api_key)
        if not include_all_fields and isinstance(data, list):
            data = _filter_fields(data, COMMON_FIELDS["theme"])
        return _denormalize_response(data)

    async def create_theme(self, payload: dict[str, Any], api_key: Optional[str] = None) -> Any:
        return _denormalize_response(await self.post("/api/v1/ppt/themes/create", api_key, json=payload))

    async def update_theme(self, theme_id: str, payload: dict[str, Any], api_key: Optional[str] = None) -> Any:
        return _denormalize_response(await self.patch(f"/api/v1/ppt/themes/update/{theme_id}", api_key, json=payload))

    async def delete_theme_by_id(self, theme_id: str, api_key: Optional[str] = None) -> Any:
        return await self.delete(f"/api/v1/ppt/themes/delete/{theme_id}", api_key)

    async def generate_theme(self, payload: dict[str, Any], api_key: Optional[str] = None) -> Any:
        return _denormalize_response(await self.post("/api/v1/ppt/theme/generate", api_key, json=payload))

    # =========================================================================
    # Fonts
    # =========================================================================

    async def get_all_fonts(self, api_key: Optional[str] = None, include_all_fields: bool = False) -> Any:
        data = await self.get("/api/v1/ppt/fonts/list", api_key)
        result = data.get("fonts", data) if isinstance(data, dict) else data
        if not include_all_fields and isinstance(result, list):
            result = _filter_fields(result, COMMON_FIELDS["font"])
        return _denormalize_response(result)

    async def get_uploaded_fonts(self, api_key: Optional[str] = None, include_all_fields: bool = False) -> Any:
        data = await self.get("/api/v1/ppt/fonts/uploaded", api_key)
        result = data.get("fonts", data) if isinstance(data, dict) else data
        if not include_all_fields and isinstance(result, list):
            result = _filter_fields(result, COMMON_FIELDS["font"])
        return _denormalize_response(result)

    # =========================================================================
    # Images
    # =========================================================================

    async def search_stock_images(self, query: str, api_key: Optional[str] = None, limit: int = 12) -> Any:
        return _denormalize_response(await self.get(f"/api/v1/ppt/images/search?query={query}&limit={limit}", api_key))

    async def generate_image(self, prompt: str, api_key: Optional[str] = None) -> Any:
        return _denormalize_response(await self.get(f"/api/v1/ppt/images/generate?prompt={prompt}", api_key))

    async def get_generated_images(self, api_key: Optional[str] = None, include_all_fields: bool = False) -> Any:
        data = await self.get("/api/v1/ppt/images/generated", api_key)
        if not include_all_fields and isinstance(data, list):
            data = _filter_fields(data, COMMON_FIELDS["image"])
        return _denormalize_response(data)

    async def get_uploaded_images(self, api_key: Optional[str] = None, include_all_fields: bool = False) -> Any:
        data = await self.get("/api/v1/ppt/images/uploaded", api_key)
        if not include_all_fields and isinstance(data, list):
            data = _filter_fields(data, COMMON_FIELDS["image"])
        return _denormalize_response(data)

    # =========================================================================
    # Icons
    # =========================================================================

    async def search_icons(self, query: str, api_key: Optional[str] = None, limit: int = 20) -> Any:
        return _denormalize_response(await self.get(f"/api/v1/ppt/icons/search?query={query}&limit={limit}", api_key))

    # =========================================================================
    # Outlines
    # =========================================================================

    async def get_outline_by_id(self, outline_id: str, api_key: Optional[str] = None, include_all_fields: bool = False) -> Any:
        data = await self.get(f"/api/v1/ppt/outlines/{outline_id}", api_key)
        if data is None:
            raise Exception("Resource not found")
        return _denormalize_response(data)

    async def update_outline(self, outline_id: str, payload: dict[str, Any], api_key: Optional[str] = None) -> Any:
        return _denormalize_response(await self.put(f"/api/v1/ppt/outlines/{outline_id}", api_key, json=payload))

    # =========================================================================
    # Slides
    # =========================================================================

    async def edit_slide(self, payload: dict[str, Any], api_key: Optional[str] = None) -> Any:
        return _denormalize_response(await self.post("/api/v1/ppt/slide/edit", api_key, json=payload))

    async def edit_slide_html(self, payload: dict[str, Any], api_key: Optional[str] = None) -> Any:
        return _denormalize_response(await self.post("/api/v1/ppt/slide/edit-html", api_key, json=payload))

    # =========================================================================
    # Files
    # =========================================================================

    async def decompose_file(self, payload: dict[str, Any], api_key: Optional[str] = None) -> Any:
        return _denormalize_response(await self.post("/api/v1/ppt/files/decompose", api_key, json=payload))

    # =========================================================================
    # Chat
    # =========================================================================

    async def list_chat_conversations(self, presentation_id: str, api_key: Optional[str] = None, include_all_fields: bool = False) -> Any:
        data = await self.get(f"/api/v1/ppt/chat/conversations?presentation_id={presentation_id}", api_key)
        if not include_all_fields and isinstance(data, list):
            data = _filter_fields(data, COMMON_FIELDS["chat_conversation"])
        return _denormalize_response(data)

    async def get_chat_history(self, presentation_id: str, conversation_id: str, api_key: Optional[str] = None, include_all_fields: bool = False) -> Any:
        data = await self.get(f"/api/v1/ppt/chat/history?presentation_id={presentation_id}&conversation_id={conversation_id}", api_key)
        return _denormalize_response(data)

    async def delete_chat_conversation(self, presentation_id: str, conversation_id: str, api_key: Optional[str] = None) -> Any:
        return await self.delete(f"/api/v1/ppt/chat/conversation?presentation_id={presentation_id}&conversation_id={conversation_id}", api_key)

    async def send_chat_message(self, payload: dict[str, Any], api_key: Optional[str] = None) -> Any:
        return _denormalize_response(await self.post("/api/v1/ppt/chat/message", api_key, json=payload))

    # =========================================================================
    # Async Tasks
    # =========================================================================

    async def list_async_tasks(self, api_key: Optional[str] = None, include_all_fields: bool = False) -> Any:
        data = await self.get("/api/v1/async-tasks", api_key)
        if not include_all_fields and isinstance(data, list):
            data = _filter_fields(data, COMMON_FIELDS["async_task"])
        return _denormalize_response(data)

    async def get_async_task_status(self, task_id: str, api_key: Optional[str] = None) -> Any:
        data = await self.get(f"/api/v1/async-tasks/status/{task_id}", api_key)
        if data is None:
            raise Exception("Resource not found")
        return _denormalize_response(data)

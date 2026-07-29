import json
import os
import sys
from contextvars import ContextVar
from typing import Any, Optional

from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field
from toon_mcp import json_to_toon

from .client import PresentonClient, _normalize_datetime

_current_user_token: ContextVar[Optional[str]] = ContextVar("current_user_token", default=None)


class AuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            auth_header = headers.get(b"authorization", b"").decode()
            if auth_header.startswith("Bearer "):
                _current_user_token.set(auth_header[7:])
        await self.app(scope, receive, send)


mcp = FastMCP("Presenton-mcp-server")

_client: Optional[PresentonClient] = None


def get_client() -> PresentonClient:
    global _client
    if _client is None:
        _client = PresentonClient()
    return _client


def get_user_token() -> Optional[str]:
    return _current_user_token.get()


ALLOW_ALL_AGGREGATE = os.getenv("ALLOW_ALL_AGGREGATE", "false").lower() in ("true", "1", "yes")
IS_STATEFUL = os.getenv("IS_STATEFUL", "false").lower() in ("true", "1", "yes")


# =============================================================================
# Pydantic Contract Models
# =============================================================================


class CreatePresentationParam(BaseModel):
    content: str
    n_slides: Optional[int] = None
    language: str = ""
    tone: str = "default"
    verbosity: str = "standard"
    instructions: str = ""
    include_table_of_contents: bool = False
    include_title_slide: bool = True
    web_search: bool = False


class UpdatePresentationParam(BaseModel):
    id: str
    content: Optional[str] = None
    n_slides: Optional[int] = None
    language: Optional[str] = None
    tone: Optional[str] = None
    verbosity: Optional[str] = None
    instructions: Optional[str] = None
    include_table_of_contents: Optional[bool] = None
    include_title_slide: Optional[bool] = None
    web_search: Optional[bool] = None


class GeneratePresentationAsyncParam(BaseModel):
    id: str


class EditPresentationParam(BaseModel):
    id: str
    prompt: str


class CreateThemeParam(BaseModel):
    name: str
    description: str = ""
    company_name: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class UpdateThemeParam(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    company_name: Optional[str] = None
    data: Optional[dict[str, Any]] = None


class GenerateThemeParam(BaseModel):
    prompt: str


class UpdateOutlineParam(BaseModel):
    outline: str


class EditSlideParam(BaseModel):
    id: str
    prompt: str


class EditSlideHtmlParam(BaseModel):
    id: str
    prompt: str
    html: str = ""


class DecomposeFileParam(BaseModel):
    file_paths: list[str]
    language: str = ""


class ChatMessageParam(BaseModel):
    presentation_id: str
    message: str
    conversation_id: str = ""


# =============================================================================
# Presentation Management Tools (11 tools)
# =============================================================================


@mcp.tool(tags={"read", "basic", "presenton"})
async def list_all_presentations(
    include_all_fields: bool = False,
    ctx: Context = None,
) -> dict[str, Any]:
    """List all presentation records.

    Args:
        include_all_fields: Default False (common fields only). Set True for all fields.
    """
    data = await get_client().get_all_presentations(
        get_user_token(),
        include_all_fields=include_all_fields if ALLOW_ALL_AGGREGATE else False,
    )
    return {"items": json_to_toon(data)}


@mcp.tool(tags={"read", "basic", "presenton"})
async def get_presentation_by_id(
    id: str,
    include_all_fields: bool = False,
    ctx: Context = None,
) -> dict[str, Any]:
    """Get a single presentation by its ID.

    Args:
        id: The unique ID of the presentation.
        include_all_fields: Default False (common fields only). Set True for all fields.
    """
    return await get_client().get_presentation_by_id(id, get_user_token(), include_all_fields=include_all_fields)


@mcp.tool(tags={"write", "basic", "presenton"})
async def create_presentation(
    content: str,
    n_slides: Optional[int] = None,
    language: str = "",
    tone: str = "default",
    verbosity: str = "standard",
    instructions: str = "",
    include_table_of_contents: bool = False,
    include_title_slide: bool = True,
    web_search: bool = False,
    ctx: Context = None,
) -> dict[str, Any]:
    """Create a new presentation from markdown content.

    Args:
        content: Markdown content of the presentation.
        n_slides: Number of slides to generate. 0 for auto.
        language: Language code for the presentation content.
        tone: Presentation tone. One of: default, professional, casual, enthusiastic, informative, humorous, inspiring, persuasive, formal, friendly, creative, witty, educational, motivational, storytelling.
        verbosity: Content verbosity. One of: standard, concise, detailed, comprehensive, brief.
        instructions: Additional instructions for the AI generator.
        include_table_of_contents: Include a table of contents slide: true or false.
        include_title_slide: Include a title slide: true or false.
        web_search: Enable web search for content enrichment: true or false.
    """
    params = CreatePresentationParam(
        content=content, n_slides=n_slides, language=language,
        tone=tone, verbosity=verbosity, instructions=instructions,
        include_table_of_contents=include_table_of_contents,
        include_title_slide=include_title_slide, web_search=web_search,
    )
    return await get_client().create_presentation(
        params.model_dump(exclude_unset=True), get_user_token()
    )


@mcp.tool(tags={"write", "basic", "presenton"})
async def update_presentation(
    id: str,
    content: Optional[str] = None,
    n_slides: Optional[int] = None,
    language: Optional[str] = None,
    tone: Optional[str] = None,
    verbosity: Optional[str] = None,
    instructions: Optional[str] = None,
    include_table_of_contents: Optional[bool] = None,
    include_title_slide: Optional[bool] = None,
    web_search: Optional[bool] = None,
    ctx: Context = None,
) -> dict[str, Any]:
    """Update an existing presentation.

    Args:
        id: The unique ID of the presentation to update.
        content: Updated markdown content.
        n_slides: Updated number of slides.
        language: Updated language code.
        tone: Updated presentation tone.
        verbosity: Updated content verbosity.
        instructions: Updated AI instructions.
        include_table_of_contents: Include table of contents: true or false.
        include_title_slide: Include title slide: true or false.
        web_search: Enable web search: true or false.
    """
    params = UpdatePresentationParam(
        id=id, content=content, n_slides=n_slides, language=language,
        tone=tone, verbosity=verbosity, instructions=instructions,
        include_table_of_contents=include_table_of_contents,
        include_title_slide=include_title_slide, web_search=web_search,
    )
    p = params.model_dump(exclude_unset=True, exclude_none=True)
    if not any(v is not None for v in p.values()):
        raise ValueError("At least one field to update must be provided")
    return await get_client().update_presentation(p, get_user_token())


@mcp.tool(tags={"write", "basic", "presenton"})
async def delete_presentation_by_id(
    id: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Delete a presentation by its ID.

    Args:
        id: The unique ID of the presentation to delete.
    """
    await get_client().delete_presentation_by_id(id, get_user_token())
    return {"deleted": True, "id": id}


@mcp.tool(tags={"write", "primary", "presenton"})
async def duplicate_presentation(
    id: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Duplicate an existing presentation.

    Args:
        id: The unique ID of the presentation to duplicate.
    """
    return await get_client().duplicate_presentation(id, get_user_token())


@mcp.tool(tags={"write", "primary", "presenton"})
async def generate_presentation_async(
    id: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Generate slides for a presentation asynchronously.

    Args:
        id: The unique ID of the presentation to generate slides for.
    """
    params = GeneratePresentationAsyncParam(id=id)
    return await get_client().generate_presentation_async(
        params.model_dump(exclude_unset=True), get_user_token()
    )


@mcp.tool(tags={"read", "primary", "presenton"})
async def get_presentation_generation_status(
    id: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Check the async generation status of a presentation.

    Args:
        id: The task ID returned from generate_presentation_async.
    """
    return await get_client().get_presentation_generation_status(id, get_user_token())


@mcp.tool(tags={"write", "primary", "presenton"})
async def edit_presentation(
    id: str,
    prompt: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Edit an existing presentation's content using an AI prompt.

    Args:
        id: The unique ID of the presentation to edit.
        prompt: Instructions for the AI on how to edit the presentation.
    """
    params = EditPresentationParam(id=id, prompt=prompt)
    return await get_client().edit_presentation(
        params.model_dump(exclude_unset=True), get_user_token()
    )


@mcp.tool(tags={"write", "advanced", "presenton"})
async def derive_presentation(
    id: str,
    prompt: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Derive a new presentation from an existing one using an AI prompt.

    Args:
        id: The unique ID of the source presentation.
        prompt: Instructions for the AI on how to derive the new presentation.
    """
    params = EditPresentationParam(id=id, prompt=prompt)
    return await get_client().derive_presentation(
        params.model_dump(exclude_unset=True), get_user_token()
    )


@mcp.tool(tags={"write", "primary", "presenton"})
async def prepare_presentation(
    id: str,
    outlines: str,
    layout: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Prepare a presentation by assigning layouts to slides.

    Args:
        id: The unique ID of the presentation to prepare.
        outlines: JSON string of outlines array.
        layout: JSON string of layout object.
    """
    outlines_list = json.loads(outlines)
    layout_obj = json.loads(layout)
    payload = {"presentation_id": id, "outlines": outlines_list, "layout": layout_obj}
    return await get_client().prepare_presentation(payload, get_user_token())


# =============================================================================
# Template Management Tools (8 tools)
# =============================================================================


@mcp.tool(tags={"read", "basic", "presenton"})
async def list_all_templates(
    include_all_fields: bool = False,
    page: int = 1,
    page_size: int = 20,
    ctx: Context = None,
) -> dict[str, Any]:
    """List all template records.

    Args:
        include_all_fields: Default False (common fields only). Set True for all fields.
        page: Page number (1-indexed).
        page_size: Items per page (1-100).
    """
    data = await get_client().get_all_templates(
        get_user_token(),
        include_all_fields=include_all_fields if ALLOW_ALL_AGGREGATE else False,
        page=page,
        page_size=page_size,
    )
    items = data.get("items", data) if isinstance(data, dict) else data
    return {"items": json_to_toon(items)}


@mcp.tool(tags={"read", "basic", "presenton"})
async def get_template_by_id(
    id: str,
    include_all_fields: bool = False,
    ctx: Context = None,
) -> dict[str, Any]:
    """Get a single template by its ID.

    Args:
        id: The unique ID of the template.
        include_all_fields: Default False (common fields only). Set True for all fields.
    """
    return await get_client().get_template_by_id(id, get_user_token(), include_all_fields=include_all_fields)


@mcp.tool(tags={"write", "primary", "presenton"})
async def create_template_async(
    pptx_url: str,
    slide_image_urls: list[str],
    fonts: dict[str, Any] = {},
    name: str = "",
    description: str = "",
    ctx: Context = None,
) -> dict[str, Any]:
    """Create a new template asynchronously from a PPTX file URL.

    Args:
        pptx_url: URL path to the PPTX file in the app data directory.
        slide_image_urls: List of slide preview image URLs, one per slide.
        fonts: Font mapping dictionary. (Default: {})
        name: Template name. (Default: derived from PPTX filename)
        description: Template description. (Default: "")
    """
    payload = {
        "pptx_url": pptx_url,
        "slide_image_urls": slide_image_urls,
        "fonts": fonts,
    }
    if name:
        payload["name"] = name
    if description:
        payload["description"] = description
    return await get_client().create_template_async(payload, get_user_token())


@mcp.tool(tags={"write", "primary", "presenton"})
async def create_template_init(
    pptx_url: str,
    slide_image_urls: list[str],
    name: str = "",
    description: str = "",
    ctx: Context = None,
) -> dict[str, Any]:
    """Create a template synchronously from a PPTX file path (no async worker needed).

    Args:
        pptx_url: Path to the PPTX file on the backend server.
        slide_image_urls: List of slide preview image URLs, one per slide.
        name: Template name.
        description: Template description.
    """
    payload = {
        "pptx_url": pptx_url,
        "slide_image_urls": slide_image_urls,
    }
    if name:
        payload["name"] = name
    if description:
        payload["description"] = description
    template_id = await get_client().create_template_init(payload, get_user_token())
    return {"id": template_id}


@mcp.tool(tags={"write", "primary", "presenton"})
async def create_template_layouts(
    template_id: str,
    index: Optional[int] = None,
    indices: Optional[list[int]] = None,
    ctx: Context = None,
) -> dict[str, Any]:
    """Create slide layouts for a template.

    Args:
        template_id: The unique ID of the template.
        index: A single slide index to create a layout for.
        indices: Multiple slide indices to create layouts for.
    """
    payload = {"template_id": template_id}
    if index is not None:
        payload["index"] = index
    if indices is not None:
        payload["indices"] = indices
    return await get_client().create_template_layouts(payload, get_user_token())


@mcp.tool(tags={"write", "advanced", "presenton"})
async def generate_template_blocks(
    template_id: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Generate merged component blocks for a template.

    Args:
        template_id: The unique ID of the template.
    """
    payload = {"template_id": template_id}
    return await get_client().generate_template_blocks(payload, get_user_token())


@mcp.tool(tags={"write", "primary", "presenton"})
async def update_template_layouts(
    template_id: str,
    index: int,
    layout: dict[str, Any],
    ctx: Context = None,
) -> dict[str, Any]:
    """Update a single slide layout within a template.

    Args:
        template_id: The unique ID of the template.
        index: Slide index to update.
        layout: The layout object to set for the slide.
    """
    payload = {"index": index, "layout": layout}
    return await get_client().update_template_layouts(template_id, payload, get_user_token())


@mcp.tool(tags={"write", "basic", "presenton"})
async def update_template(
    id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    ctx: Context = None,
) -> dict[str, Any]:
    """Update a template's metadata.

    Args:
        id: The unique ID of the template to update.
        name: New template name.
        description: New template description.
    """
    payload = {}
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    return await get_client().update_template(id, payload, get_user_token())


@mcp.tool(tags={"write", "basic", "presenton"})
async def delete_template_by_id(
    id: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Delete a template by its ID.

    Args:
        id: The unique ID of the template to delete.
    """
    await get_client().delete_template_by_id(id, get_user_token())
    return {"deleted": True, "id": id}


# =============================================================================
# Theme Management Tools (6 tools)
# =============================================================================


@mcp.tool(tags={"read", "basic", "presenton"})
async def list_default_themes(
    include_all_fields: bool = False,
    ctx: Context = None,
) -> dict[str, Any]:
    """List default theme records.

    Args:
        include_all_fields: Default False (common fields only). Set True for all fields.
    """
    data = await get_client().get_default_themes(
        get_user_token(),
        include_all_fields=include_all_fields if ALLOW_ALL_AGGREGATE else False,
    )
    return {"items": json_to_toon(data)}


@mcp.tool(tags={"read", "basic", "presenton"})
async def list_all_themes(
    include_all_fields: bool = False,
    ctx: Context = None,
) -> dict[str, Any]:
    """List all custom theme records.

    Args:
        include_all_fields: Default False (common fields only). Set True for all fields.
    """
    data = await get_client().get_all_themes(
        get_user_token(),
        include_all_fields=include_all_fields if ALLOW_ALL_AGGREGATE else False,
    )
    return {"items": json_to_toon(data)}


@mcp.tool(tags={"write", "basic", "presenton"})
async def create_theme(
    name: str,
    description: str = "",
    company_name: str = "",
    data: dict[str, Any] = {},
    ctx: Context = None,
) -> dict[str, Any]:
    """Create a new custom theme.

    Args:
        name: Name of the new theme.
        description: Description of the theme.
        company_name: Company name associated with the theme.
        data: Theme data/configuration object.
    """
    params = CreateThemeParam(
        name=name, description=description,
        company_name=company_name, data=data,
    )
    return await get_client().create_theme(
        params.model_dump(exclude_unset=True), get_user_token()
    )


@mcp.tool(tags={"write", "primary", "presenton"})
async def update_theme(
    id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    company_name: Optional[str] = None,
    data: Optional[dict[str, Any]] = None,
    ctx: Context = None,
) -> dict[str, Any]:
    """Update an existing custom theme.

    Args:
        id: The unique ID of the theme to update.
        name: New theme name.
        description: New theme description.
        company_name: New company name.
        data: New theme data/configuration object.
    """
    params = UpdateThemeParam(
        name=name, description=description,
        company_name=company_name, data=data,
    )
    p = params.model_dump(exclude_unset=True, exclude_none=True)
    return await get_client().update_theme(id, p, get_user_token())


@mcp.tool(tags={"write", "basic", "presenton"})
async def delete_theme_by_id(
    id: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Delete a custom theme by its ID.

    Args:
        id: The unique ID of the theme to delete.
    """
    await get_client().delete_theme_by_id(id, get_user_token())
    return {"deleted": True, "id": id}


@mcp.tool(tags={"write", "primary", "presenton"})
async def generate_theme(
    prompt: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Generate a color palette and theme data from a prompt.

    Args:
        prompt: A description of the desired theme colors and style.
    """
    params = GenerateThemeParam(prompt=prompt)
    return await get_client().generate_theme(
        params.model_dump(exclude_unset=True), get_user_token()
    )


# =============================================================================
# Image & Icon Management Tools (6 tools)
# =============================================================================


@mcp.tool(tags={"read", "basic", "presenton"})
async def search_stock_images(
    query: str,
    limit: int = 12,
    ctx: Context = None,
) -> dict[str, Any]:
    """Search stock images from integrated providers.

    Args:
        query: Search query string.
        limit: Maximum number of results (1-30).
    """
    data = await get_client().search_stock_images(query, get_user_token(), limit=limit)
    if isinstance(data, dict):
        results = data.get("results", data.get("photos", data.get("videos", [])))
        return {"items": json_to_toon(results)}
    return {"items": json_to_toon(data) if isinstance(data, list) else data}


@mcp.tool(tags={"write", "primary", "presenton"})
async def generate_image(
    prompt: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Generate an image using AI based on a text prompt.

    Args:
        prompt: Description of the image to generate.
    """
    return await get_client().generate_image(prompt, get_user_token())


@mcp.tool(tags={"read", "primary", "presenton"})
async def list_generated_images(
    include_all_fields: bool = False,
    ctx: Context = None,
) -> dict[str, Any]:
    """List all AI-generated images.

    Args:
        include_all_fields: Default False (common fields only). Set True for all fields.
    """
    data = await get_client().get_generated_images(
        get_user_token(),
        include_all_fields=include_all_fields if ALLOW_ALL_AGGREGATE else False,
    )
    return {"items": json_to_toon(data)}


@mcp.tool(tags={"read", "basic", "presenton"})
async def list_uploaded_images(
    include_all_fields: bool = False,
    ctx: Context = None,
) -> dict[str, Any]:
    """List all uploaded images.

    Args:
        include_all_fields: Default False (common fields only). Set True for all fields.
    """
    data = await get_client().get_uploaded_images(
        get_user_token(),
        include_all_fields=include_all_fields if ALLOW_ALL_AGGREGATE else False,
    )
    return {"items": json_to_toon(data)}


@mcp.tool(tags={"read", "primary", "presenton"})
async def search_icons(
    query: str,
    limit: int = 20,
    ctx: Context = None,
) -> dict[str, Any]:
    """Search icons from the Phosphor icon library.

    Args:
        query: Search query string.
        limit: Maximum number of results.
    """
    data = await get_client().search_icons(query, get_user_token(), limit=limit)
    return {"items": json_to_toon(data) if isinstance(data, list) else data}


# =============================================================================
# Font & File Management Tools (4 tools)
# =============================================================================


@mcp.tool(tags={"read", "basic", "presenton"})
async def list_all_fonts(
    include_all_fields: bool = False,
    ctx: Context = None,
) -> dict[str, Any]:
    """List all font records.

    Args:
        include_all_fields: Default False (common fields only). Set True for all fields.
    """
    data = await get_client().get_all_fonts(
        get_user_token(),
        include_all_fields=include_all_fields if ALLOW_ALL_AGGREGATE else False,
    )
    return {"items": json_to_toon(data)}


@mcp.tool(tags={"read", "basic", "presenton"})
async def list_uploaded_fonts(
    include_all_fields: bool = False,
    ctx: Context = None,
) -> dict[str, Any]:
    """List uploaded font files.

    Args:
        include_all_fields: Default False (common fields only). Set True for all fields.
    """
    data = await get_client().get_uploaded_fonts(
        get_user_token(),
        include_all_fields=include_all_fields if ALLOW_ALL_AGGREGATE else False,
    )
    return {"items": json_to_toon(data)}


@mcp.tool(tags={"write", "basic", "presenton"})
async def delete_font_by_filename(
    filename: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Delete a font file by its filename.

    Args:
        filename: The filename of the font to delete.
    """
    await get_client().delete_font_by_filename(filename, get_user_token())
    return {"deleted": True, "filename": filename}


@mcp.tool(tags={"write", "primary", "presenton"})
async def decompose_file(
    file_paths: list[str],
    language: str = "",
    ctx: Context = None,
) -> dict[str, Any]:
    """Decompose uploaded files into text for presentation content.

    Args:
        file_paths: List of file paths (strings) to decompose.
        language: Language code for document processing.
    """
    params = DecomposeFileParam(file_paths=file_paths, language=language)
    data = await get_client().decompose_file(
        params.model_dump(exclude_unset=True), get_user_token()
    )
    return {"items": data} if isinstance(data, list) else data


# =============================================================================
# Slide & Outline Management Tools (4 tools)
# =============================================================================


@mcp.tool(tags={"read", "primary", "presenton"})
async def get_outline_by_id(
    id: str,
    include_all_fields: bool = False,
    ctx: Context = None,
) -> dict[str, Any]:
    """Get a presentation outline by its ID.

    Args:
        id: The unique ID of the outline.
        include_all_fields: Default False (common fields only). Set True for all fields.
    """
    return await get_client().get_outline_by_id(id, get_user_token(), include_all_fields=include_all_fields)


@mcp.tool(tags={"write", "primary", "presenton"})
async def update_outline(
    id: str,
    outline: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Update a presentation outline.

    Args:
        id: The unique ID of the outline to update.
        outline: The updated outline content as a JSON string (will be parsed as slides array).
    """
    try:
        slides_list = json.loads(outline)
        if not isinstance(slides_list, list):
            slides_list = []
    except (json.JSONDecodeError, TypeError):
        slides_list = []
    payload = {"slides": slides_list}
    return await get_client().update_outline(id, payload, get_user_token())


@mcp.tool(tags={"write", "primary", "presenton"})
async def edit_slide(
    id: str,
    prompt: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Edit a slide's content using an AI prompt.

    Args:
        id: The unique ID of the slide to edit.
        prompt: Instructions for the AI on how to edit the slide.
    """
    params = EditSlideParam(id=id, prompt=prompt)
    return await get_client().edit_slide(
        params.model_dump(exclude_unset=True), get_user_token()
    )


@mcp.tool(tags={"write", "advanced", "presenton"})
async def edit_slide_html(
    id: str,
    prompt: str,
    html: str = "",
    ctx: Context = None,
) -> dict[str, Any]:
    """Edit a slide's HTML representation using an AI prompt.

    Args:
        id: The unique ID of the slide to edit.
        prompt: Instructions for the AI on how to edit the slide HTML.
        html: The current HTML content of the slide to edit.
    """
    params = EditSlideHtmlParam(id=id, prompt=prompt, html=html)
    return await get_client().edit_slide_html(
        params.model_dump(exclude_unset=True), get_user_token()
    )


# =============================================================================
# Chat & Async Operations Tools (6 tools)
# =============================================================================


@mcp.tool(tags={"read", "primary", "presenton"})
async def list_chat_conversations(
    presentation_id: str,
    include_all_fields: bool = False,
    ctx: Context = None,
) -> dict[str, Any]:
    """List chat conversations for a presentation.

    Args:
        presentation_id: The unique ID of the presentation.
        include_all_fields: Default False (common fields only). Set True for all fields.
    """
    data = await get_client().list_chat_conversations(
        presentation_id, get_user_token(),
        include_all_fields=include_all_fields if ALLOW_ALL_AGGREGATE else False,
    )
    return {"items": json_to_toon(data)}


@mcp.tool(tags={"read", "primary", "presenton"})
async def get_chat_history(
    presentation_id: str,
    conversation_id: str,
    include_all_fields: bool = False,
    ctx: Context = None,
) -> dict[str, Any]:
    """Get chat message history for a conversation.

    Args:
        presentation_id: The unique ID of the presentation.
        conversation_id: The unique ID of the chat conversation.
        include_all_fields: Default False (common fields only). Set True for all fields.
    """
    return await get_client().get_chat_history(
        presentation_id, conversation_id, get_user_token(),
        include_all_fields=include_all_fields,
    )


@mcp.tool(tags={"write", "primary", "presenton"})
async def delete_chat_conversation(
    presentation_id: str,
    conversation_id: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Delete a chat conversation.

    Args:
        presentation_id: The unique ID of the presentation.
        conversation_id: The unique ID of the chat conversation to delete.
    """
    await get_client().delete_chat_conversation(
        presentation_id, conversation_id, get_user_token()
    )
    return {"deleted": True, "conversation_id": conversation_id}


@mcp.tool(tags={"write", "primary", "presenton"})
async def send_chat_message(
    presentation_id: str,
    message: str,
    conversation_id: str = "",
    ctx: Context = None,
) -> dict[str, Any]:
    """Send a chat message for a presentation.

    Args:
        presentation_id: The unique ID of the presentation.
        message: The message content to send.
        conversation_id: The conversation ID to continue. Empty starts a new conversation.
    """
    params = ChatMessageParam(
        presentation_id=presentation_id,
        message=message,
        conversation_id=conversation_id,
    )
    return await get_client().send_chat_message(
        params.model_dump(exclude_unset=True), get_user_token()
    )


@mcp.tool(tags={"read", "basic", "presenton"})
async def list_async_tasks(
    include_all_fields: bool = False,
    ctx: Context = None,
) -> dict[str, Any]:
    """List all async task records.

    Args:
        include_all_fields: Default False (common fields only). Set True for all fields.
    """
    data = await get_client().list_async_tasks(
        get_user_token(),
        include_all_fields=include_all_fields if ALLOW_ALL_AGGREGATE else False,
    )
    return {"items": json_to_toon(data)}


@mcp.tool(tags={"read", "primary", "presenton"})
async def get_async_task_status(
    id: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Get the status of an async task by its ID.

    Args:
        id: The unique ID of the async task.
    """
    return await get_client().get_async_task_status(id, get_user_token())


# =============================================================================
# Entry Point
# =============================================================================


def main():
    if not os.getenv("PRESENTON_BASE_URL"):
        print("ERROR: PRESENTON_BASE_URL environment variable is required", file=sys.stderr)
        print("Example: export PRESENTON_BASE_URL=http://presenton-api:80", file=sys.stderr)
        sys.exit(1)

    port_env = os.getenv("MCP_SERVER_PORT")
    if not port_env:
        print("ERROR: MCP_SERVER_PORT environment variable is required", file=sys.stderr)
        print("Example: export MCP_SERVER_PORT=5641", file=sys.stderr)
        sys.exit(1)

    host = "0.0.0.0"
    port = int(port_env)
    path = "/mcp"
    if IS_STATEFUL:
        app = mcp.http_app(path=path)
    else:
        app = mcp.http_app(path=path, stateless_http=True)
    app = AuthMiddleware(app)
    print(f"Starting Presenton MCP server on http://{host}:{port}{path}", file=sys.stderr)
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()

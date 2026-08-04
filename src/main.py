import os
import sys
from contextvars import ContextVar
from typing import Any, Optional, Union

from fastmcp import FastMCP, Context
from mcp.types import ToolAnnotations
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


class SlideOutlineItem(BaseModel):
    content: str = Field(description="Markdown content (e.g. '# Introduction\\n\\nOverview of the topic')")


class SlideContent(BaseModel):
    model_config = {"extra": "allow"}


class SlideContentUpdateItem(BaseModel):
    index: int = Field(description="Slide index, 0-based (e.g. 0)")
    content: SlideContent = Field(description="Updated slide content by component ID (e.g. {'hero': {'title': 'New Title'}})")


class FontEntry(BaseModel):
    name: str = Field(description="Font family name (e.g. 'Inter')")
    url: str = Field(description="Font file URL (e.g. 'https://fonts.example.com/inter.woff2')")


class ThemeColorConfig(BaseModel):
    primary: Optional[str] = Field(default=None, description="Primary color hex (e.g. #2563EB)")
    background: Optional[str] = Field(default=None, description="Background color hex")
    card: Optional[str] = Field(default=None, description="Card color hex")
    stroke: Optional[str] = Field(default=None, description="Stroke color hex")
    primary_text: Optional[str] = Field(default=None, description="Primary text color hex")
    background_text: Optional[str] = Field(default=None, description="Background text color hex")
    graph_0: Optional[str] = Field(default=None, description="Graph series 0 color hex")
    graph_1: Optional[str] = Field(default=None, description="Graph series 1 color hex")
    graph_2: Optional[str] = Field(default=None, description="Graph series 2 color hex")
    graph_3: Optional[str] = Field(default=None, description="Graph series 3 color hex")
    graph_4: Optional[str] = Field(default=None, description="Graph series 4 color hex")
    graph_5: Optional[str] = Field(default=None, description="Graph series 5 color hex")
    graph_6: Optional[str] = Field(default=None, description="Graph series 6 color hex")
    graph_7: Optional[str] = Field(default=None, description="Graph series 7 color hex")
    graph_8: Optional[str] = Field(default=None, description="Graph series 8 color hex")
    graph_9: Optional[str] = Field(default=None, description="Graph series 9 color hex")


class ThemeFontRef(BaseModel):
    name: Optional[str] = Field(default=None, description="Font name (e.g. 'Inter')")
    url: Optional[str] = Field(default=None, description="Font URL (e.g. 'https://fonts.example.com/inter.woff2')")


class ThemeFontConfig(BaseModel):
    textFont: Optional[ThemeFontRef] = Field(default=None, description="Font configuration")


class ThemeData(BaseModel):
    name: Optional[str] = Field(default=None, description="Theme name (e.g. 'Corporate Blue')")
    description: Optional[str] = Field(default=None, description="Theme description (e.g. 'Professional blue theme')")
    colors: Optional[ThemeColorConfig] = Field(default=None, description="Color configuration")
    fonts: Optional[ThemeFontConfig] = Field(default=None, description="Font configuration")
    textFont: Optional[ThemeFontRef] = Field(default=None, description="Text font override")


class ChatAttachmentItem(BaseModel):
    type: str = Field(default="document", description="Attachment type (e.g. 'document') (Default: document)")
    name: str = Field(description="File name (e.g. 'report.pptx')")
    file_path: str = Field(description="Server path (e.g. '/tmp/uploads/report.pptx')")
    mime_type: Optional[str] = Field(default=None, description="MIME type (e.g. 'application/pdf')")


class Position(BaseModel):
    x: float = Field(description="X coordinate (e.g. 0.0)")
    y: float = Field(description="Y coordinate (e.g. 0.0)")


class Size(BaseModel):
    width: float = Field(description="Width (e.g. 100.0)")
    height: float = Field(description="Height (e.g. 100.0)")


class TextRun(BaseModel):
    text: str = Field(description="Run text content (e.g. 'Hello World')")
    bold: Optional[bool] = Field(default=None, description="Bold style: true or false")
    italic: Optional[bool] = Field(default=None, description="Italic style: true or false")


class BaseElement(BaseModel):
    position: Optional[Position] = Field(default=None, description="Position")
    size: Optional[Size] = Field(default=None, description="Size")


class TextElement(BaseElement):
    type: str = Field(default="text", description="Element type (e.g. 'text') (Default: text)")
    runs: list[TextRun] = Field(description="Text runs (e.g. [{'text': 'Hello'}])")
    decorative: bool = Field(default=False, description="Decorative element: true or false")
    name: Optional[str] = Field(default=None, description="Element name (e.g. 'r1')")
    max_length: Optional[int] = Field(default=None, description="Max text length (e.g. 100)")
    min_length: Optional[int] = Field(default=None, description="Min text length (e.g. 1)")


class ImageElement(BaseElement):
    type: str = Field(default="image", description="Element type (e.g. 'image') (Default: image)")
    data: str = Field(default="", description="Image data URL (e.g. '/static/images/photo.png')")
    decorative: bool = Field(default=False, description="Decorative element: true or false")
    name: Optional[str] = Field(default=None, description="Element name (e.g. 'img1')")
    is_icon: bool = Field(default=False, description="Icon element: true or false")


class TextListElement(BaseElement):
    type: str = Field(default="text-list", description="Element type (e.g. 'text-list') (Default: text-list)")
    items: list[list[TextRun]] = Field(description="List items (e.g. [[{'text': 'Item 1'}], [{'text': 'Item 2'}]])")
    decorative: bool = Field(default=False, description="Decorative element: true or false")
    name: Optional[str] = Field(default=None, description="Element name (e.g. 'bullets')")
    max_items: Optional[int] = Field(default=None, description="Max items (e.g. 10)")
    min_items: Optional[int] = Field(default=None, description="Min items (e.g. 1)")


SlideElement = Union[TextElement, ImageElement, TextListElement]


class LayoutComponent(BaseModel):
    id: str = Field(description="Component ID (e.g. 'c1')")
    description: str = Field(description="Component description (e.g. 'test component...')")
    position: Position = Field(description="Position")
    size: Optional[Size] = Field(default=None, description="Size")
    elements: list[SlideElement] = Field(description="Component elements (e.g. [{'type': 'text', 'runs': [{'text': 'hello'}]}])")


class LayoutObject(BaseModel):
    id: str = Field(description="Layout ID (e.g. 'test-layout')")
    description: str = Field(description="Layout description (min 10 chars, e.g. 'test layout description...')")
    components: list[LayoutComponent] = Field(description="Components")


class UpdatePresentationParam(BaseModel):
    id: str = Field(description="Presentation ID (e.g. 'a1b2c3d4-...')")
    content: Optional[str] = Field(default=None, description="Updated markdown content (e.g. '# Updated Content')")
    n_slides: Optional[int] = Field(default=None, description="Updated number of slides (e.g. 10)")
    language: Optional[str] = Field(default=None, description="Updated language code (e.g. 'en')")
    tone: Optional[str] = Field(default=None, description="Updated tone. One of: default, professional, casual, enthusiastic, informative, humorous, inspiring, persuasive, formal, friendly, creative, witty, educational, motivational, or storytelling")
    verbosity: Optional[str] = Field(default=None, description="Updated verbosity. One of: standard, concise, detailed, comprehensive, or brief")
    instructions: Optional[str] = Field(default=None, description="Updated AI instructions (e.g. 'Add charts')")
    include_table_of_contents: Optional[bool] = Field(default=None, description="Updated table of contents: true or false")
    include_title_slide: Optional[bool] = Field(default=None, description="Updated title slide: true or false")
    web_search: Optional[bool] = Field(default=None, description="Updated web search: true or false")


class GeneratePresentationAsyncParam(BaseModel):
    content: str = Field(description="Content to generate the presentation from (e.g. '# AI Trends\\n\\nOverview...')")
    n_slides: Optional[int] = Field(default=None, description="Number of slides to generate (e.g. 10)")
    instructions: Optional[str] = Field(default=None, description="Additional instructions for the AI (e.g. 'Focus on benefits')")
    tone: str = Field(default="default", description="Presentation tone. One of: default, casual, professional, funny, educational, or sales_pitch (Default: default)")
    verbosity: str = Field(default="standard", description="Content verbosity. One of: concise, standard, or text-heavy (Default: standard)")
    language: Optional[str] = Field(default=None, description="Language code (e.g. 'en')")
    template: str = Field(default="general", description="Template name (e.g. 'general') (Default: general)")
    include_table_of_contents: bool = Field(default=False, description="Include table of contents: true or false")
    include_title_slide: bool = Field(default=True, description="Include title slide: true or false")
    web_search: bool = Field(default=False, description="Enable web search for content enrichment: true or false")


class BootstrapPresentationParam(BaseModel):
    content: str = Field(description="Markdown content (e.g. '# My Talk\\n\\nIntroduction...')")
    n_slides: Optional[int] = Field(default=None, description="Number of slides (e.g. 10)")
    language: str = Field(default="", description="Language code (e.g. 'en')")


class EditPresentationParam(BaseModel):
    presentation_id: str = Field(description="Presentation ID (e.g. 'a1b2c3d4-...')")
    slides: list[SlideContentUpdateItem] = Field(description="Slide content updates")
    export_as: str = Field(default="pptx", description="Export format (e.g. 'pptx' or 'pdf') (Default: pptx)")


class CreateThemeParam(BaseModel):
    name: str = Field(description="Theme name (e.g. 'Corporate Blue')")
    description: str = Field(default="", description="Theme description (e.g. 'Professional blue theme')")
    company_name: str = Field(default="", description="Company name (e.g. 'Acme Corp')")
    data: ThemeData = Field(default_factory=ThemeData, description="Theme configuration")


class UpdateThemeParam(BaseModel):
    name: Optional[str] = Field(default=None, description="Updated theme name (e.g. 'Corporate Blue')")
    description: Optional[str] = Field(default=None, description="Updated description (e.g. 'Updated blue theme')")
    company_name: Optional[str] = Field(default=None, description="Updated company name (e.g. 'Acme Corp')")
    data: Optional[ThemeData] = Field(default=None, description="Updated theme configuration")


class GenerateThemeParam(BaseModel):
    primary: Optional[str] = Field(default=None, description="Primary color hex (e.g. #2563EB)")
    background: Optional[str] = Field(default=None, description="Background color hex")
    accent_1: Optional[str] = Field(default=None, description="First accent color hex")
    accent_2: Optional[str] = Field(default=None, description="Second accent color hex")
    text_1: Optional[str] = Field(default=None, description="Primary text color hex")
    text_2: Optional[str] = Field(default=None, description="Secondary text color hex")


class EditSlideParam(BaseModel):
    id: str = Field(description="Slide ID (e.g. 'a1b2c3d4-...')")
    prompt: str = Field(description="AI editing instructions (e.g. 'Make this slide more concise')")


class EditSlideHtmlParam(BaseModel):
    id: str = Field(description="Slide ID (e.g. 'a1b2c3d4-...')")
    prompt: str = Field(description="AI editing instructions for HTML (e.g. 'Improve the layout')")
    html: str = Field(default="", description="Current HTML content (e.g. '<p>hello</p>')")


class DecomposeFileParam(BaseModel):
    file_paths: list[str] = Field(description="File paths (e.g. ['/tmp/report.pptx'])")
    language: str = Field(default="", description="Language code (e.g. 'en')")


class ChatMessageParam(BaseModel):
    presentation_id: str = Field(description="Presentation ID (e.g. 'a1b2c3d4-...')")
    message: str = Field(description="Message content (e.g. 'What is this about?')")
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID to continue (null starts new)")
    attachments: Optional[list[ChatAttachmentItem]] = Field(default=None, description="File attachments")


# =============================================================================
# Presentation Management Tools (10 tools)
# =============================================================================


@mcp.tool(
    tags={"basic", "presenton"}, annotations=ToolAnnotations(title="List All Presentations", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
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


@mcp.tool(
    tags={"basic", "presenton"}, annotations=ToolAnnotations(title="Get Presentation By Id", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def get_presentation_by_id(
    id: str,
    include_all_fields: bool = False,
    ctx: Context = None,
) -> dict[str, Any]:
    """Get a single presentation by its ID.

    Args:
        id: The unique ID of the presentation (e.g. 'a1b2c3d4-...').
        include_all_fields: Default False (common fields only). Set True for all fields.
    """
    return await get_client().get_presentation_by_id(id, get_user_token(), include_all_fields=include_all_fields)


@mcp.tool(
    tags={"basic", "presenton"}, annotations=ToolAnnotations(title="Create Presentation", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def create_presentation(
    content: str,
    n_slides: Optional[int] = None,
    instructions: Optional[str] = None,
    tone: str = "default",
    verbosity: str = "standard",
    language: Optional[str] = None,
    template: str = "general",
    include_table_of_contents: bool = False,
    include_title_slide: bool = True,
    web_search: bool = False,
    ctx: Context = None,
) -> dict[str, Any]:
    """Create a new presentation with AI-generated slides. This runs asynchronously — returns a task_id and presentation_url immediately. Use get_presentation_generation_status(task_id) to check progress (takes a few minutes), or just access via presentation_url.

    Args:
        content: The content to generate the presentation from (e.g. '# AI Trends\\n\\nOverview...').
        n_slides: Number of slides to generate (e.g. 10).
        instructions: Additional instructions for the AI (e.g. 'Focus on benefits').
        tone: The tone of the presentation. One of: default, casual, professional, funny, educational, or sales_pitch (Default: default).
        verbosity: The verbosity level. One of: concise, standard, or text-heavy (Default: standard).
        language: The language for the presentation (e.g. 'en').
        template: The template to use (Default: general) (e.g. 'general').
        include_table_of_contents: Whether to include a table of contents: true or false.
        include_title_slide: Whether to include a title slide: true or false.
        web_search: Enable web search for content enrichment: true or false.
    """
    params = GeneratePresentationAsyncParam(
        content=content,
        n_slides=n_slides,
        instructions=instructions,
        tone=tone,
        verbosity=verbosity,
        language=language,
        template=template,
        include_table_of_contents=include_table_of_contents,
        include_title_slide=include_title_slide,
        web_search=web_search,
    )
    return await get_client().create_presentation(
        params.model_dump(exclude_unset=True), get_user_token(),
        include_all_fields=ALLOW_ALL_AGGREGATE,
    )


@mcp.tool(
    tags={"basic", "presenton"}, annotations=ToolAnnotations(title="Bootstrap Presentation", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def bootstrap_presentation(
    content: str,
    n_slides: Optional[int] = None,
    language: str = "",
    ctx: Context = None,
) -> dict[str, Any]:
    """Create a simple presentation shell without AI processing. The content is stored directly as markdown.

    Args:
        content: Markdown content of the presentation (e.g. '# My Talk\\n\\nIntroduction...').
        n_slides: Number of slides (e.g. 10).
        language: Language code (e.g. 'en').
    """
    params = BootstrapPresentationParam(content=content, n_slides=n_slides, language=language)
    return await get_client().bootstrap_presentation(
        params.model_dump(exclude_unset=True), get_user_token(),
        include_all_fields=ALLOW_ALL_AGGREGATE,
    )


@mcp.tool(
    tags={"basic", "presenton"}, annotations=ToolAnnotations(title="Update Presentation", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
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
        id: The unique ID of the presentation to update (e.g. 'a1b2c3d4-...').
        content: Updated markdown content (e.g. '# Updated Content').
        n_slides: Updated number of slides (e.g. 10).
        language: Updated language code (e.g. 'en').
        tone: Updated presentation tone. One of: default, professional, casual, enthusiastic, informative, humorous, inspiring, persuasive, formal, friendly, creative, witty, educational, motivational, or storytelling.
        verbosity: Updated content verbosity. One of: standard, concise, detailed, comprehensive, or brief.
        instructions: Updated AI instructions (e.g. 'Add charts').
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
    return await get_client().update_presentation(p, get_user_token(), include_all_fields=ALLOW_ALL_AGGREGATE)


@mcp.tool(
    tags={"basic", "presenton"}, annotations=ToolAnnotations(title="Delete Presentation By Id", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def delete_presentation_by_id(
    id: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Delete a presentation by its ID.

    Args:
        id: The unique ID of the presentation to delete (e.g. 'a1b2c3d4-...').
    """
    await get_client().delete_presentation_by_id(id, get_user_token())
    return {"deleted": True, "id": id}


@mcp.tool(
    tags={"primary", "presenton"}, annotations=ToolAnnotations(title="Duplicate Presentation", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def duplicate_presentation(
    id: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Duplicate an existing presentation.

    Args:
        id: The unique ID of the presentation to duplicate (e.g. 'a1b2c3d4-...').
    """
    return await get_client().duplicate_presentation(id, get_user_token(), include_all_fields=ALLOW_ALL_AGGREGATE)


@mcp.tool(
    tags={"primary", "presenton"}, annotations=ToolAnnotations(title="Edit Presentation", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def edit_presentation(
    presentation_id: str,
    slides: list[SlideContentUpdateItem],
    export_as: str = "pptx",
    ctx: Context = None,
) -> dict[str, Any]:
    """Edit an existing presentation's slides.

    Args:
        presentation_id: Presentation ID (e.g. 'a1b2c3d4-...').
        slides: Slide content updates (e.g. [{'index': 0, 'content': {'hero': {'title': 'New'}}}]).
        export_as: Export format (e.g. 'pptx' or 'pdf').
    """
    params = EditPresentationParam(
        presentation_id=presentation_id,
        slides=slides,
        export_as=export_as,
    )
    return await get_client().edit_presentation(
        params.model_dump(exclude_unset=True), get_user_token(),
        include_all_fields=ALLOW_ALL_AGGREGATE,
    )


@mcp.tool(
    tags={"advanced", "presenton"}, annotations=ToolAnnotations(title="Derive Presentation", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def derive_presentation(
    presentation_id: str,
    slides: list[SlideContentUpdateItem],
    export_as: str = "pptx",
    ctx: Context = None,
) -> dict[str, Any]:
    """Derive a new presentation from an existing one.

    Args:
        presentation_id: Source presentation ID (e.g. 'a1b2c3d4-...').
        slides: Slide content updates (e.g. [{'index': 0, 'content': {'hero': {'title': 'New'}}}]).
        export_as: Export format (e.g. 'pptx' or 'pdf').
    """
    params = EditPresentationParam(
        presentation_id=presentation_id,
        slides=slides,
        export_as=export_as,
    )
    return await get_client().derive_presentation(
        params.model_dump(exclude_unset=True), get_user_token(),
        include_all_fields=ALLOW_ALL_AGGREGATE,
    )


@mcp.tool(
    tags={"primary", "presenton"}, annotations=ToolAnnotations(title="Prepare Presentation", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def prepare_presentation(
    id: str,
    outlines: list[SlideOutlineItem],
    layout: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Prepare a presentation by assigning layouts to slides.

    Args:
        id: Presentation ID (e.g. 'a1b2c3d4-...').
        outlines: Slide outline items (e.g. [{'content': '# Intro\\nOverview...'}]).
        layout: Layout template name (e.g. 'standard').
    """
    outlines_list = [o.model_dump() for o in outlines]
    payload = {"presentation_id": id, "outlines": outlines_list, "layout": layout}
    return await get_client().prepare_presentation(payload, get_user_token(), include_all_fields=ALLOW_ALL_AGGREGATE)


# =============================================================================
# Template Management Tools (9 tools)
# =============================================================================


@mcp.tool(
    tags={"basic", "presenton"}, annotations=ToolAnnotations(title="List All Templates", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def list_all_templates(
    include_all_fields: bool = False,
    page: int = 1,
    page_size: int = 20,
    ctx: Context = None,
) -> dict[str, Any]:
    """List all template records.

    Args:
        include_all_fields: Default False (common fields only). Set True for all fields.
        page: Page number (1-indexed) (Default: 1).
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


@mcp.tool(
    tags={"basic", "presenton"}, annotations=ToolAnnotations(title="Get Template By Id", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def get_template_by_id(
    id: str,
    include_all_fields: bool = False,
    ctx: Context = None,
) -> dict[str, Any]:
    """Get a single template by its ID.

    Args:
        id: The unique ID of the template (e.g. 'a1b2c3d4-...').
        include_all_fields: Default False (common fields only). Set True for all fields.
    """
    return await get_client().get_template_by_id(id, get_user_token(), include_all_fields=include_all_fields)


@mcp.tool(
    tags={"primary", "presenton"}, annotations=ToolAnnotations(title="Create Template Async", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def create_template_async(
    pptx_url: str,
    slide_image_urls: list[str],
    fonts: list[FontEntry] = [],
    name: str = "",
    description: str = "",
    ctx: Context = None,
) -> dict[str, Any]:
    """Create a new template asynchronously from a PPTX file URL.

    Args:
        pptx_url: URL path to the PPTX file (e.g. '/app_data/exports/template.pptx').
        slide_image_urls: Slide preview image URLs, one per slide (e.g. ['/images/slide1.png']).
        fonts: Font entries mapping font names to URLs (e.g. [FontEntry(name='Inter', url='https://...')]).
        name: Template name (e.g. 'My Template').
        description: Template description (e.g. 'Professional template for reports').
    """
    payload = {
        "pptx_url": pptx_url,
        "slide_image_urls": slide_image_urls,
        "fonts": {f.name: f.url for f in fonts},
    }
    if name:
        payload["name"] = name
    if description:
        payload["description"] = description
    return await get_client().create_template_async(payload, get_user_token(), include_all_fields=ALLOW_ALL_AGGREGATE)


@mcp.tool(
    tags={"primary", "presenton"}, annotations=ToolAnnotations(title="Create Template Init", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def create_template_init(
    pptx_url: str,
    slide_image_urls: list[str],
    name: str = "",
    description: str = "",
    ctx: Context = None,
) -> dict[str, Any]:
    """Create a template synchronously from a PPTX file path.

    Args:
        pptx_url: PPTX file path (e.g. '/app_data/exports/template.pptx').
        slide_image_urls: Slide preview image URLs, one per slide (e.g. ['/images/slide1.png']).
        name: Template name (e.g. 'My Template').
        description: Template description (e.g. 'Professional template for reports').
    """
    payload = {
        "pptx_url": pptx_url,
        "slide_image_urls": slide_image_urls,
    }
    if name:
        payload["name"] = name
    if description:
        payload["description"] = description
    template_id = await get_client().create_template_init(payload, get_user_token(), include_all_fields=ALLOW_ALL_AGGREGATE)
    return {"id": template_id}


@mcp.tool(
    tags={"primary", "presenton"}, annotations=ToolAnnotations(title="Create Template Layouts", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def create_template_layouts(
    template_id: str,
    index: Optional[int] = None,
    indices: Optional[list[int]] = None,
    ctx: Context = None,
) -> dict[str, Any]:
    """Create slide layouts for a template.

    Args:
        template_id: The unique ID of the template (e.g. 'a1b2c3d4-...').
        index: A single slide index to create a layout for (e.g. 0).
        indices: Multiple slide indices to create layouts for (e.g. [0, 1, 2]).
    """
    payload = {"template_id": template_id}
    if index is not None:
        payload["index"] = index
    if indices is not None:
        payload["indices"] = indices
    return await get_client().create_template_layouts(payload, get_user_token(), include_all_fields=ALLOW_ALL_AGGREGATE)


@mcp.tool(
    tags={"advanced", "presenton"}, annotations=ToolAnnotations(title="Generate Template Blocks", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def generate_template_blocks(
    template_id: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Generate merged component blocks for a template.

    Args:
        template_id: The unique ID of the template (e.g. 'a1b2c3d4-...').
    """
    payload = {"template_id": template_id}
    return await get_client().generate_template_blocks(payload, get_user_token(), include_all_fields=ALLOW_ALL_AGGREGATE)


@mcp.tool(
    tags={"primary", "presenton"}, annotations=ToolAnnotations(title="Update Template Layouts", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def update_template_layouts(
    template_id: str,
    index: Optional[int] = None,
    layout: Optional[LayoutObject] = None,
    layouts: Optional[list[LayoutObject]] = None,
    ctx: Context = None,
) -> dict[str, Any]:
    """Update slide layouts within a template.

    Args:
        template_id: Template ID (e.g. 'a1b2c3d4-...').
        index: Slide index to update (used with single layout) (e.g. 0).
        layout: Layout object to set for a single slide (e.g. LayoutObject(id='lay1', description='desc', components=[...])).
        layouts: Batch list of layouts for updating multiple slides (e.g. [LayoutObject(...), LayoutObject(...)]).
    """
    payload: dict[str, Any] = {}
    if index is not None:
        payload["index"] = index
    if layout is not None:
        payload["layout"] = layout.model_dump()
    if layouts is not None:
        payload["layouts"] = [l.model_dump() for l in layouts]
    return await get_client().update_template_layouts(template_id, payload, get_user_token(), include_all_fields=ALLOW_ALL_AGGREGATE)


@mcp.tool(
    tags={"basic", "presenton"}, annotations=ToolAnnotations(title="Update Template", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def update_template(
    id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    ctx: Context = None,
) -> dict[str, Any]:
    """Update a template's metadata.

    Args:
        id: The unique ID of the template to update (e.g. 'a1b2c3d4-...').
        name: New template name (e.g. 'Updated Template').
        description: New template description (e.g. 'Updated description').
    """
    payload = {}
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    return await get_client().update_template(id, payload, get_user_token(), include_all_fields=ALLOW_ALL_AGGREGATE)


@mcp.tool(
    tags={"basic", "presenton"}, annotations=ToolAnnotations(title="Delete Template By Id", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def delete_template_by_id(
    id: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Delete a template by its ID.

    Args:
        id: The unique ID of the template to delete (e.g. 'a1b2c3d4-...').
    """
    await get_client().delete_template_by_id(id, get_user_token())
    return {"deleted": True, "id": id}


# =============================================================================
# Theme Management Tools (6 tools)
# =============================================================================


@mcp.tool(
    tags={"basic", "presenton"}, annotations=ToolAnnotations(title="List Default Themes", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
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


@mcp.tool(
    tags={"basic", "presenton"}, annotations=ToolAnnotations(title="List All Themes", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
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


@mcp.tool(
    tags={"basic", "presenton"}, annotations=ToolAnnotations(title="Create Theme", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def create_theme(
    name: str,
    description: str = "",
    company_name: str = "",
    data: ThemeData = ThemeData(),
    ctx: Context = None,
) -> dict[str, Any]:
    """Create a new custom theme.

    Args:
        name: Theme name (e.g. 'Corporate Blue').
        description: Theme description (e.g. 'Professional blue theme').
        company_name: Company name (e.g. 'Acme Corp').
        data: Theme configuration (e.g. ThemeData(colors={'primary': '#2563EB'})).
    """
    params = CreateThemeParam(
        name=name, description=description,
        company_name=company_name, data=data,
    )
    return await get_client().create_theme(
        params.model_dump(exclude_unset=True), get_user_token(),
        include_all_fields=ALLOW_ALL_AGGREGATE,
    )


@mcp.tool(
    tags={"primary", "presenton"}, annotations=ToolAnnotations(title="Update Theme", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def update_theme(
    id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    company_name: Optional[str] = None,
    data: Optional[ThemeData] = None,
    ctx: Context = None,
) -> dict[str, Any]:
    """Update an existing custom theme.

    Args:
        id: Theme ID (e.g. 'a1b2c3d4-...').
        name: Updated theme name (e.g. 'Corporate Blue v2').
        description: Updated description (e.g. 'Updated blue theme').
        company_name: Updated company name (e.g. 'Acme Corp').
        data: Updated theme configuration (e.g. ThemeData(name='Corporate Blue')).
    """
    params = UpdateThemeParam(
        name=name, description=description,
        company_name=company_name, data=data,
    )
    p = params.model_dump(exclude_unset=True, exclude_none=True)
    return await get_client().update_theme(id, p, get_user_token(), include_all_fields=ALLOW_ALL_AGGREGATE)


@mcp.tool(
    tags={"basic", "presenton"}, annotations=ToolAnnotations(title="Delete Theme By Id", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def delete_theme_by_id(
    id: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Delete a custom theme by its ID.

    Args:
        id: The unique ID of the theme to delete (e.g. 'a1b2c3d4-...').
    """
    await get_client().delete_theme_by_id(id, get_user_token())
    return {"deleted": True, "id": id}


@mcp.tool(
    tags={"primary", "presenton"}, annotations=ToolAnnotations(title="Generate Theme", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def generate_theme(
    primary: Optional[str] = None,
    background: Optional[str] = None,
    accent_1: Optional[str] = None,
    accent_2: Optional[str] = None,
    text_1: Optional[str] = None,
    text_2: Optional[str] = None,
    ctx: Context = None,
) -> dict[str, Any]:
    """Generate a color palette and theme data from optional color hints.

    Args:
        primary: Primary color hex value (e.g. #2563EB).
        background: Background color hex value (e.g. #FFFFFF).
        accent_1: First accent color hex value (e.g. #FF5733).
        accent_2: Second accent color hex value (e.g. #33FF57).
        text_1: Primary text color hex value (e.g. #000000).
        text_2: Secondary text color hex value (e.g. #666666).
    """
    params = GenerateThemeParam(
        primary=primary,
        background=background,
        accent_1=accent_1,
        accent_2=accent_2,
        text_1=text_1,
        text_2=text_2,
    )
    return await get_client().generate_theme(
        params.model_dump(exclude_unset=True), get_user_token(),
        include_all_fields=ALLOW_ALL_AGGREGATE,
    )


# =============================================================================
# Image & Icon Management Tools (6 tools)
# =============================================================================


@mcp.tool(
    tags={"basic", "presenton"}, annotations=ToolAnnotations(title="Search Stock Images", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True)
)
async def search_stock_images(
    query: str,
    limit: int = 12,
    ctx: Context = None,
) -> dict[str, Any]:
    """Search stock images from integrated providers.

    Args:
        query: Search query string (e.g. 'business meeting').
        limit: Maximum number of results (1-30).
    """
    data = await get_client().search_stock_images(query, get_user_token(), limit=limit)
    if isinstance(data, dict):
        results = data.get("results", data.get("photos", data.get("videos", [])))
        return {"items": json_to_toon(results)}
    return {"items": json_to_toon(data) if isinstance(data, list) else data}


@mcp.tool(
    tags={"primary", "presenton"}, annotations=ToolAnnotations(title="Generate Image", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True)
)
async def generate_image(
    prompt: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Generate an image using AI based on a text prompt.

    Args:
        prompt: Description of the image to generate (e.g. 'A beautiful sunset over mountains').
    """
    result = await get_client().generate_image(prompt, get_user_token())
    if isinstance(result, str):
        return {"image_url": result, "prompt": prompt}
    return result


@mcp.tool(
    tags={"primary", "presenton"}, annotations=ToolAnnotations(title="List Generated Images", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
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


@mcp.tool(
    tags={"basic", "presenton"}, annotations=ToolAnnotations(title="List Uploaded Images", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
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


@mcp.tool(
    tags={"primary", "presenton"}, annotations=ToolAnnotations(title="Search Icons", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True)
)
async def search_icons(
    query: str,
    limit: int = 20,
    ctx: Context = None,
) -> dict[str, Any]:
    """Search icons from the Phosphor icon library.

    Args:
        query: Search query string (e.g. 'arrow').
        limit: Maximum number of results (1-50).
    """
    data = await get_client().search_icons(query, get_user_token(), limit=limit)
    return {"items": json_to_toon(data) if isinstance(data, list) else data}


# =============================================================================
# Font & File Management Tools (4 tools)
# =============================================================================


@mcp.tool(
    tags={"basic", "presenton"}, annotations=ToolAnnotations(title="List All Fonts", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
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


@mcp.tool(
    tags={"basic", "presenton"}, annotations=ToolAnnotations(title="List Uploaded Fonts", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
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


@mcp.tool(
    tags={"primary", "presenton"}, annotations=ToolAnnotations(title="Decompose File", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def decompose_file(
    file_paths: list[str],
    language: str = "",
    ctx: Context = None,
) -> dict[str, Any]:
    """Decompose uploaded files into text for presentation content.

    Args:
        file_paths: List of file paths (strings) to decompose (e.g. ['/tmp/report.pptx']).
        language: Language code for document processing (e.g. 'en').
    """
    params = DecomposeFileParam(file_paths=file_paths, language=language)
    data = await get_client().decompose_file(
        params.model_dump(exclude_unset=True), get_user_token()
    )
    return {"items": data} if isinstance(data, list) else data


# =============================================================================
# Slide & Outline Management Tools (4 tools)
# =============================================================================


@mcp.tool(
    tags={"primary", "presenton"}, annotations=ToolAnnotations(title="Get Outline By Id", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def get_outline_by_id(
    id: str,
    include_all_fields: bool = False,
    ctx: Context = None,
) -> dict[str, Any]:
    """Get a presentation outline by its ID.

    Args:
        id: The unique ID of the outline (e.g. 'a1b2c3d4-...').
        include_all_fields: Default False (common fields only). Set True for all fields.
    """
    return await get_client().get_outline_by_id(id, get_user_token(), include_all_fields=include_all_fields)


@mcp.tool(
    tags={"primary", "presenton"}, annotations=ToolAnnotations(title="Update Outline", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def update_outline(
    id: str,
    slides: list[SlideOutlineItem],
    ctx: Context = None,
) -> dict[str, Any]:
    """Update a presentation outline.

    Args:
        id: Outline ID (e.g. 'a1b2c3d4-...').
        slides: Updated slide outline items (e.g. [{'content': '# Intro\\n\\nOverview...'}]).
    """
    payload = {"slides": [s.model_dump() for s in slides]}
    return await get_client().update_outline(id, payload, get_user_token(), include_all_fields=ALLOW_ALL_AGGREGATE)


@mcp.tool(
    tags={"primary", "presenton"}, annotations=ToolAnnotations(title="Edit Slide", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def edit_slide(
    presentation_id: str,
    index: int,
    prompt: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Edit a slide's content using an AI prompt.

    Args:
        presentation_id: The unique ID of the presentation (e.g. 'a1b2c3d4-...').
        index: The 0-based index of the slide to edit (e.g. 0 for the first slide, 4 for the 5th slide).
        prompt: Instructions for the AI on how to edit the slide (e.g. 'Make this slide more concise').
    """
    slide_id = await get_client().resolve_slide_id(presentation_id, index, get_user_token())
    params = EditSlideParam(id=slide_id, prompt=prompt)
    return await get_client().edit_slide(
        params.model_dump(exclude_unset=True), get_user_token(),
        include_all_fields=ALLOW_ALL_AGGREGATE,
    )


@mcp.tool(
    tags={"advanced", "presenton"}, annotations=ToolAnnotations(title="Edit Slide Html", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def edit_slide_html(
    presentation_id: str,
    index: int,
    prompt: str,
    html: str = "",
    ctx: Context = None,
) -> dict[str, Any]:
    """Edit a slide's HTML representation using an AI prompt.

    Args:
        presentation_id: The unique ID of the presentation (e.g. 'a1b2c3d4-...').
        index: The 0-based index of the slide to edit (e.g. 0 for the first slide).
        prompt: Instructions for the AI on how to edit the slide HTML (e.g. 'Improve the layout').
        html: The current HTML content of the slide to edit (e.g. '<p>hello</p>').
    """
    slide_id = await get_client().resolve_slide_id(presentation_id, index, get_user_token())
    params = EditSlideHtmlParam(id=slide_id, prompt=prompt, html=html)
    return await get_client().edit_slide_html(
        params.model_dump(exclude_unset=True), get_user_token(),
        include_all_fields=ALLOW_ALL_AGGREGATE,
    )


# =============================================================================
# Chat & Async Operations Tools (7 tools)
# =============================================================================


@mcp.tool(
    tags={"primary", "presenton"}, annotations=ToolAnnotations(title="List Chat Conversations", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def list_chat_conversations(
    presentation_id: str,
    include_all_fields: bool = False,
    ctx: Context = None,
) -> dict[str, Any]:
    """List chat conversations for a presentation.

    Args:
        presentation_id: The unique ID of the presentation (e.g. 'a1b2c3d4-...').
        include_all_fields: Default False (common fields only). Set True for all fields.
    """
    data = await get_client().list_chat_conversations(
        presentation_id, get_user_token(),
        include_all_fields=include_all_fields if ALLOW_ALL_AGGREGATE else False,
    )
    return {"items": json_to_toon(data)}


@mcp.tool(
    tags={"primary", "presenton"}, annotations=ToolAnnotations(title="Get Chat History", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def get_chat_history(
    presentation_id: str,
    conversation_id: str,
    include_all_fields: bool = False,
    ctx: Context = None,
) -> dict[str, Any]:
    """Get chat message history for a conversation.

    Args:
        presentation_id: The unique ID of the presentation (e.g. 'a1b2c3d4-...').
        conversation_id: The unique ID of the chat conversation (e.g. 'a1b2c3d4-...').
        include_all_fields: Default False (common fields only). Set True for all fields.
    """
    return await get_client().get_chat_history(
        presentation_id, conversation_id, get_user_token(),
        include_all_fields=include_all_fields,
    )


@mcp.tool(
    tags={"primary", "presenton"}, annotations=ToolAnnotations(title="Delete Chat Conversation", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def delete_chat_conversation(
    presentation_id: str,
    conversation_id: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Delete a chat conversation.

    Args:
        presentation_id: The unique ID of the presentation (e.g. 'a1b2c3d4-...').
        conversation_id: The unique ID of the chat conversation to delete (e.g. 'a1b2c3d4-...').
    """
    await get_client().delete_chat_conversation(
        presentation_id, conversation_id, get_user_token()
    )
    return {"deleted": True, "conversation_id": conversation_id}


@mcp.tool(
    tags={"primary", "presenton"}, annotations=ToolAnnotations(title="Send Chat Message", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def send_chat_message(
    presentation_id: str,
    message: str,
    conversation_id: str = "",
    attachments: Optional[list[ChatAttachmentItem]] = None,
    ctx: Context = None,
) -> dict[str, Any]:
    """Send a chat message for a presentation.

    Args:
        presentation_id: Presentation ID (e.g. 'a1b2c3d4-...').
        message: Message content (e.g. 'What is this about?').
        conversation_id: Conversation ID to continue. Empty starts new (e.g. 'a1b2c3d4-...').
        attachments: File attachments (e.g. [ChatAttachmentItem(name='report.pptx', file_path='/tmp/r.pptx')]).
    """
    params = ChatMessageParam(
        presentation_id=presentation_id,
        message=message,
        conversation_id=conversation_id or None,
        attachments=attachments,
    )
    return await get_client().send_chat_message(
        params.model_dump(exclude_unset=True, exclude_none=True), get_user_token(),
        include_all_fields=ALLOW_ALL_AGGREGATE,
    )


@mcp.tool(
    tags={"basic", "presenton"}, annotations=ToolAnnotations(title="List Async Tasks", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
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


@mcp.tool(
    tags={"primary", "presenton"}, annotations=ToolAnnotations(title="Get Async Task Status", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def get_async_task_status(
    id: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Get the status of an async task by its ID.

    Args:
        id: The unique ID of the async task (e.g. 'a1b2c3d4-...').
    """
    return await get_client().get_async_task_status(id, get_user_token())


@mcp.tool(
    tags={"primary", "presenton"}, annotations=ToolAnnotations(title="Get Presentation Generation Status", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def get_presentation_generation_status(
    id: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Check the async generation status of a presentation by task ID.

    Args:
        id: The task ID returned from create_presentation (e.g. 'a1b2c3d4-...').
    """
    return await get_client().get_presentation_generation_status(id, get_user_token())


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

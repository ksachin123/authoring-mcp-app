import logging
import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import FileResponse, Response
from research_authoring.db.connection import create_db
from research_authoring.logging_utils import configure_logging
from research_authoring.tools.register_tools import register_tools

load_dotenv()
configure_logging()
logger = logging.getLogger("research_authoring.server")

db_path = os.environ.get("DB_PATH", "./data/poc.db")
os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
db = create_db(db_path)
logger.info("db ready path=%s", db_path)

# NOTE: deviation from the task brief for Step 9. The brief's example uses a
# bare `@mcp.resource("ui://widget/report-workspace.html")` decorator with no
# extra kwargs. The installed mcp SDK (1.28.1) `FastMCP.resource()` decorator
# does accept `mime_type` and `meta` kwargs (see
# .venv/lib/python*/site-packages/mcp/server/fastmcp/server.py, ~line 534).
#
# The built `dist/index.html` references its script as the relative
# "./bundle.js" -- resolved live against ChatGPT and confirmed broken: `ui://`
# is a custom scheme with no origin for the sandboxed iframe to resolve a
# relative URL against, so the widget's JS silently failed to load (React
# never mounted, blank widget) even though the tool call, its `_meta`, and
# this resource fetch all succeeded. `report_workspace_widget()` below
# inlines bundle.js directly into the served HTML instead, so the resource is
# fully self-contained -- the "/widget/bundle.js" custom_route is no longer
# needed by the widget itself and is kept only as a standalone way to check
# the built bundle is present and served correctly.
#
# mime_type was originally "text/html+skybridge" (the older ChatGPT-specific
# convention). Live logging (added separately) showed ChatGPT calling
# run_eval_tool/approve_artefact_tool successfully with correct
# `_meta["openai/outputTemplate"]` on every call, but NEVER once calling
# resources/read for this resource across an entire session -- i.e. ChatGPT
# wasn't failing to fetch the widget, it was never attempting to. OpenAI's
# current Apps SDK docs (openai/apps-sdk "Add UI to your MCP server") specify
# the newer MCP Apps standard mimeType "text/html;profile=mcp-app" as
# "required for widget recognition", plus `_meta.ui.resourceUri` (not just
# `openai/outputTemplate`) linking the tool to the resource, and a `_meta.ui`
# block on the resource itself. Switched to that mimeType and meta shape
# here.
_WIDGET_DIST = os.path.join(os.path.dirname(__file__), "..", "..", "..", "widget", "dist")

for _asset in ("index.html", "bundle.js"):
    _asset_path = os.path.join(_WIDGET_DIST, _asset)
    if os.path.exists(_asset_path):
        logger.info("widget asset found: %s", _asset_path)
    else:
        logger.warning("widget asset MISSING (widget will not render): %s", _asset_path)


# REVERTED a content-hash-derived URI (e.g. "report-workspace-<sha>.html").
# The theory was that a fresh URI per deploy would prevent ChatGPT from ever
# showing stale cached widget content -- but after deploying it, EVERY
# run_eval_tool call started returning "Error loading app: Failed to fetch
# template" in ChatGPT, 100% reproducibly, across multiple fresh
# conversations, while resources/read for that exact URI kept succeeding
# perfectly over raw MCP calls (verified directly: 200, correct mimeType,
# correct 1MB+ content, clean URI with no hidden characters). That split --
# server provably correct, ChatGPT consistently refusing to fetch -- points
# to ChatGPT's Developer Mode binding/pinning the widget's resource URI to
# the connector at connect-time rather than re-discovering it on every tool
# call, so a URI that changes on every deploy breaks resolution entirely
# instead of solving the staleness problem. Back to a fixed URI; the actual
# fix for stale widget content is reconnecting the app in ChatGPT after a
# widget change (which is what got the widget rendering at all earlier in
# this debugging session), not changing the URI server-side.
_WIDGET_URI = "ui://widget/report-workspace.html"
logger.info("widget resource uri: %s", _WIDGET_URI)

# NOTE: deviation from the task brief. The installed mcp SDK's FastMCP.run()
# only accepts a `transport` argument (and `mount_path`) -- host/port are not
# accepted there. Instead, FastMCP.__init__ takes `host`/`port` directly, which
# it stores in self.settings and uses when constructing the streamable-http
# ASGI app. Render (and most PaaS hosts) require binding 0.0.0.0 and the port
# they inject via the PORT env var, not localhost/a hardcoded port. See Task 18
# for the full Render deployment configuration.
_port = int(os.environ.get("PORT", 8000))
mcp = FastMCP("research-authoring-poc", host="0.0.0.0", port=_port)
register_tools(mcp, db, widget_uri=_WIDGET_URI)
logger.info("registered %d tools", len(mcp._tool_manager.list_tools()))


@mcp.resource(
    _WIDGET_URI,
    mime_type="text/html;profile=mcp-app",
    meta={"ui": {"prefersBorder": True}},
)
def report_workspace_widget() -> str:
    logger.info("resource read: %s", _WIDGET_URI)
    with open(os.path.join(_WIDGET_DIST, "index.html")) as f:
        html = f.read()
    with open(os.path.join(_WIDGET_DIST, "bundle.js")) as f:
        bundle_js = f.read()
    # `ui://...` is a custom scheme with no origin for ChatGPT's sandboxed
    # iframe to resolve a relative `<script src="./bundle.js">` against, so
    # the script silently fails to load -- React never mounts and the widget
    # renders blank -- even though the tool call, its `_meta`, and this
    # resource fetch all succeed (confirmed live against the deployed
    # server: the tool call and resource read both work, but the widget
    # never visibly renders). Inline the bundle directly instead, matching
    # the working reference app in ../mcp-app, which ships a single
    # self-contained widget file with no external script fetch at all.
    # Escape any literal "</script" inside the bundle so it can't
    # prematurely close this HTML <script> tag.
    inline_script = f'<script type="module">{bundle_js.replace("</script", "<\\/script")}</script>'
    return html.replace('<script type="module" src="./bundle.js"></script>', inline_script)


@mcp.custom_route("/widget/bundle.js", methods=["GET"])
async def report_workspace_widget_bundle(request: Request) -> Response:
    bundle_path = os.path.join(_WIDGET_DIST, "bundle.js")
    if not os.path.exists(bundle_path):
        logger.warning("GET /widget/bundle.js -> 404 (not built at %s)", bundle_path)
        return Response("widget bundle not built", status_code=404)
    logger.info("GET /widget/bundle.js -> 200")
    return FileResponse(bundle_path, media_type="application/javascript")


@mcp.custom_route("/health", methods=["GET"])
async def healthz(request: Request) -> Response:
    logger.debug("GET /health -> 200")
    return Response("ok", status_code=200)


if __name__ == "__main__":
    logger.info("starting research-authoring-poc MCP server on 0.0.0.0:%d", _port)
    mcp.run(transport="streamable-http")

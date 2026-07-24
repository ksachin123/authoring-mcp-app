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

# NOTE: deviation from the task brief. The installed mcp SDK's FastMCP.run()
# only accepts a `transport` argument (and `mount_path`) -- host/port are not
# accepted there. Instead, FastMCP.__init__ takes `host`/`port` directly, which
# it stores in self.settings and uses when constructing the streamable-http
# ASGI app. Render (and most PaaS hosts) require binding 0.0.0.0 and the port
# they inject via the PORT env var, not localhost/a hardcoded port. See Task 18
# for the full Render deployment configuration.
_port = int(os.environ.get("PORT", 8000))
mcp = FastMCP("research-authoring-poc", host="0.0.0.0", port=_port)
register_tools(mcp, db)
logger.info("registered %d tools", len(mcp._tool_manager.list_tools()))

# NOTE: deviation from the task brief for Step 9. The brief's example uses a
# bare `@mcp.resource("ui://widget/report-workspace.html")` decorator with no
# extra kwargs. The installed mcp SDK (1.28.1) `FastMCP.resource()` decorator
# does accept `mime_type` and `meta` kwargs (see
# .venv/lib/python*/site-packages/mcp/server/fastmcp/server.py, ~line 534), so
# we pass `mime_type="text/html+skybridge"` here per the Apps SDK convention
# for fullscreen widget resources. There is no dedicated API for serving a
# widget's supporting static assets (e.g. bundle.js) as part of the resource
# registration itself -- FastMCP resources are single documents read via
# `resources/read`, not a static file mount. bundle.js is instead served via
# `@mcp.custom_route(...)`, which registers an arbitrary Starlette HTTP route
# on the same ASGI app (see same file, ~line 705) at "/widget/bundle.js". The
# built `dist/index.html` (per the brief's exact Step 7 content) references
# its script as the relative "./bundle.js", which resolves correctly when the
# file is served directly from this route's sibling path; whether ChatGPT's
# renderer needs an absolute URL instead when it loads the `ui://` resource
# is unverified until Task 17's live ChatGPT pass.
#
# `run_eval_tool` and `approve_artefact_tool` declare
# `_meta={"openai/outputTemplate": "ui://widget/report-workspace.html"}` in
# `register_tools.py` so ChatGPT knows to render this resource after either
# tool call -- see register_tools.py's `_WIDGET_OUTPUT_TEMPLATE`.
_WIDGET_DIST = os.path.join(os.path.dirname(__file__), "..", "..", "..", "widget", "dist")

for _asset in ("index.html", "bundle.js"):
    _asset_path = os.path.join(_WIDGET_DIST, _asset)
    if os.path.exists(_asset_path):
        logger.info("widget asset found: %s", _asset_path)
    else:
        logger.warning("widget asset MISSING (widget will not render): %s", _asset_path)


@mcp.resource("ui://widget/report-workspace.html", mime_type="text/html+skybridge")
def report_workspace_widget() -> str:
    logger.info("resource read: ui://widget/report-workspace.html")
    with open(os.path.join(_WIDGET_DIST, "index.html")) as f:
        return f.read()


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

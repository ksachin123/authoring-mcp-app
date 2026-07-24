import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import FileResponse, Response
from research_authoring.db.connection import create_db
from research_authoring.tools.register_tools import register_tools

load_dotenv()

os.makedirs(os.path.dirname(os.environ.get("DB_PATH", "./data/poc.db")) or ".", exist_ok=True)
db = create_db(os.environ.get("DB_PATH", "./data/poc.db"))

# NOTE: deviation from the task brief. The installed mcp SDK's FastMCP.run()
# only accepts a `transport` argument (and `mount_path`) -- host/port are not
# accepted there. Instead, FastMCP.__init__ takes `host`/`port` directly, which
# it stores in self.settings and uses when constructing the streamable-http
# ASGI app. Render (and most PaaS hosts) require binding 0.0.0.0 and the port
# they inject via the PORT env var, not localhost/a hardcoded port. See Task 18
# for the full Render deployment configuration.
mcp = FastMCP("research-authoring-poc", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
register_tools(mcp, db)

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
# We deliberately do NOT set `_meta`/`openai/outputTemplate` on
# `run_eval_tool` / `approve_artefact_tool` in this task -- doing so would
# require editing the `@mcp.tool(...)` decorators in
# `research_authoring/tools/register_tools.py`, which is out of scope here
# (Task 16 instructions restrict changes to `server.py` only). That tool-meta
# wiring, and verifying the exact `openai/outputTemplate` key/value shape
# ChatGPT expects, is left for Task 17's live ChatGPT Developer Mode pass, per
# this task brief's own note.
_WIDGET_DIST = os.path.join(os.path.dirname(__file__), "..", "..", "..", "widget", "dist")


@mcp.resource("ui://widget/report-workspace.html", mime_type="text/html+skybridge")
def report_workspace_widget() -> str:
    with open(os.path.join(_WIDGET_DIST, "index.html")) as f:
        return f.read()


@mcp.custom_route("/widget/bundle.js", methods=["GET"])
async def report_workspace_widget_bundle(request: Request) -> Response:
    bundle_path = os.path.join(_WIDGET_DIST, "bundle.js")
    if not os.path.exists(bundle_path):
        return Response("widget bundle not built", status_code=404)
    return FileResponse(bundle_path, media_type="application/javascript")


@mcp.custom_route("/health", methods=["GET"])
async def healthz(request: Request) -> Response:
    return Response("ok", status_code=200)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")

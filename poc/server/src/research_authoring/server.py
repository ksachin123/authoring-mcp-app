import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
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

if __name__ == "__main__":
    mcp.run(transport="streamable-http")

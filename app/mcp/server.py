"""Run the optional StudyPilot MCP server over stdio."""


def main() -> None:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as error:
        raise RuntimeError(
            "The MCP server requires the optional 'mcp' dependency. "
            "Install project requirements first."
        ) from error

    from app.mcp import tools

    server = FastMCP("StudyPilot")

    @server.tool()
    def list_open_tasks() -> dict:
        """Return the first 50 incomplete tasks and the total open task count."""
        return tools.list_open_tasks()

    @server.tool()
    def add_study_task(
        title: str,
        subject: str = "General",
        due_date: str | None = None,
        estimated_minutes: int = 30,
    ) -> dict:
        """Create a study task with an optional ISO-formatted due date."""
        return tools.add_study_task(title, subject, due_date, estimated_minutes)

    @server.tool()
    def complete_study_task(task_id: int) -> dict:
        """Mark a study task complete."""
        return tools.complete_study_task(task_id)

    @server.tool()
    def get_study_plan(days: int = 7) -> dict:
        """Return an upcoming study plan for open tasks."""
        return tools.get_study_plan(days)

    server.run(transport="stdio")


if __name__ == "__main__":
    main()

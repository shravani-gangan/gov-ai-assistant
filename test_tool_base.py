import asyncio
from src.tools.base import BaseTool


class TestTool(BaseTool):
    name = "test_tool"

    async def _execute(self, **kwargs):
        return {"message": "tool working"}


async def main():
    tool = TestTool()
    result = await tool.run()

    print(result.tool_name)
    print(result.success)
    print(result.data)

asyncio.run(main())
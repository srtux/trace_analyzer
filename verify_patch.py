try:
    from mcp.client.session import ClientSession
    from pydantic import BaseModel

    print(
        f"ClientSession has patch: {hasattr(ClientSession, '__get_pydantic_core_schema__')}"
    )

    class TestModel(BaseModel):
        """Test model for pydantic bridge."""

        session: ClientSession

    print("Success: Model created!")
except Exception as e:
    print(f"Failed: {e}")
    import traceback

    traceback.print_exc()

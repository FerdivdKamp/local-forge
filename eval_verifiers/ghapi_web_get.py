"""Check the ghapi endpoint and exact parameters without making network calls."""

import asyncio
import importlib.metadata
import inspect
import sys
import types
import unittest


assert importlib.metadata.version("ghapi") == "2.1.4", "Fixture requires ghapi 2.1.4"

calls = []


class FakeIssues:
    async def get(self, **kwargs):
        calls.append(("issues.get", kwargs))
        return types.SimpleNamespace(title=f"Issue {kwargs['issue_number']}", body="Details")

    def __getattr__(self, name):
        raise AssertionError(f"Wrong issues endpoint: {name}")


class FakeGhApi:
    def __init__(self, *args, **kwargs):
        assert not args and kwargs.get("sync") is not True
        self.issues = FakeIssues()

    def __getattr__(self, name):
        raise AssertionError(f"Wrong ghapi operation group: {name}")


fake_package = types.ModuleType("ghapi")
fake_package.__path__ = []
fake_core = types.ModuleType("ghapi.core")
fake_package.GhApi = FakeGhApi
fake_core.GhApi = FakeGhApi
sys.modules["ghapi"] = fake_package
sys.modules["ghapi.core"] = fake_core

from issue_lookup import fetch_issue  # noqa: E402


class HiddenTests(unittest.TestCase):
    def test_async_exact_endpoint_and_parameters(self):
        self.assertTrue(inspect.iscoroutinefunction(fetch_issue))
        for owner, repo, number in (("octo", "widget", 42), ("fastai", "ghapi", 7)):
            calls.clear()
            result = asyncio.run(fetch_issue(owner, repo, number))
            self.assertEqual(calls, [("issues.get", {
                "owner": owner, "repo": repo, "issue_number": number,
            })])
            self.assertEqual(result, {"title": f"Issue {number}", "body": "Details"})


if __name__ == "__main__":
    unittest.main()

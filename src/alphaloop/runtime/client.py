from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from alphaloop.contracts.research_spec import ResearchSpec


class JobClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def create_run(self, spec: ResearchSpec) -> dict[str, Any]:
        return self._request("POST", "/v1/jobs", spec.to_dict())

    def get_run(self, run_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/jobs/{quote(run_id, safe='')}")

    def cancel_run(self, run_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/v1/jobs/{quote(run_id, safe='')}/cancel",
        )

    def resume_run(self, run_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/v1/jobs/{quote(run_id, safe='')}/resume",
        )

    def healthz(self) -> dict[str, Any]:
        return self._request("GET", "/healthz")

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        request = Request(
            self.base_url + path,
            data=body,
            headers=headers,
            method=method,
        )
        with urlopen(request) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not isinstance(result, dict):
            raise ValueError("response JSON must be an object")
        return result

"""Explicit model management; catalog lookups and downloads require consent."""
from __future__ import annotations

from html.parser import HTMLParser
import json
from urllib.parse import urljoin, urlsplit

import httpx

from prometheist.gui_config import ModelSelection
from prometheist.model_parameters import parameter_catalog
from prometheist.network_consent import NetworkPurpose, require_destination
from prometheist.openai_transport import OPENAI_BASE_URL, OPENAI_ORIGIN

CATALOG_ORIGIN = "https://ollama.com"
DOWNLOAD_ORIGIN = "https://registry.ollama.ai"
MODEL_HTTP_TIMEOUT_SECONDS = 10
MODEL_PULL_TIMEOUT_SECONDS = 300
MAX_CATALOG_BYTES = 2097152
MAX_CATALOG_RESULTS = 40


def ollama_request(base_url, path, *, method="GET", body=None):
    require_destination(base_url, NetworkPurpose.MODEL)
    with httpx.Client(base_url=base_url, trust_env=False, follow_redirects=False,
                      timeout=MODEL_HTTP_TIMEOUT_SECONDS) as client:
        response = client.request(method, path, json=body)
        response.raise_for_status()
        return response.json() if response.content else {}


def installed_models(base_url):
    result = ollama_request(base_url, "/api/tags")
    return result.get("models", [])


def model_details(base_url, name):
    ModelSelection(model=name)
    data = ollama_request(base_url, "/api/show", method="POST", body={"model": name})
    if data.get("remote_host") or data.get("remote_model"):
        raise ValueError("This model delegates to a cloud service; choose an explicit supported provider")
    return {"model": name, "details": data.get("details", {}),
            "capabilities": data.get("capabilities", []), "model_info": data.get("model_info", {}),
            "parameters": data.get("parameters", ""),
            "controls": parameter_catalog("ollama", name, data)}


def validate_local_selection(base_url, selection):
    details = model_details(base_url, selection.model)
    if "completion" not in details["capabilities"] and details["capabilities"]:
        raise ValueError(f"{selection.model} does not report text completion support")
    for name, value in selection.parameters.items():
        if name not in details["controls"]:
            raise ValueError(f"{selection.model} does not report support for {name}")
        maximum = details["controls"][name].get("maximum")
        if maximum is not None and isinstance(value, (int, float)) and value > maximum:
            raise ValueError(f"{name} exceeds this model's reported limit of {maximum}")
    return details


def delete_model(base_url, name):
    ModelSelection(model=name)
    return ollama_request(base_url, "/api/delete", method="DELETE", body={"model": name})


def pull_model(base_url, name, report):
    ModelSelection(model=name)
    require_destination(base_url, NetworkPurpose.MODEL)
    require_destination(DOWNLOAD_ORIGIN, NetworkPurpose.MODEL_DOWNLOAD)
    with httpx.Client(base_url=base_url, trust_env=False, follow_redirects=False,
                      timeout=MODEL_PULL_TIMEOUT_SECONDS) as client:
        with client.stream("POST", "/api/pull", json={"model": name, "stream": True}) as response:
            response.raise_for_status()
            completed = False
            for line in response.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                if data.get("error"):
                    raise ValueError(str(data["error"])[:500])
                report({key: data[key] for key in ("status", "digest", "total", "completed") if key in data})
                completed = data.get("status") == "success"
            if not completed:
                raise ValueError("Ollama download ended without a success receipt")
    return model_details(base_url, name)


class CatalogParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.names = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        href = dict(attrs).get("href", "")
        parsed = urlsplit(urljoin(CATALOG_ORIGIN, href))
        if parsed.hostname != "ollama.com" or not parsed.path.startswith("/library/"):
            return
        name = parsed.path.removeprefix("/library/").strip("/")
        if "/" in name or name in self.names:
            return
        try:
            ModelSelection(model=name)
        except ValueError:
            return
        if len(self.names) < MAX_CATALOG_RESULTS:
            self.names.append(name)


def search_catalog(query):
    require_destination(CATALOG_ORIGIN, NetworkPurpose.MODEL_CATALOG)
    with httpx.Client(trust_env=False, follow_redirects=False, timeout=MODEL_HTTP_TIMEOUT_SECONDS) as client:
        with client.stream("GET", CATALOG_ORIGIN + "/search", params={"q": query}) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_CATALOG_BYTES:
                    raise ValueError("Catalog response exceeds its read budget")
                chunks.append(chunk)
    parser = CatalogParser()
    parser.feed(b"".join(chunks).decode("utf-8", errors="replace"))
    return [{"name": name, "url": CATALOG_ORIGIN + "/library/" + name} for name in parser.names]


def openai_models(key):
    require_destination(OPENAI_ORIGIN, NetworkPurpose.MODEL)
    if not key:
        raise ValueError("Connect an API key first")
    with httpx.Client(trust_env=False, follow_redirects=False, timeout=MODEL_HTTP_TIMEOUT_SECONDS) as client:
        response = client.get(OPENAI_BASE_URL + "/models", headers={"Authorization": "Bearer " + key})
    if response.is_error:
        raise ValueError(f"OpenAI model listing returned HTTP {response.status_code}; check key and project access")
    # The listing supplies IDs, not a reliable parameter/capability schema.
    return sorted([{"id": item["id"]} for item in response.json().get("data", [])
                   if isinstance(item.get("id"), str)], key=lambda item: item["id"])

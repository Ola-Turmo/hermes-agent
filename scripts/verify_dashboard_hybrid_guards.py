#!/usr/bin/env python3
"""Fail fast if the VPS dashboard is about to start in the known-broken state."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HYBRID_MODEL = "hybrid-deepseek-gpt55-medium"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"dashboard hybrid guard failed: {message}")


def file_contains(path: str, needle: str) -> bool:
    return needle in (ROOT / path).read_text(encoding="utf-8")


def main() -> int:
    require(
        file_contains("hermes_cli/runtime_provider.py", "hybrid-local-api"),
        "runtime provider is missing the local hybrid redirect",
    )
    require(
        file_contains("hermes_cli/inventory.py", "HYBRID_LOCAL_MODEL"),
        "model inventory is missing the hybrid picker override",
    )
    chat_source = (ROOT / "web/src/pages/ChatPage.tsx").read_text(encoding="utf-8")
    require("channelParam" in chat_source, "dashboard chat no longer preserves URL channel")
    require("Uint8Array([13])" in chat_source, "dashboard chat no longer sends Enter as binary CR")
    require("WebglAddon" not in chat_source, "dashboard chat has re-enabled the xterm WebGL renderer")

    from hermes_cli.inventory import ConfigContext, build_models_payload
    from hermes_cli.runtime_provider import resolve_runtime_provider

    runtime = resolve_runtime_provider(
        requested="cloudflare-native",
        target_model=HYBRID_MODEL,
    )
    require(runtime.get("source") == "hybrid-local-api", f"unexpected runtime source: {runtime.get('source')!r}")
    require(runtime.get("provider") == "custom", f"unexpected runtime provider: {runtime.get('provider')!r}")
    require(
        runtime.get("base_url") == "http://127.0.0.1:8644/v1",
        f"unexpected runtime base_url: {runtime.get('base_url')!r}",
    )
    require(bool(runtime.get("api_key")), "runtime redirect has no API token")

    ctx = ConfigContext(
        current_provider="custom",
        current_model=HYBRID_MODEL,
        current_base_url="",
        user_providers={},
        custom_providers=[],
    )
    payload = build_models_payload(
        ctx,
        include_unconfigured=True,
        picker_hints=True,
        canonical_order=True,
        max_models=50,
    )
    row = next((r for r in payload["providers"] if r.get("slug") == "cloudflare-native"), None)
    require(row is not None, "cloudflare-native picker row is missing")
    require(row.get("authenticated") is True, f"cloudflare-native row not authenticated: {row!r}")
    require(row.get("source") == "hybrid-local-api", f"unexpected picker source: {row.get('source')!r}")
    require(not row.get("warning"), f"unexpected picker warning: {row.get('warning')!r}")
    require(row.get("is_current") is True, f"cloudflare-native row is not current: {row!r}")
    custom_skeleton = [
        r for r in payload["providers"]
        if r.get("slug") == "custom" and r.get("source") == "canonical" and not r.get("models")
    ]
    require(not custom_skeleton, f"unexpected custom no-key skeleton: {custom_skeleton!r}")

    print("dashboard hybrid guards ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())

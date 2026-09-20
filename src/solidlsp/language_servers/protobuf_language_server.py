"""
Provides a generic adapter for Protobuf language servers implementing LSP.
"""
# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
from typing import Any

from overrides import override

from solidlsp.dependency_provider import LanguageServerDependencyProviderBaseCommand
from solidlsp.ls import SolidLanguageServer
from solidlsp.ls_config import ExternalLanguageServerId, FilenameMatcher, LanguageServerConfig, LanguageServerRegistry
from solidlsp.settings import SolidLSPSettings

log = logging.getLogger(__name__)

PROTOBUF_LANGUAGE_SERVER_KEY = "protobuf"
PROTOBUF_EXTENSIONS = (
    ".proto",
    ".textproto",
    ".pbtxt",
    ".prototxt",
    ".txtpb",
    ".textpb",
    ".pb.txt",
)
Settings = dict[str, Any] | SolidLSPSettings.CustomLSSettings


def _get_dict_setting(settings: Settings, key: str) -> dict[str, Any]:
    value = settings.get(key, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        log.warning("The '%s' setting should be a mapping. Ignoring the provided value: %s", key, value)
        return {}
    return value


class ProtobufLanguageServer(SolidLanguageServer):
    """Adapt any stdio-based Protobuf language server to Serena's LSP interface."""

    def __init__(self, config: LanguageServerConfig, repository_root_path: str, solidlsp_settings: SolidLSPSettings):
        super().__init__(config, repository_root_path, None, "proto", solidlsp_settings)
        self.language_id = str(self._custom_settings.get("language_id", "proto"))
        self._textproto_language_id = str(self._custom_settings.get("textproto_language_id", self.language_id))

    def _create_dependency_provider(self) -> LanguageServerDependencyProviderBaseCommand:
        return self.DependencyProvider(self._custom_settings, self._ls_resources_dir)

    class DependencyProvider(LanguageServerDependencyProviderBaseCommand):
        """Build the configured command for any Protobuf LSP implementation."""

        def _create_default_base_command(self) -> list[str]:
            raise FileNotFoundError(
                "No Protobuf language server command configured. Set "
                "ls_specific_settings.protobuf.ls_base_cmd to the language server command."
            )

        def _create_launch_command_from_base_command(self, base_command: list[str]) -> list[str]:
            return base_command

    @override
    def _get_language_id_for_file(self, relative_file_path: str) -> str:
        if relative_file_path.lower().endswith(PROTOBUF_EXTENSIONS[1:]):
            return self._textproto_language_id
        return self.language_id

    @override
    def _create_base_initialize_params(self) -> dict[str, Any]:
        return {
            "capabilities": {
                "textDocument": {
                    "synchronization": {"didSave": True, "dynamicRegistration": True},
                    "completion": {"dynamicRegistration": True, "completionItem": {"snippetSupport": True}},
                    "definition": {"dynamicRegistration": True},
                    "references": {"dynamicRegistration": True},
                    "documentSymbol": {
                        "dynamicRegistration": True,
                        "hierarchicalDocumentSymbolSupport": True,
                        "symbolKind": {"valueSet": list(range(1, 27))},
                    },
                    "hover": {"dynamicRegistration": True, "contentFormat": ["markdown", "plaintext"]},
                    "rename": {"dynamicRegistration": True, "prepareSupport": True},
                    "codeAction": {"dynamicRegistration": True},
                    "publishDiagnostics": {"relatedInformation": True},
                },
                "workspace": {
                    "workspaceFolders": True,
                    "configuration": True,
                    "didChangeConfiguration": {"dynamicRegistration": True},
                    "symbol": {"dynamicRegistration": True},
                },
            },
            "initializationOptions": _get_dict_setting(self._custom_settings, "initialization_options"),
        }

    def _start_server(self) -> None:
        def do_nothing(_params: Any) -> None:
            return

        def handle_workspace_configuration(params: dict[str, Any]) -> list[dict[str, Any]]:
            configuration = _get_dict_setting(self._custom_settings, "workspace_configuration")
            section = self._custom_settings.get("workspace_configuration_section")
            items = params.get("items", []) if isinstance(params, dict) else []
            result: list[dict[str, Any]] = []
            for item in items:
                requested_section = item.get("section") if isinstance(item, dict) else None
                if section is None or requested_section in (None, section):
                    result.append(configuration)
                else:
                    result.append({})
            return result

        def window_log_message(message: dict[str, Any]) -> None:
            log.info("Protobuf LSP: window/logMessage: %s", message)

        self.server.on_request("client/registerCapability", do_nothing)
        self.server.on_request("workspace/configuration", handle_workspace_configuration)
        self.server.on_notification("window/logMessage", window_log_message)
        self.server.on_notification("window/showMessage", window_log_message)
        self.server.on_notification("$/logTrace", do_nothing)
        self.server.on_notification("$/progress", do_nothing)
        self.server.on_notification("textDocument/publishDiagnostics", do_nothing)

        log.info("Starting Protobuf language server")
        self.server.start()
        self.server.send.initialize(self._create_initialize_params())
        self.server.notify.initialized({})

        requests = self._custom_settings.get("initialization_requests", [])
        if not isinstance(requests, list):
            log.warning("The 'initialization_requests' setting should be a list. Ignoring the provided value: %s", requests)
            return
        for request in requests:
            if not isinstance(request, dict) or not isinstance(request.get("method"), str):
                log.warning("Ignoring invalid Protobuf LSP initialization request: %s", request)
                continue
            params = request.get("params")
            if params is not None and not isinstance(params, dict):
                log.warning("Ignoring initialization request with invalid params: %s", request)
                continue
            self.server.send_request(request["method"], params)


def register_protobuf() -> None:
    """Register the generic Protobuf language-server adapter with SolidLSP."""
    LanguageServerRegistry.get_instance().register(
        ExternalLanguageServerId(
            key=PROTOBUF_LANGUAGE_SERVER_KEY,
            matcher=FilenameMatcher(*PROTOBUF_EXTENSIONS, case_sensitive=False),
            implementation=ProtobufLanguageServer,
        )
    )

# SPDX-License-Identifier: MIT

from pathlib import Path

import pytest

from solidlsp.language_servers.protobuf_language_server import (
    PROTOBUF_EXTENSIONS,
    ProtobufLanguageServer,
)
from solidlsp.ls_config import FilenameMatcher


def test_protobuf_extensions_match_proto_and_textproto_files() -> None:
    matcher = FilenameMatcher(*PROTOBUF_EXTENSIONS, case_sensitive=False)

    assert matcher.is_relevant_filename("schema.proto")
    assert matcher.is_relevant_filename("message.textproto")
    assert matcher.is_relevant_filename("message.pb.txt")
    assert matcher.is_relevant_filename("SCHEMA.PROTO")
    assert not matcher.is_relevant_filename("README.txt")


def test_language_id_is_configurable(tmp_path: Path) -> None:
    server = object.__new__(ProtobufLanguageServer)
    server.language_id = "protobuf"
    server._textproto_language_id = "textproto"

    assert server._get_language_id_for_file("schema.proto") == "protobuf"
    assert server._get_language_id_for_file("fixtures/message.textproto") == "textproto"


def test_dependency_provider_uses_configured_command(tmp_path: Path) -> None:
    provider = ProtobufLanguageServer.DependencyProvider(
        {"ls_base_cmd": ["custom-protobuf-lsp", "--stdio"]},
        str(tmp_path),
    )

    assert provider.create_launch_command() == ["custom-protobuf-lsp", "--stdio"]


def test_dependency_provider_requires_a_command(tmp_path: Path) -> None:
    provider = ProtobufLanguageServer.DependencyProvider({}, str(tmp_path))

    with pytest.raises(FileNotFoundError, match="ls_base_cmd"):
        provider.create_launch_command()

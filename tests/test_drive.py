"""Tests for Google Drive, Docs, and Sheets service methods."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from gsuite_cli.services.docs_sheets import (
    append_sheet,
    read_doc_as_markdown,
    read_sheet,
)
from gsuite_cli.services.drive import search_files


def test_search_drive_files() -> None:
    mock_service = MagicMock()
    mock_service.files().list().execute.return_value = {
        "files": [
            {
                "id": "file1",
                "name": "Project Roadmap.docx",
                "mimeType": "application/vnd.google-apps.document",
                "modifiedTime": "2026-10-11T10:00:00Z",
                "size": "1048576",
            }
        ]
    }

    with patch("gsuite_cli.services.drive._get_drive_service", return_value=mock_service):
        results = search_files("test@example.com", query="Roadmap", limit=5)
        assert len(results) == 1
        assert results[0]["id"] == "file1"
        assert results[0]["name"] == "Project Roadmap.docx"


def test_read_doc_as_markdown() -> None:
    mock_service = MagicMock()
    mock_service.documents().get().execute.return_value = {
        "title": "Architecture Overview",
        "revisionId": "rev1",
        "body": {
            "content": [
                {
                    "paragraph": {
                        "paragraphStyle": {"namedStyleType": "HEADING_1"},
                        "elements": [{"textRun": {"content": "System Architecture\n"}}],
                    }
                },
                {
                    "paragraph": {
                        "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                        "elements": [
                            {
                                "textRun": {
                                    "content": "This is a bold text",
                                    "textStyle": {"bold": True},
                                }
                            },
                            {"textRun": {"content": " and regular text.\n"}},
                        ],
                    }
                },
                {
                    "paragraph": {
                        "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                        "bullet": {"listId": "list1"},
                        "elements": [{"textRun": {"content": "Bullet point item\n"}}],
                    }
                },
            ]
        },
    }

    with patch("gsuite_cli.services.docs_sheets._get_docs_service", return_value=mock_service):
        res = read_doc_as_markdown("test@example.com", "doc123")
        assert res["id"] == "doc123"
        assert res["title"] == "Architecture Overview"
        md = res["markdown"]
        assert "# System Architecture" in md
        assert "**This is a bold text**" in md
        assert "* Bullet point item" in md


def test_read_sheet() -> None:
    mock_service = MagicMock()
    mock_service.spreadsheets().values().get().execute.return_value = {
        "range": "Sheet1!A1:B2",
        "values": [
            ["Metric", "Value"],
            ["CPU", "85%"],
        ],
    }

    with patch("gsuite_cli.services.docs_sheets._get_sheets_service", return_value=mock_service):
        res = read_sheet("test@example.com", "sheet123", range_name="Sheet1!A1:B2")
        assert res["spreadsheetId"] == "sheet123"
        assert res["rowCount"] == 2
        assert res["values"][0] == ["Metric", "Value"]
        assert res["values"][1] == ["CPU", "85%"]


def test_append_sheet() -> None:
    mock_service = MagicMock()
    mock_service.spreadsheets().values().append().execute.return_value = {
        "updates": {
            "updatedRange": "Sheet1!A3:B3",
            "updatedRows": 1,
            "updatedColumns": 2,
            "updatedCells": 2,
        }
    }

    with patch("gsuite_cli.services.docs_sheets._get_sheets_service", return_value=mock_service):
        res = append_sheet(
            "test@example.com",
            spreadsheet_id="sheet123",
            range_name="Sheet1!A1",
            values=[["Memory", "64GB"]],
        )
        assert res["status"] == "success"
        assert res["action"] == "appended"
        assert res["updatedRange"] == "Sheet1!A3:B3"
        assert res["updatedRows"] == 1

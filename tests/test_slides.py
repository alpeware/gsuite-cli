"""Tests for Google Slides service methods."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from gsuite_cli.services.slides import (
    create_presentation,
    read_presentation_text,
)


def test_create_presentation() -> None:
    mock_service = MagicMock()
    mock_service.presentations().create().execute.return_value = {
        "presentationId": "pres_123",
        "title": "Quarterly Review",
    }

    with patch("gsuite_cli.services.slides._get_slides_service", return_value=mock_service):
        res = create_presentation("test@example.com", title="Quarterly Review")
        assert res["presentationId"] == "pres_123"
        assert res["title"] == "Quarterly Review"


def test_read_presentation_text() -> None:
    mock_service = MagicMock()
    mock_service.presentations().get().execute.return_value = {
        "presentationId": "pres_abc",
        "title": "Agentic Architecture",
        "slides": [
            {
                "objectId": "slide_1",
                "pageElements": [
                    {
                        "shape": {
                            "text": {
                                "textElements": [
                                    {"textRun": {"content": "Executive Summary\n"}}
                                ]
                            }
                        }
                    }
                ],
                "slideProperties": {
                    "notesPage": {
                        "pageElements": [
                            {
                                "shape": {
                                    "text": {
                                        "textElements": [
                                            {"textRun": {"content": "Introduce agenda\n"}}
                                        ]
                                    }
                                }
                            }
                        ]
                    }
                },
            }
        ],
    }

    with patch("gsuite_cli.services.slides._get_slides_service", return_value=mock_service):
        data = read_presentation_text("test@example.com", presentation_id="pres_abc")
        assert data["title"] == "Agentic Architecture"
        assert data["slide_count"] == 1
        slide = data["slides"][0]
        assert "Executive Summary" in slide["content"][0]
        assert slide["speaker_notes"] == "Introduce agenda"

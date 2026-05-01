from __future__ import annotations

import subprocess

from backend.services.campaign_asset_import_service import CampaignAssetImportService


def test_extract_pdf_text_preserves_page_markers(monkeypatch, tmp_path):
    service = CampaignAssetImportService()
    pdf_path = tmp_path / "example.pdf"
    pdf_path.write_bytes(b"%PDF-1.6 test pdf")

    def fake_run(cmd, check, capture_output, text):
        assert cmd[0] == "pdftotext"
        assert "-nopgbrk" not in cmd
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout="Cover page text\fSecond page text\nMore text",
            stderr="",
        )

    monkeypatch.setattr(
        "backend.services.campaign_asset_import_service.subprocess.run",
        fake_run,
    )

    content, non_empty_lines = service._extract_pdf_text(pdf_path)

    assert "[Page 1]" in content
    assert "Cover page text" in content
    assert "[Page 2]" in content
    assert "Second page text" in content
    assert non_empty_lines >= 4

from __future__ import annotations

from pathlib import Path

import pytest

from app.papers import pdf_figures


def test_extract_pdf_figure_to_storage_picks_largest_image(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        pdf_figures.shutil,
        "which",
        lambda command: "/usr/bin/pdfimages" if command == "pdfimages" else None,
    )

    def fake_run_pdfimages(*, pdf_path: Path, output_prefix: Path) -> None:
        assert pdf_path.exists()
        (output_prefix.parent / f"{output_prefix.name}-000.png").write_bytes(b"a" * 2048)
        (output_prefix.parent / f"{output_prefix.name}-001.png").write_bytes(b"b" * 24576)

    monkeypatch.setattr(pdf_figures, "_run_pdfimages", fake_run_pdfimages)

    extracted = pdf_figures.extract_pdf_figure_to_storage(
        pdf_bytes=b"%PDF-1.7 fake",
        paper_key="2603.18762v1",
        output_root=tmp_path,
    )

    assert extracted is not None
    assert extracted.exists()
    assert extracted.parent == tmp_path / "2603.18762v1"
    assert extracted.read_bytes() == b"b" * 24576


def test_build_public_figure_asset_url_uses_api_base() -> None:
    url = pdf_figures.build_public_figure_asset_url(
        relative_path=Path("2603.18762v1") / "figure.png",
        public_api_base="http://127.0.0.1:8000",
    )

    assert url == "http://127.0.0.1:8000/api/v1/reports/paper-assets/2603.18762v1/figure.png"

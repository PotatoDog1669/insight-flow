"""Best-effort PDF figure extraction helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote

import httpx

from app.config import PROJECT_ROOT

DEFAULT_PAPER_FIGURE_ASSET_DIR = PROJECT_ROOT / "output" / "paper_assets" / "_figures"
MIN_PDF_IMAGE_BYTES = 10_000


def sanitize_paper_key(paper_key: str) -> str:
    value = "".join(ch if ch.isalnum() or ch in {".", "_", "-"} else "-" for ch in str(paper_key or "").strip())
    return value.strip("-") or "paper"


def build_public_figure_asset_url(*, relative_path: Path, public_api_base: str) -> str:
    base = str(public_api_base or "").rstrip("/")
    quoted = quote(relative_path.as_posix())
    return f"{base}/api/v1/reports/paper-assets/{quoted}"


def extract_pdf_figure_to_storage(
    *,
    pdf_bytes: bytes,
    paper_key: str,
    output_root: Path | None = None,
    min_size_bytes: int = MIN_PDF_IMAGE_BYTES,
) -> Path | None:
    if not pdf_bytes or shutil.which("pdfimages") is None:
        return None

    root = output_root or DEFAULT_PAPER_FIGURE_ASSET_DIR
    safe_key = sanitize_paper_key(paper_key)
    target_dir = root / safe_key
    target_dir.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(prefix="paper-pdf-figure-") as temp_dir:
        temp_root = Path(temp_dir)
        pdf_path = temp_root / "paper.pdf"
        output_prefix = temp_root / "figure"
        pdf_path.write_bytes(pdf_bytes)
        _run_pdfimages(pdf_path=pdf_path, output_prefix=output_prefix)
        selected = _select_extracted_figure(
            temp_root=temp_root,
            output_prefix=output_prefix,
            min_size_bytes=min_size_bytes,
        )
        if selected is None:
            return None
        target_path = target_dir / f"figure{selected.suffix or '.png'}"
        shutil.copyfile(selected, target_path)
        return target_path


async def extract_pdf_figure_public_url(
    client: httpx.AsyncClient,
    *,
    pdf_url: str,
    paper_key: str,
    public_api_base: str,
    output_root: Path | None = None,
) -> str:
    if not pdf_url or not paper_key or not public_api_base:
        return ""
    try:
        response = await client.get(pdf_url)
        response.raise_for_status()
    except Exception:
        return ""
    content_type = str((response.headers or {}).get("content-type") or "").lower()
    if "pdf" not in content_type and not pdf_url.lower().endswith(".pdf"):
        return ""
    extracted = extract_pdf_figure_to_storage(
        pdf_bytes=bytes(getattr(response, "content", b"") or b""),
        paper_key=paper_key,
        output_root=output_root,
    )
    if extracted is None:
        return ""
    root = output_root or DEFAULT_PAPER_FIGURE_ASSET_DIR
    return build_public_figure_asset_url(relative_path=extracted.relative_to(root), public_api_base=public_api_base)


def _run_pdfimages(*, pdf_path: Path, output_prefix: Path) -> None:
    subprocess.run(
        ["pdfimages", "-png", str(pdf_path), str(output_prefix)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _select_extracted_figure(*, temp_root: Path, output_prefix: Path, min_size_bytes: int) -> Path | None:
    candidates = sorted(path for path in temp_root.glob(f"{output_prefix.name}-*") if path.is_file())
    if not candidates:
        return None
    preferred = [path for path in candidates if path.stat().st_size >= min_size_bytes]
    pool = preferred or candidates
    return max(pool, key=lambda path: path.stat().st_size, default=None)

"""Parse PDF scores into MusicXML using Audiveris OMR."""

import subprocess
import tempfile
import shutil
from pathlib import Path


def check_audiveris_installed() -> bool:
    return shutil.which("audiveris") is not None


def pdf_to_musicxml(pdf_path: str, output_dir: str | None = None) -> Path:
    """Convert a PDF score to MusicXML using Audiveris.

    Falls back to a manual upload prompt if Audiveris is not installed.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="barbershop_")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not check_audiveris_installed():
        raise RuntimeError(
            "Audiveris is not installed. Please install it from "
            "https://github.com/Audiveris/audiveris or provide a MusicXML file directly."
        )

    result = subprocess.run(
        [
            "audiveris",
            "-batch",
            "-export",
            "-output", str(output_dir),
            str(pdf_path),
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Audiveris failed: {result.stderr}")

    mxl_files = list(output_dir.glob("*.mxl")) + list(output_dir.glob("*.musicxml"))
    if not mxl_files:
        raise RuntimeError("Audiveris produced no MusicXML output.")

    return mxl_files[0]


def pdf_to_images(pdf_path: str) -> list:
    """Convert PDF pages to images for preview."""
    try:
        from pdf2image import convert_from_path
        return convert_from_path(pdf_path, dpi=150)
    except Exception:
        return []

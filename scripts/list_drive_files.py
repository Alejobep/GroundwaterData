"""Index the shared Google Drive folder into catalogue/drive_files.csv.

Walks the public Drive folder that mirrors the study-area PDFs (no login;
uses gdown's folder parser) and records one row per file so the per-file
catalogue can link each PDF to its Drive copy:

- drive_path: path inside the shared folder (``study_area_files/odisha/Koraput.pdf``)
- original_filename: basename, the join key against catalogue/files.csv
- drive_file_id, drive_url: Drive identifier and ``https://drive.google.com/file/d/<id>/view``
- mime_type: Drive MIME type (Google Sheets and other non-files are kept, flagged by type)

Usage:
    python scripts/list_drive_files.py [--folder-id ID]
"""

import argparse
import csv
import sys
from pathlib import Path

import requests
from gdown.download_folder import _download_and_parse_google_drive_link

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "catalogue" / "drive_files.csv"
DEFAULT_FOLDER_ID = "1rDVeaKACaz2sBBOeS6_QnoAmjbAh4niK"
COLUMNS = ("drive_path", "original_filename", "drive_file_id", "drive_url", "mime_type")


def walk(node, parents: list[str], rows: list[dict[str, str]]) -> None:
    if node.is_folder():
        for child in node.children:
            walk(child, parents + [node.name], rows)
        return
    # Drop the shared root folder's own name so paths are stable if it is renamed.
    path = "/".join(parents[1:] + [node.name])
    rows.append({
        "drive_path": path,
        "original_filename": node.name,
        "drive_file_id": node.id,
        "drive_url": f"https://drive.google.com/file/d/{node.id}/view",
        "mime_type": node.type,
    })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--folder-id", default=DEFAULT_FOLDER_ID)
    args = parser.parse_args()

    root = _download_and_parse_google_drive_link(
        sess=requests.Session(), folder_id=args.folder_id, quiet=True, verify=True, timeout=120
    )
    rows: list[dict[str, str]] = []
    walk(root, [], rows)
    rows.sort(key=lambda row: row["drive_path"])

    names = [row["original_filename"] for row in rows]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        sys.exit("same filename appears more than once on Drive, cannot join by name: " + ", ".join(duplicates))

    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} Drive items -> {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

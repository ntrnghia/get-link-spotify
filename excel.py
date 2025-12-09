"""
Excel export functionality for ZingMP3-Spotify results.
"""

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from config import EXCEL_COLUMN_WIDTHS, EXCEL_HEADERS


def write_excel(results: list[dict], output_file: str) -> None:
    """Write results to Excel file with formatting.

    12 columns: ZingMP3 (5) + Spotify (6) + Match % (1)

    Args:
        results: List of song result dicts
        output_file: Path to output Excel file
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "ZingMP3 Chart"

    # Header styling
    zing_fill = PatternFill(
        start_color="4472C4", end_color="4472C4", fill_type="solid"
    )  # Blue for ZingMP3
    spotify_fill = PatternFill(
        start_color="1DB954", end_color="1DB954", fill_type="solid"
    )  # Green for Spotify
    match_fill = PatternFill(
        start_color="FFC000", end_color="FFC000", fill_type="solid"
    )  # Orange for Match
    header_font = Font(bold=True, color="FFFFFF")

    for col, header in enumerate(EXCEL_HEADERS, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
        # Color based on column group
        if col <= 5:
            cell.fill = zing_fill
        elif col <= 11:
            cell.fill = spotify_fill
        else:
            cell.fill = match_fill

    # Data rows
    for row_idx, r in enumerate(results, 2):
        # ZingMP3 columns
        ws.cell(row=row_idx, column=1, value=r.get("rank", ""))
        ws.cell(row=row_idx, column=2, value=r.get("song_name", ""))
        ws.cell(row=row_idx, column=3, value=r.get("artists", ""))
        ws.cell(row=row_idx, column=4, value=r.get("duration", ""))
        ws.cell(row=row_idx, column=5, value=r.get("zing_url", ""))

        # Spotify columns
        ws.cell(row=row_idx, column=6, value=r.get("spotify_name", ""))
        ws.cell(row=row_idx, column=7, value=r.get("spotify_artist", ""))
        ws.cell(row=row_idx, column=8, value=r.get("spotify_album", ""))
        ws.cell(row=row_idx, column=9, value=r.get("spotify_duration", ""))
        ws.cell(row=row_idx, column=10, value=r.get("spotify_url", ""))
        ws.cell(row=row_idx, column=11, value=r.get("popularity", 0))

        # Match column (as percentage)
        match_score = r.get("match_score", 0)
        ws.cell(
            row=row_idx,
            column=12,
            value=f"{match_score * 100:.0f}%" if match_score else "",
        )

    # Set column widths
    for col, width in enumerate(EXCEL_COLUMN_WIDTHS, 1):
        ws.column_dimensions[get_column_letter(col)].width = width

    # Freeze header row
    ws.freeze_panes = "A2"

    wb.save(output_file)

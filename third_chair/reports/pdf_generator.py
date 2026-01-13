"""PDF report generation with Bates numbering.

Uses reportlab to create PDF documents with:
- Bates numbering on each page
- Professional formatting
- Tables and structured content
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)
from reportlab.pdfgen import canvas

from ..models import Case


class BatesNumberedCanvas(canvas.Canvas):
    """Canvas subclass that adds Bates numbers to each page."""

    def __init__(self, *args, bates_prefix: str = "DEF", start_number: int = 1, **kwargs):
        """
        Initialize with Bates numbering settings.

        Args:
            bates_prefix: Prefix for Bates numbers (e.g., "DEF", "PLT")
            start_number: Starting Bates number
        """
        super().__init__(*args, **kwargs)
        self.bates_prefix = bates_prefix
        self.start_number = start_number
        self._page_number = 0

    def showPage(self):
        """Called at the end of each page."""
        self._add_bates_number()
        self._page_number += 1
        super().showPage()

    def _add_bates_number(self):
        """Add Bates number to current page."""
        bates_num = self.start_number + self._page_number
        bates_str = f"{self.bates_prefix}{bates_num:06d}"

        # Add at bottom right of page
        self.saveState()
        self.setFont("Helvetica", 9)
        self.drawRightString(
            letter[0] - 0.5 * inch,
            0.5 * inch,
            bates_str,
        )
        self.restoreState()

    def save(self):
        """Save and return the final Bates number."""
        super().save()
        return self.start_number + self._page_number


class PdfGenerator:
    """Generator for PDF reports with Bates numbering."""

    def __init__(
        self,
        bates_prefix: str = "DEF",
        bates_start: int = 1,
    ):
        """
        Initialize PDF generator.

        Args:
            bates_prefix: Prefix for Bates numbers
            bates_start: Starting Bates number
        """
        self.bates_prefix = bates_prefix
        self.bates_start = bates_start
        self.styles = getSampleStyleSheet()
        self._setup_styles()
        self.elements = []

    def _setup_styles(self) -> None:
        """Configure custom styles."""
        # Title style
        self.styles.add(ParagraphStyle(
            name="ReportTitle",
            parent=self.styles["Heading1"],
            fontSize=24,
            spaceAfter=30,
            alignment=1,  # Center
        ))

        # Subtitle style
        self.styles.add(ParagraphStyle(
            name="ReportSubtitle",
            parent=self.styles["Normal"],
            fontSize=14,
            spaceAfter=12,
            alignment=1,  # Center
        ))

        # Section header
        self.styles.add(ParagraphStyle(
            name="SectionHeader",
            parent=self.styles["Heading2"],
            fontSize=14,
            spaceBefore=20,
            spaceAfter=10,
            textColor=colors.darkblue,
        ))

        # Alert style
        self.styles.add(ParagraphStyle(
            name="Alert",
            parent=self.styles["Normal"],
            textColor=colors.red,
            fontName="Helvetica-Bold",
        ))

    def add_title(self, title: str, subtitle: Optional[str] = None) -> None:
        """Add a title page."""
        self.elements.append(Spacer(1, 2 * inch))
        self.elements.append(Paragraph(title, self.styles["ReportTitle"]))

        if subtitle:
            self.elements.append(Paragraph(subtitle, self.styles["ReportSubtitle"]))

        self.elements.append(Spacer(1, inch))

    def add_case_info(self, case: Case) -> None:
        """Add case information block."""
        info_lines = [
            f"<b>Case ID:</b> {case.case_id}",
        ]
        if case.court_case:
            info_lines.append(f"<b>Court Case:</b> {case.court_case}")
        if case.agency:
            info_lines.append(f"<b>Agency:</b> {case.agency}")
        if case.incident_date:
            info_lines.append(f"<b>Incident Date:</b> {case.incident_date.strftime('%B %d, %Y')}")

        info_lines.append(f"<b>Report Generated:</b> {datetime.now().strftime('%B %d, %Y')}")

        for line in info_lines:
            self.elements.append(Paragraph(line, self.styles["Normal"]))
            self.elements.append(Spacer(1, 6))

    def add_heading(self, text: str, level: int = 1) -> None:
        """Add a section heading."""
        if level == 1:
            style = self.styles["SectionHeader"]
        else:
            style = self.styles["Heading3"]

        self.elements.append(Paragraph(text, style))

    def add_paragraph(self, text: str, style: Optional[str] = None) -> None:
        """Add a paragraph."""
        style = self.styles[style or "Normal"]
        self.elements.append(Paragraph(text, style))
        self.elements.append(Spacer(1, 6))

    def add_bullet_list(self, items: list[str]) -> None:
        """Add a bulleted list."""
        for item in items:
            self.elements.append(Paragraph(f"• {item}", self.styles["Normal"]))
            self.elements.append(Spacer(1, 3))

    def add_table(
        self,
        headers: list[str],
        rows: list[list[str]],
        col_widths: Optional[list[float]] = None,
    ) -> None:
        """
        Add a table.

        Args:
            headers: Column headers
            rows: Table data
            col_widths: Column widths in inches
        """
        # Convert widths to points
        if col_widths:
            col_widths = [w * inch for w in col_widths]

        # Build table data
        data = [headers] + rows

        table = Table(data, colWidths=col_widths)
        table.setStyle(TableStyle([
            # Header styling
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("TOPPADDING", (0, 0), (-1, 0), 8),

            # Data styling
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
            ("TOPPADDING", (0, 1), (-1, -1), 4),

            # Grid
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),

            # Alternating row colors
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.95, 0.95)]),

            # Alignment
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))

        self.elements.append(table)
        self.elements.append(Spacer(1, 12))

    def add_evidence_table(self, case: Case) -> None:
        """Add evidence inventory table."""
        headers = ["#", "Filename", "Type", "Size", "Status"]
        rows = []

        for i, evidence in enumerate(case.evidence_items, 1):
            # Format size
            size = evidence.size_bytes
            if size < 1024 * 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size / (1024 * 1024):.1f} MB"

            # Status
            status_parts = []
            if evidence.transcript:
                status_parts.append("T")
            if evidence.summary:
                status_parts.append("S")
            status_str = ", ".join(status_parts) if status_parts else "-"

            # Truncate filename
            fname = evidence.filename
            if len(fname) > 35:
                fname = fname[:32] + "..."

            rows.append([str(i), fname, evidence.file_type.value, size_str, status_str])

        self.add_table(headers, rows, col_widths=[0.4, 3.0, 0.8, 0.8, 0.6])

    def add_witness_table(self, case: Case) -> None:
        """Add witness list table."""
        if not case.witnesses.witnesses:
            self.add_paragraph("No witnesses identified.")
            return

        headers = ["Name", "Role", "Speaker IDs", "Verified"]
        rows = []

        for witness in case.witnesses.witnesses:
            speaker_ids = ", ".join(witness.speaker_ids[:2])
            if len(witness.speaker_ids) > 2:
                speaker_ids += "..."

            rows.append([
                witness.display_name,
                witness.role.value,
                speaker_ids,
                "Yes" if witness.verified else "No",
            ])

        self.add_table(headers, rows, col_widths=[2.0, 1.2, 1.5, 0.8])

    def add_timeline(self, case: Case) -> None:
        """Add timeline section."""
        if not case.timeline:
            self.add_paragraph("No timeline events.")
            return

        current_date = None

        for event in case.timeline:
            event_date = event.timestamp.date()

            # Date header
            if event_date != current_date:
                current_date = event_date
                self.add_paragraph(
                    f"<b>{event_date.strftime('%B %d, %Y')}</b>",
                )

            # Event
            time_str = event.timestamp.strftime("%H:%M:%S")
            importance = event.metadata.get("importance", "normal") if event.metadata else "normal"

            prefix = ""
            if importance == "critical":
                prefix = "[!!!] "
            elif importance == "high":
                prefix = "[!] "

            self.elements.append(Paragraph(
                f"&nbsp;&nbsp;{time_str}&nbsp;&nbsp;{prefix}{event.description}",
                self.styles["Normal"],
            ))

    def add_key_statements(self, case: Case) -> None:
        """Add key statements section."""
        key_statements = []

        for evidence in case.evidence_items:
            if not evidence.transcript:
                continue

            for segment in evidence.transcript.key_statements:
                key_statements.append({
                    "evidence": evidence.filename,
                    "speaker": segment.speaker,
                    "text": segment.text,
                    "translation": segment.translation,
                })

        if not key_statements:
            self.add_paragraph("No key statements flagged.")
            return

        for stmt in key_statements:
            text = f"<b>[{stmt['evidence'][:30]}]</b> "
            if stmt["speaker"]:
                text += f"<i>{stmt['speaker']}:</i> "
            text += stmt["text"]

            self.add_paragraph(text)

            if stmt["translation"]:
                self.add_paragraph(
                    f"&nbsp;&nbsp;&nbsp;&nbsp;<i>[Translation: {stmt['translation']}]</i>",
                )

    def add_page_break(self) -> None:
        """Add a page break."""
        self.elements.append(PageBreak())

    def save(self, path: Path) -> int:
        """
        Save the PDF to a file.

        Args:
            path: Output file path

        Returns:
            Final Bates number (for continuation)
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Create document with custom canvas
        def make_canvas(*args, **kwargs):
            return BatesNumberedCanvas(
                *args,
                bates_prefix=self.bates_prefix,
                start_number=self.bates_start,
                **kwargs,
            )

        doc = SimpleDocTemplate(
            str(path),
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        # Build with custom canvas
        doc.build(self.elements, canvasmaker=make_canvas)

        # Return approximate final Bates number
        # (actual count determined during build)
        return self.bates_start + len(self.elements) // 20  # Rough estimate


def generate_case_pdf(
    case: Case,
    output_path: Path,
    bates_prefix: str = "DEF",
    bates_start: int = 1,
) -> tuple[Path, int]:
    """
    Generate a complete case report in PDF format with Bates numbering.

    Args:
        case: Case to report on
        output_path: Where to save the PDF
        bates_prefix: Bates number prefix
        bates_start: Starting Bates number

    Returns:
        Tuple of (path to generated PDF, final Bates number)
    """
    gen = PdfGenerator(bates_prefix=bates_prefix, bates_start=bates_start)

    # Title
    gen.add_title(
        "CASE ANALYSIS REPORT",
        f"Case ID: {case.case_id}",
    )

    gen.add_case_info(case)
    gen.add_page_break()

    # Executive summary
    gen.add_heading("Executive Summary")
    if case.summary:
        gen.add_paragraph(case.summary)
    else:
        gen.add_paragraph("No summary available.")

    # Key findings
    if case.metadata and case.metadata.get("key_findings"):
        gen.add_heading("Key Findings", level=2)
        gen.add_bullet_list(case.metadata["key_findings"])

    gen.add_page_break()

    # Alerts
    if case.metadata:
        threats = case.metadata.get("threats_identified", 0)
        violence = case.metadata.get("violence_indicators", 0)

        if threats > 0 or violence > 0:
            gen.add_heading("Alerts")
            if threats > 0:
                gen.add_paragraph(f"Threat keywords detected: {threats}", style="Alert")
            if violence > 0:
                gen.add_paragraph(f"Violence indicators: {violence}", style="Alert")

    # Evidence inventory
    gen.add_heading("Evidence Inventory")
    gen.add_evidence_table(case)
    gen.add_page_break()

    # Witnesses
    gen.add_heading("Witnesses")
    gen.add_witness_table(case)
    gen.add_page_break()

    # Timeline
    gen.add_heading("Timeline of Events")
    gen.add_timeline(case)
    gen.add_page_break()

    # Key statements
    gen.add_heading("Key Statements")
    gen.add_key_statements(case)
    gen.add_page_break()

    # Items needing review
    if case.metadata and case.metadata.get("items_needing_review"):
        gen.add_heading("Items Requiring Review")
        gen.add_bullet_list(case.metadata["items_needing_review"])

    # Save and get final Bates number
    final_bates = gen.save(output_path)

    return output_path, final_bates

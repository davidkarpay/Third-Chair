"""Third Chair CLI - Legal Discovery Processing Tool."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="third-chair",
    help="Legal discovery processing tool for Axon evidence packages.",
    no_args_is_help=True,
)

console = Console()


@app.command()
def process(
    zip_file: Path = typer.Argument(..., help="Path to Axon ZIP file"),
    output: Path = typer.Option(
        None,
        "--output", "-o",
        help="Output directory (default: based on ZIP filename)",
    ),
    court_case: Optional[str] = typer.Option(
        None,
        "--court-case", "-c",
        help="Court case number (e.g., 50-2025-CF-001234)",
    ),
    skip_transcription: bool = typer.Option(
        False,
        "--skip-transcription",
        help="Skip audio/video transcription",
    ),
    skip_translation: bool = typer.Option(
        False,
        "--skip-translation",
        help="Skip Spanish translation",
    ),
    skip_summarization: bool = typer.Option(
        False,
        "--skip-summarization",
        help="Skip AI summarization",
    ),
    no_diarization: bool = typer.Option(
        False,
        "--no-diarization",
        help="Disable speaker diarization",
    ),
):
    """
    Process an Axon evidence package.

    This is the main command that runs the full pipeline:
    1. Extract and classify files
    2. Transcribe audio/video
    3. Detect language and translate Spanish
    4. Generate AI summaries and timeline
    5. Generate reports
    """
    from ..ingest import ingest_axon_package
    from ..transcription import transcribe_case
    from ..translation import translate_case
    from ..summarization import summarize_case_evidence

    # Validate input
    if not zip_file.exists():
        console.print(f"[red]Error: File not found: {zip_file}[/red]")
        raise typer.Exit(1)

    # Set output directory
    if output is None:
        output = Path.cwd() / zip_file.stem

    console.print(f"\n[bold]Third Chair - Legal Discovery Processor[/bold]\n")
    console.print(f"Input: {zip_file}")
    console.print(f"Output: {output}\n")

    # Step 1: Ingest
    console.print("[bold]Step 1: Ingesting evidence package...[/bold]")
    case = ingest_axon_package(
        zip_path=zip_file,
        output_dir=output,
        court_case=court_case,
    )

    console.print(f"  Case ID: {case.case_id}")
    console.print(f"  Evidence items: {case.evidence_count}")
    console.print(f"  Media files: {case.media_count}")

    # Step 2: Transcription
    if not skip_transcription and case.media_count > 0:
        console.print("\n[bold]Step 2: Transcribing media files...[/bold]")
        case = transcribe_case(
            case=case,
            enable_diarization=not no_diarization,
            show_progress=True,
        )

    # Step 3: Translation
    if not skip_translation:
        console.print("\n[bold]Step 3: Translating Spanish content...[/bold]")
        case = translate_case(case=case, show_progress=True)

    # Step 4: Summarization
    if not skip_summarization:
        console.print("\n[bold]Step 4: Generating AI summaries...[/bold]")
        case = summarize_case_evidence(case=case, show_progress=True)

    # Step 5: Reports
    console.print("\n[bold]Step 5: Generating reports...[/bold]")
    from ..reports import generate_attorney_report, ReportConfig
    report_config = ReportConfig(format="docx")
    report_result = generate_attorney_report(
        case=case,
        output_dir=output,
        config=report_config,
        show_progress=True,
    )

    # Summary
    console.print("\n[bold green]Processing complete![/bold green]")
    console.print(f"  Processed: {case.processed_count}/{case.evidence_count} items")
    if case.error_count > 0:
        console.print(f"  [yellow]Errors: {case.error_count}[/yellow]")

    console.print(f"\nOutput saved to: {output}")


@app.command()
def ingest(
    zip_file: Path = typer.Argument(..., help="Path to Axon ZIP file"),
    output: Path = typer.Option(
        None,
        "--output", "-o",
        help="Output directory",
    ),
    court_case: Optional[str] = typer.Option(
        None,
        "--court-case", "-c",
        help="Court case number",
    ),
):
    """
    Extract and classify an Axon evidence package.

    This performs only the ingestion step without transcription.
    """
    from ..ingest import ingest_axon_package, get_file_stats

    if not zip_file.exists():
        console.print(f"[red]Error: File not found: {zip_file}[/red]")
        raise typer.Exit(1)

    if output is None:
        output = Path.cwd() / zip_file.stem

    console.print(f"Ingesting: {zip_file}")

    case = ingest_axon_package(
        zip_path=zip_file,
        output_dir=output,
        court_case=court_case,
    )

    # Show stats
    stats = get_file_stats(case)

    console.print(f"\n[bold]Case: {case.case_id}[/bold]")
    console.print(f"Total files: {stats['total_files']}")
    console.print(f"Total size: {stats['total_size_mb']:.1f} MB")

    # File type breakdown
    table = Table(title="Files by Type")
    table.add_column("Type", style="cyan")
    table.add_column("Count", justify="right")

    for file_type, count in sorted(stats["by_file_type"].items()):
        table.add_row(file_type, str(count))

    console.print(table)
    console.print(f"\nCase saved to: {output / 'case.json'}")


@app.command()
def transcribe(
    case_dir: Path = typer.Argument(..., help="Case directory (containing case.json)"),
    whisper_model: str = typer.Option(
        "medium",
        "--whisper-model", "-m",
        help="Whisper model size (tiny, base, small, medium, large)",
    ),
    no_diarization: bool = typer.Option(
        False,
        "--no-diarization",
        help="Disable speaker diarization",
    ),
):
    """
    Transcribe audio/video files in a case.

    Requires a case directory created by the 'ingest' command.
    """
    from ..models import Case
    from ..transcription import transcribe_case
    from ..config.settings import get_settings

    case_file = case_dir / "case.json"
    if not case_file.exists():
        console.print(f"[red]Error: case.json not found in {case_dir}[/red]")
        raise typer.Exit(1)

    # Update Whisper model setting
    settings = get_settings()
    settings.whisper.model_size = whisper_model

    case = Case.load(case_file)
    console.print(f"Transcribing case: {case.case_id}")
    console.print(f"Media files: {case.media_count}")

    case = transcribe_case(
        case=case,
        enable_diarization=not no_diarization,
        show_progress=True,
    )

    console.print(f"\n[green]Transcription complete![/green]")
    console.print(f"Processed: {case.processed_count} files")


@app.command()
def translate(
    case_dir: Path = typer.Argument(..., help="Case directory"),
    ollama_model: str = typer.Option(
        "aya-expanse:8b",
        "--ollama-model",
        help="Ollama model for translation",
    ),
):
    """
    Translate Spanish content in transcripts.

    Requires Ollama to be running locally.
    """
    from ..models import Case
    from ..translation import translate_case, check_ollama_available
    from ..config.settings import get_settings

    case_file = case_dir / "case.json"
    if not case_file.exists():
        console.print(f"[red]Error: case.json not found in {case_dir}[/red]")
        raise typer.Exit(1)

    if not check_ollama_available():
        console.print("[red]Error: Ollama not available. Please start Ollama first.[/red]")
        raise typer.Exit(1)

    settings = get_settings()
    settings.ollama.translation_model = ollama_model

    case = Case.load(case_file)
    console.print(f"Translating case: {case.case_id}")

    case = translate_case(case=case, show_progress=True)

    console.print(f"\n[green]Translation complete![/green]")


@app.command()
def info(
    zip_file: Path = typer.Argument(..., help="Path to Axon ZIP file"),
):
    """
    Show information about an Axon ZIP file without extracting.
    """
    from ..ingest import list_zip_contents

    if not zip_file.exists():
        console.print(f"[red]Error: File not found: {zip_file}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]ZIP Contents: {zip_file.name}[/bold]\n")

    contents = list_zip_contents(zip_file)

    # Group by extension
    by_extension: dict[str, list] = {}
    total_size = 0

    for item in contents:
        ext = Path(item["filename"]).suffix.lower() or "(no extension)"
        if ext not in by_extension:
            by_extension[ext] = []
        by_extension[ext].append(item)
        total_size += item["size_bytes"]

    table = Table(title=f"Summary ({len(contents)} files, {total_size / (1024*1024):.1f} MB)")
    table.add_column("Extension", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Size (MB)", justify="right")

    for ext in sorted(by_extension.keys()):
        items = by_extension[ext]
        ext_size = sum(i["size_bytes"] for i in items) / (1024 * 1024)
        table.add_row(ext, str(len(items)), f"{ext_size:.1f}")

    console.print(table)


@app.command()
def status(
    case_dir: Path = typer.Argument(..., help="Case directory"),
):
    """
    Show processing status of a case.
    """
    from ..models import Case

    case_file = case_dir / "case.json"
    if not case_file.exists():
        console.print(f"[red]Error: case.json not found in {case_dir}[/red]")
        raise typer.Exit(1)

    case = Case.load(case_file)

    console.print(f"\n[bold]Case: {case.case_id}[/bold]")
    if case.court_case:
        console.print(f"Court Case: {case.court_case}")

    console.print(f"\nEvidence Items: {case.evidence_count}")
    console.print(f"  Media files: {case.media_count}")
    console.print(f"  Processed: {case.processed_count}")
    console.print(f"  Pending: {case.pending_count}")
    if case.error_count > 0:
        console.print(f"  [yellow]Errors: {case.error_count}[/yellow]")

    if case.media_count > 0:
        console.print(f"\nTotal media duration: {case.total_duration_formatted}")

    console.print(f"Witnesses: {len(case.witnesses.witnesses)}")


@app.command()
def witnesses(
    case_dir: Path = typer.Argument(..., help="Case directory"),
    import_file: Optional[Path] = typer.Option(
        None,
        "--import", "-i",
        help="Import witness list from file (PDF, DOCX, XLSX, TXT)",
    ),
    list_all: bool = typer.Option(
        False,
        "--list", "-l",
        help="List all witnesses",
    ),
    rename: Optional[str] = typer.Option(
        None,
        "--rename", "-r",
        help="Rename a speaker (format: SPEAKER_1=John Doe)",
    ),
    suggest: bool = typer.Option(
        False,
        "--suggest",
        help="Suggest names for unnamed speakers",
    ),
):
    """
    Manage witnesses in a case.

    Import witness lists, rename speakers, and view witness information.
    """
    from ..models import Case
    from ..witnesses import (
        process_witnesses,
        rename_speaker,
        get_unnamed_speakers,
        suggest_speaker_names,
    )

    case_file = case_dir / "case.json"
    if not case_file.exists():
        console.print(f"[red]Error: case.json not found in {case_dir}[/red]")
        raise typer.Exit(1)

    case = Case.load(case_file)

    # Handle rename
    if rename:
        if "=" not in rename:
            console.print("[red]Error: Use format SPEAKER_1=John Doe[/red]")
            raise typer.Exit(1)

        speaker_id, name = rename.split("=", 1)
        speaker_id = speaker_id.strip()
        name = name.strip()

        if rename_speaker(case, speaker_id, name):
            console.print(f"[green]Renamed {speaker_id} to {name}[/green]")
        else:
            console.print(f"[yellow]Speaker {speaker_id} not found[/yellow]")
        return

    # Handle import
    if import_file:
        if not import_file.exists():
            console.print(f"[red]Error: File not found: {import_file}[/red]")
            raise typer.Exit(1)

        case = process_witnesses(
            case=case,
            witness_list_path=import_file,
            show_progress=True,
        )
        console.print(f"[green]Imported and matched witnesses[/green]")
        return

    # Handle suggest
    if suggest:
        console.print("\n[bold]Name Suggestions for Speakers[/bold]\n")

        for evidence in case.evidence_items:
            if not evidence.transcript:
                continue

            suggestions = suggest_speaker_names(evidence.transcript)
            if suggestions:
                console.print(f"[cyan]{evidence.filename}:[/cyan]")
                for speaker_id, names in suggestions.items():
                    console.print(f"  {speaker_id}: {', '.join(names)}")

        return

    # Default: list witnesses
    if list_all or not (import_file or rename or suggest):
        _list_witnesses(case)


def _list_witnesses(case) -> None:
    """Display witness list in a table."""
    from ..models import WitnessRole

    if not case.witnesses.witnesses:
        console.print("[yellow]No witnesses found. Run with --import to add a witness list.[/yellow]")
        return

    table = Table(title=f"Witnesses ({len(case.witnesses.witnesses)} total)")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Role")
    table.add_column("Speaker IDs")
    table.add_column("Evidence")
    table.add_column("Verified", justify="center")

    for witness in case.witnesses.witnesses:
        # Format role with color
        role_str = witness.role.value
        if witness.role == WitnessRole.VICTIM:
            role_str = f"[red]{role_str}[/red]"
        elif witness.role == WitnessRole.OFFICER:
            role_str = f"[blue]{role_str}[/blue]"
        elif witness.role == WitnessRole.WITNESS:
            role_str = f"[green]{role_str}[/green]"

        table.add_row(
            witness.id[:8],
            witness.display_name,
            role_str,
            ", ".join(witness.speaker_ids[:2]) + ("..." if len(witness.speaker_ids) > 2 else ""),
            str(len(witness.evidence_appearances)),
            "[green]✓[/green]" if witness.verified else "[dim]✗[/dim]",
        )

    console.print(table)

    # Show unmatched count
    unnamed = case.witnesses.get_unnamed()
    if unnamed:
        console.print(f"\n[yellow]{len(unnamed)} speakers without names. Use --rename to assign names.[/yellow]")


@app.command()
def documents(
    case_dir: Path = typer.Argument(..., help="Case directory"),
    no_ocr: bool = typer.Option(
        False,
        "--no-ocr",
        help="Disable OCR for scanned documents",
    ),
    extract_file: Optional[Path] = typer.Option(
        None,
        "--extract", "-e",
        help="Extract text from a specific file",
    ),
):
    """
    Process documents in a case.

    Extracts text from PDFs, Word documents, and images.
    """
    from ..models import Case
    from ..documents import (
        process_case_documents,
        get_document_summary,
        extract_document_text,
    )

    # Handle single file extraction
    if extract_file:
        if not extract_file.exists():
            console.print(f"[red]Error: File not found: {extract_file}[/red]")
            raise typer.Exit(1)

        console.print(f"Extracting text from: {extract_file.name}\n")
        try:
            text = extract_document_text(extract_file)
            if text:
                console.print(text[:2000])
                if len(text) > 2000:
                    console.print(f"\n[dim]... ({len(text)} characters total)[/dim]")
            else:
                console.print("[yellow]No text extracted.[/yellow]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
        return

    # Process case documents
    case_file = case_dir / "case.json"
    if not case_file.exists():
        console.print(f"[red]Error: case.json not found in {case_dir}[/red]")
        raise typer.Exit(1)

    case = Case.load(case_file)

    console.print(f"Processing documents in case: {case.case_id}\n")

    case = process_case_documents(
        case=case,
        ocr_if_needed=not no_ocr,
        show_progress=True,
    )

    # Show summary
    summary = get_document_summary(case)

    console.print(f"\n[bold]Document Summary[/bold]")
    console.print(f"  Total documents: {summary['total_documents']}")
    console.print(f"  Processed: {summary['processed']}")
    console.print(f"  With text: {summary['with_text']}")
    console.print(f"  Total words: {summary['total_words']:,}")

    if summary['axon_transcripts'] > 0:
        console.print(f"  Axon transcripts: {summary['axon_transcripts']}")

    if summary['by_type']:
        console.print("\n  By type:")
        for ext, count in sorted(summary['by_type'].items()):
            console.print(f"    {ext}: {count}")


@app.command()
def summarize(
    case_dir: Path = typer.Argument(..., help="Case directory"),
    timeline_only: bool = typer.Option(
        False,
        "--timeline",
        help="Only generate timeline",
    ),
    full: bool = typer.Option(
        False,
        "--full",
        help="Include detailed transcript summaries",
    ),
    output_file: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Write summary to file",
    ),
):
    """
    Generate AI summaries for a case.

    Creates:
    - Transcript summaries with key statements
    - Chronological timeline
    - Executive case summary

    Requires Ollama to be running with mistral or similar model.
    """
    from ..models import Case
    from ..summarization import (
        summarize_case_evidence,
        get_case_summary_text,
        get_timeline_text,
        check_ollama_ready,
    )

    case_file = case_dir / "case.json"
    if not case_file.exists():
        console.print(f"[red]Error: case.json not found in {case_dir}[/red]")
        raise typer.Exit(1)

    # Check Ollama
    is_ready, message = check_ollama_ready()
    if not is_ready:
        console.print(f"[yellow]Warning: {message}[/yellow]")
        console.print("[dim]Summaries may be limited without AI.[/dim]\n")

    case = Case.load(case_file)

    console.print(f"\n[bold]Summarizing case: {case.case_id}[/bold]\n")

    if timeline_only:
        # Just build and show timeline
        from ..summarization import build_timeline, format_timeline

        console.print("[bold]Building timeline...[/bold]")
        entries = build_timeline(case)

        if not entries:
            console.print("[yellow]No timeline events found.[/yellow]")
            return

        timeline_text = format_timeline(entries)

        if output_file:
            output_file.write_text(timeline_text)
            console.print(f"\nTimeline saved to: {output_file}")
        else:
            console.print(f"\n{timeline_text}")

        console.print(f"\n[dim]{len(entries)} timeline events[/dim]")
        return

    # Full summarization
    case = summarize_case_evidence(case=case, show_progress=True)

    # Display or save summary
    summary_text = get_case_summary_text(case)

    if output_file:
        output_file.write_text(summary_text)
        console.print(f"\n[green]Summary saved to: {output_file}[/green]")
    else:
        console.print("\n" + "=" * 60)
        console.print(summary_text)

    # Show key stats
    console.print("\n[bold]Summary Statistics[/bold]")
    if case.metadata:
        if case.metadata.get("threats_identified", 0) > 0:
            console.print(f"  [red]Threats detected: {case.metadata['threats_identified']}[/red]")
        if case.metadata.get("violence_indicators", 0) > 0:
            console.print(f"  [yellow]Violence indicators: {case.metadata['violence_indicators']}[/yellow]")
        if case.metadata.get("items_needing_review"):
            console.print(f"  [yellow]Items needing review: {len(case.metadata['items_needing_review'])}[/yellow]")

    console.print(f"  Timeline events: {len(case.timeline)}")


@app.command()
def report(
    case_dir: Path = typer.Argument(..., help="Case directory"),
    format: str = typer.Option(
        "docx",
        "--format", "-f",
        help="Output format: docx, pdf, text, or all",
    ),
    bates_prefix: str = typer.Option(
        "DEF",
        "--bates-prefix", "-b",
        help="Bates number prefix (e.g., DEF, PLT)",
    ),
    bates_start: int = typer.Option(
        1,
        "--bates-start",
        help="Starting Bates number",
    ),
    prepared_by: Optional[str] = typer.Option(
        None,
        "--prepared-by", "-p",
        help="Name of report preparer",
    ),
    include_transcripts: bool = typer.Option(
        False,
        "--include-transcripts",
        help="Include full transcripts in report",
    ),
):
    """
    Generate attorney reports for a case.

    Creates comprehensive reports including:
    - Evidence inventory
    - Witness list
    - Timeline of events
    - Key statements
    - Executive summary

    Output formats:
    - docx: Word document
    - pdf: PDF with Bates numbering
    - text: Plain text
    - all: All formats
    """
    from ..models import Case
    from ..reports import generate_attorney_report, ReportConfig

    case_file = case_dir / "case.json"
    if not case_file.exists():
        console.print(f"[red]Error: case.json not found in {case_dir}[/red]")
        raise typer.Exit(1)

    if format not in ("docx", "pdf", "text", "all"):
        console.print(f"[red]Error: Invalid format '{format}'. Use: docx, pdf, text, or all[/red]")
        raise typer.Exit(1)

    case = Case.load(case_file)

    console.print(f"\n[bold]Generating reports for case: {case.case_id}[/bold]\n")

    config = ReportConfig(
        format=format,
        bates_prefix=bates_prefix,
        bates_start=bates_start,
        prepared_by=prepared_by,
        include_transcripts=include_transcripts,
    )

    result = generate_attorney_report(
        case=case,
        output_dir=case_dir,
        config=config,
        show_progress=True,
    )

    # Show results
    console.print(f"\n[bold green]Reports generated successfully![/bold green]")
    console.print(f"Output directory: {result.output_dir}")
    console.print(f"\nFiles created ({len(result.files_created)}):")

    for filename in result.files_created:
        console.print(f"  - {filename}")

    if result.final_bates_number:
        console.print(f"\n[dim]Bates range: {bates_prefix}{bates_start:06d} - {bates_prefix}{result.final_bates_number:06d}[/dim]")


@app.command()
def version():
    """Show version information."""
    console.print("Third Chair v0.1.0")
    console.print("Legal Discovery Processing Tool")


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()

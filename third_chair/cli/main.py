"""Third Chair CLI - Legal Discovery Processing Tool."""

from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

# Load environment variables early for all commands
load_dotenv()

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


@app.command(name="extract-propositions")
def extract_propositions(
    case_dir: Path = typer.Argument(..., help="Case directory"),
    issue: str = typer.Option(
        "self_defense",
        "--issue", "-i",
        help="Default material issue (self_defense, assault, battery)",
    ),
    proponent: str = typer.Option(
        "Defense",
        "--proponent", "-p",
        help="Default proponent party (Defense, State)",
    ),
    min_confidence: float = typer.Option(
        0.5,
        "--min-confidence",
        help="Minimum transcript confidence threshold",
    ),
    include_timeline: bool = typer.Option(
        True,
        "--include-timeline/--no-timeline",
        help="Include timeline events as proposits",
    ),
):
    """
    Extract propositions from case evidence using the Skanda Framework.

    Seeds proposits from:
    - Flagged transcript segments (threats, violence)
    - Key statements
    - Timeline events
    - Vision analysis findings

    Groups into propositions and evaluates deterministically.
    """
    import json
    from ..models import Case
    from ..analysis import (
        extract_propositions_from_case,
        evaluate_all_propositions,
    )
    from ..analysis.proposition_extractor import ExtractionConfig

    case_file = case_dir / "case.json"
    if not case_file.exists():
        console.print(f"[red]Error: case.json not found in {case_dir}[/red]")
        raise typer.Exit(1)

    with open(case_file) as f:
        data = json.load(f)
    case = Case.from_dict(data)

    console.print(f"\n[bold]Extracting Propositions: {case.case_id}[/bold]\n")

    # Configure extraction
    config = ExtractionConfig(
        include_threats=True,
        include_violence=True,
        include_low_confidence=False,
        include_timeline=include_timeline,
        min_confidence=min_confidence,
        default_proponent=proponent,
        default_issue=issue,
    )

    # Extract propositions
    console.print("[bold]Step 1: Extracting proposits from evidence...[/bold]")
    propositions = extract_propositions_from_case(case, config)
    case.propositions = propositions

    if not propositions:
        console.print("[yellow]No propositions extracted. Ensure case has flagged segments.[/yellow]")
        return

    total_proposits = sum(len(p.skanda.proposits) for p in propositions)
    console.print(f"  Extracted {total_proposits} proposits into {len(propositions)} proposition(s)")

    # Evaluate propositions
    console.print("\n[bold]Step 2: Evaluating propositions...[/bold]")
    evaluate_all_propositions(case)

    # Display results
    table = Table(title="Proposition Evaluation Results")
    table.add_column("ID", style="dim")
    table.add_column("Statement", max_width=40)
    table.add_column("Holds", justify="center")
    table.add_column("Weight", justify="right")
    table.add_column("Probative", justify="right")
    table.add_column("Proposits", justify="right")

    for prop in case.propositions:
        eval_snap = prop.evaluation
        holds_str = str(eval_snap.holds_under_scrutiny.value) if eval_snap else "-"
        if holds_str == "holds":
            holds_str = "[green]holds[/green]"
        elif holds_str == "fails":
            holds_str = "[red]fails[/red]"
        else:
            holds_str = "[yellow]uncertain[/yellow]"

        table.add_row(
            prop.id,
            prop.statement[:40] + "..." if len(prop.statement) > 40 else prop.statement,
            holds_str,
            f"{eval_snap.weight:.2f}" if eval_snap else "-",
            f"{eval_snap.probative_value:.2f}" if eval_snap else "-",
            str(len(prop.skanda.proposits)),
        )

    console.print(table)

    # Save case
    console.print("\n[bold]Step 3: Saving to case.json...[/bold]")
    with open(case_file, "w") as f:
        json.dump(case.to_dict(), f, indent=2, default=str)

    console.print(f"[green]Saved {len(propositions)} proposition(s) with {total_proposits} proposits[/green]")

    # Show evaluation drivers for first proposition
    if propositions and propositions[0].evaluation:
        eval_snap = propositions[0].evaluation
        if eval_snap.drivers:
            console.print("\n[bold]Top Evaluation Drivers:[/bold]")
            if eval_snap.drivers.top_supporting:
                console.print(f"  [green]Supporting:[/green] {len(eval_snap.drivers.top_supporting)} proposits")
            if eval_snap.drivers.top_undermining:
                console.print(f"  [red]Undermining:[/red] {len(eval_snap.drivers.top_undermining)} proposits")


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
def vision(
    case_dir: Path = typer.Argument(..., help="Case directory"),
    all_images: bool = typer.Option(
        False,
        "--all",
        help="Analyze all images in the case",
    ),
    image: Optional[str] = typer.Option(
        None,
        "--image", "-i",
        help="Analyze a specific image by filename",
    ),
    prompt: Optional[str] = typer.Option(
        None,
        "--prompt", "-p",
        help="Custom analysis prompt",
    ),
    prompt_type: str = typer.Option(
        "general",
        "--type", "-t",
        help="Prompt type: general, scene, injury, property, vehicle, document",
    ),
):
    """
    Analyze images using vision AI model.

    Uses qwen2.5vl:3b (or configured vision model) to describe
    evidence photos for legal discovery.
    """
    from ..models import Case, FileType
    from ..documents.vision_analyzer import (
        VisionAnalyzer,
        check_vision_ready,
        LEGAL_PROMPTS,
    )

    case_file = case_dir / "case.json"
    if not case_file.exists():
        console.print(f"[red]Error: case.json not found in {case_dir}[/red]")
        raise typer.Exit(1)

    # Check vision model
    is_ready, message = check_vision_ready()
    if not is_ready:
        console.print(f"[red]Error: {message}[/red]")
        raise typer.Exit(1)

    case = Case.load(case_file)
    analyzer = VisionAnalyzer()

    console.print(f"\n[bold]Vision Analysis for case: {case.case_id}[/bold]")
    console.print(f"Model: {analyzer.model}\n")

    # Get images to analyze
    images = [
        e for e in case.evidence_items
        if e.file_type == FileType.IMAGE and e.file_path.exists()
    ]

    if not images:
        console.print("[yellow]No images found in case.[/yellow]")
        return

    if image:
        # Analyze specific image
        target = next((e for e in images if e.filename == image), None)
        if not target:
            console.print(f"[red]Image not found: {image}[/red]")
            console.print(f"[dim]Available: {', '.join(e.filename for e in images[:5])}...[/dim]")
            raise typer.Exit(1)
        images = [target]
    elif not all_images:
        # Show available images
        console.print(f"[bold]{len(images)} images available:[/bold]")
        for e in images[:10]:
            console.print(f"  - {e.filename}")
        if len(images) > 10:
            console.print(f"  ... and {len(images) - 10} more")
        console.print("\nUse --all to analyze all, or --image <name> for one.")
        return

    # Analyze images
    console.print(f"Analyzing {len(images)} image(s)...\n")

    for i, evidence in enumerate(images, 1):
        console.print(f"[bold][{i}/{len(images)}] {evidence.filename}[/bold]")

        analysis = analyzer.analyze(
            evidence.file_path,
            prompt=prompt,
            prompt_type=prompt_type,
        )

        if not analysis.success:
            console.print(f"[red]  Error: {analysis.error}[/red]")
            continue

        # Show results
        console.print(f"  [dim]Time: {analysis.processing_time_ms:.0f}ms[/dim]")

        if analysis.weapons_detected:
            console.print("  [red bold]WEAPONS DETECTED[/red bold]")
        if analysis.injuries_visible:
            console.print("  [yellow bold]INJURIES VISIBLE[/yellow bold]")
        if analysis.damage_detected:
            console.print("  [orange1]Damage detected[/orange1]")
        if analysis.people_count > 0:
            console.print(f"  People: {analysis.people_count}")
        if analysis.scene_type:
            console.print(f"  Scene: {analysis.scene_type}")

        # Show description (truncated)
        desc = analysis.description[:500]
        if len(analysis.description) > 500:
            desc += "..."
        console.print(f"\n  {desc}\n")

        # Store in evidence metadata
        evidence.metadata["vision_analysis"] = {
            "model": analysis.model,
            "description": analysis.description,
            "weapons_detected": analysis.weapons_detected,
            "injuries_visible": analysis.injuries_visible,
            "damage_detected": analysis.damage_detected,
            "people_count": analysis.people_count,
            "scene_type": analysis.scene_type,
            "key_findings": analysis.key_findings,
        }

    # Save updated case
    case.save(case_file)
    console.print(f"[green]Analysis saved to case.json[/green]")

    # Show summary
    if len(images) > 1:
        weapons = sum(1 for e in images if e.metadata.get("vision_analysis", {}).get("weapons_detected"))
        injuries = sum(1 for e in images if e.metadata.get("vision_analysis", {}).get("injuries_visible"))
        damage = sum(1 for e in images if e.metadata.get("vision_analysis", {}).get("damage_detected"))

        console.print(f"\n[bold]Summary:[/bold]")
        console.print(f"  Images analyzed: {len(images)}")
        if weapons:
            console.print(f"  [red]Weapons detected in {weapons} image(s)[/red]")
        if injuries:
            console.print(f"  [yellow]Injuries visible in {injuries} image(s)[/yellow]")
        if damage:
            console.print(f"  Damage detected in {damage} image(s)")


@app.command("viewing-guide")
def viewing_guide(
    case_dir: Path = typer.Argument(..., help="Path to processed case directory"),
    output: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Output file path (default: reports/viewing_guide.txt)",
    ),
    flags: Optional[str] = typer.Option(
        None,
        "--flags", "-f",
        help="Filter by flag type (comma-separated: THREAT_KEYWORD,VIOLENCE_KEYWORD)",
    ),
    no_speaker: bool = typer.Option(
        False,
        "--no-speaker",
        help="Exclude speaker information from output",
    ),
):
    """
    Generate a viewing guide with recommended video timestamps.

    Extracts flagged moments from transcripts (threats, violence, etc.)
    with timestamps for quick video review.
    """
    from ..models import Case
    from ..reports.viewing_guide import (
        generate_viewing_guide,
        format_viewing_guide_text,
        write_viewing_guide,
        get_viewing_stats,
    )

    # Validate case directory
    case_file = case_dir / "case.json"
    if not case_file.exists():
        console.print(f"[red]Error: No case.json found in {case_dir}[/red]")
        raise typer.Exit(1)

    # Load case
    console.print(f"Loading case from {case_dir}...")
    case = Case.load(case_file)

    # Parse flag filter
    flag_filter = None
    if flags:
        flag_filter = [f.strip().upper() for f in flags.split(",")]
        console.print(f"Filtering by flags: {flag_filter}")

    # Get stats first
    stats = get_viewing_stats(case)
    console.print(f"\n[bold]Viewing Guide Statistics[/bold]")
    console.print(f"  Total flagged moments: {stats['total_flagged_moments']}")
    console.print(f"  Videos with flagged content: {stats['videos_with_flags']}")

    if stats['flag_counts']:
        console.print("\n  Flag breakdown:")
        for flag, count in sorted(stats['flag_counts'].items(), key=lambda x: -x[1]):
            console.print(f"    {flag}: {count}")

    # Set output path
    if output is None:
        reports_dir = case_dir / "reports"
        reports_dir.mkdir(exist_ok=True)
        output = reports_dir / "viewing_guide.txt"

    # Generate guide
    console.print(f"\nGenerating viewing guide...")
    output_path = write_viewing_guide(
        case=case,
        output_path=output,
        flag_filter=flag_filter,
        include_speaker=not no_speaker,
    )

    console.print(f"\n[green]Viewing guide written to: {output_path}[/green]")


@app.command("sync-timeline")
def sync_timeline(
    case_dir: Path = typer.Argument(..., help="Path to case directory"),
    extract_watermarks: bool = typer.Option(
        False,
        "--extract-watermarks", "-e",
        help="Extract timestamps from video watermarks using OCR",
    ),
    force: bool = typer.Option(
        False,
        "--force", "-f",
        help="Re-extract timestamps even if they exist",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Output file for synchronized timeline",
    ),
):
    """
    Build a synchronized multi-camera timeline.

    Extracts UTC timestamps from Axon body camera watermarks and
    creates a unified timeline that correlates events across multiple
    cameras by their synchronized time.

    Steps:
    1. Extract frames from video files
    2. Read Axon watermark timestamps using OCR
    3. Build synchronized timeline mapping events to multiple camera views
    4. Export timeline with relative timecodes for each camera

    Example:
        third-chair sync-timeline ./case --extract-watermarks
        third-chair sync-timeline ./case --output timeline.json
    """
    from ..models import Case, FileType
    from ..documents.watermark_reader import extract_watermark_timestamp
    from ..summarization.multi_camera_timeline import (
        build_multi_camera_timeline,
        format_synchronized_timeline,
    )
    import json

    case_file = case_dir / "case.json"
    if not case_file.exists():
        console.print(f"[red]Error: case.json not found in {case_dir}[/red]")
        raise typer.Exit(1)

    case = Case.load(case_file)
    console.print(f"\n[bold]Synchronizing Timeline: {case.case_id}[/bold]\n")

    # Get video evidence items
    video_items = [
        e for e in case.evidence_items
        if e.file_type == FileType.VIDEO
    ]

    if not video_items:
        console.print("[yellow]No video files found in case.[/yellow]")
        return

    console.print(f"Found {len(video_items)} video file(s)")

    # Step 1: Extract watermark timestamps
    if extract_watermarks:
        console.print("\n[bold]Step 1: Extracting watermark timestamps...[/bold]")

        extracted_count = 0
        for i, evidence in enumerate(video_items, 1):
            # Skip if already has timestamp and not forcing
            if not force and evidence.metadata.get("utc_start_time"):
                console.print(f"  [{i}/{len(video_items)}] {evidence.filename}: [dim]already extracted[/dim]")
                extracted_count += 1
                continue

            console.print(f"  [{i}/{len(video_items)}] {evidence.filename}...", end=" ")

            # Extract watermark
            watermark = extract_watermark_timestamp(evidence.file_path)

            if watermark:
                evidence.metadata["utc_start_time"] = watermark.utc_timestamp.isoformat()
                evidence.metadata["camera_model"] = watermark.camera_model
                evidence.metadata["serial_number"] = watermark.serial_number
                evidence.metadata["watermark_confidence"] = watermark.confidence
                extracted_count += 1
                console.print(f"[green]{watermark.utc_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}[/green]")
            else:
                console.print("[yellow]no watermark found[/yellow]")

        console.print(f"\n  Extracted: {extracted_count}/{len(video_items)} videos")

        # Save updated case
        case.save(case_file)
        console.print("  [dim]Case saved[/dim]")

    # Step 2: Build synchronized timeline
    console.print("\n[bold]Step 2: Building synchronized timeline...[/bold]")

    timeline = build_multi_camera_timeline(case)

    if not timeline.camera_views:
        console.print("[yellow]No cameras with UTC timestamps found.[/yellow]")
        console.print("[dim]Run with --extract-watermarks to extract timestamps from videos.[/dim]")
        return

    # Show camera summary
    console.print(f"\n  Cameras: {len(timeline.camera_views)}")
    for view in timeline.camera_views:
        officer_str = f" ({view.officer})" if view.officer else ""
        console.print(
            f"    - {view.filename}{officer_str}: "
            f"{view.utc_start.strftime('%H:%M:%S')} - {view.utc_end.strftime('%H:%M:%S')} UTC"
        )

    console.print(f"\n  Events: {len(timeline.events)}")
    if timeline.time_range_start and timeline.time_range_end:
        console.print(
            f"  Time range: {timeline.time_range_start.strftime('%Y-%m-%d %H:%M:%S')} - "
            f"{timeline.time_range_end.strftime('%H:%M:%S')} UTC"
        )

    # Step 3: Output
    if output:
        # Save as JSON
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w") as f:
            json.dump(timeline.to_dict(), f, indent=2, default=str)
        console.print(f"\n[green]Timeline saved to: {output}[/green]")
    else:
        # Show formatted timeline
        console.print("\n")
        formatted = format_synchronized_timeline(timeline)
        console.print(formatted)

    # Save synchronized timeline to case metadata
    case.metadata["synchronized_timeline"] = timeline.to_dict()
    case.save(case_file)

    # Also write text report
    reports_dir = case_dir / "reports"
    reports_dir.mkdir(exist_ok=True)
    timeline_file = reports_dir / "synchronized_timeline.txt"
    timeline_file.write_text(format_synchronized_timeline(timeline))
    console.print(f"\n[dim]Timeline report saved to: {timeline_file}[/dim]")


@app.command()
def tui(
    case_dir: Optional[Path] = typer.Argument(
        None,
        help="Path to case directory (skips case selection if provided)",
    ),
    search_path: Optional[Path] = typer.Option(
        None,
        "--search-path", "-s",
        help="Additional path to search for cases",
    ),
):
    """
    Launch the Third Chair graphical interface.

    Opens a terminal-based interface with:
    - Case file navigation (left panel)
    - Research chat assistant (right panel)

    If no case directory is specified, displays a list of
    available cases for selection.

    Keyboard shortcuts:
    - Tab: Switch between panels
    - Q: Quit
    - ?: Show help

    Example:
        third-chair tui
        third-chair tui ./Case-9420250016631
        third-chair tui --search-path /mnt/d/cases
    """
    from ..tui import run_tui

    # Build search paths
    search_paths = [Path.cwd()]

    # Add common case locations
    common_paths = [
        Path("/mnt/d/Third_Chair"),
        Path("/mnt/c/Third_Chair"),
        Path.home() / "Third_Chair",
    ]
    for p in common_paths:
        if p.exists() and p not in search_paths:
            search_paths.append(p)

    # Add user-specified search path
    if search_path and search_path.exists():
        search_paths.insert(0, search_path)

    # If case_dir provided, validate it
    if case_dir:
        case_file = case_dir / "case.json"
        if not case_file.exists():
            console.print(f"[red]Error: case.json not found in {case_dir}[/red]")
            raise typer.Exit(1)

    console.print("[dim]Launching Third Chair TUI...[/dim]")
    run_tui(case_path=case_dir, search_paths=search_paths)


@app.command()
def chat(
    case_dir: Path = typer.Argument(..., help="Path to processed case directory"),
    query: Optional[str] = typer.Option(
        None,
        "--query", "-q",
        help="Single query to run (non-interactive mode)",
    ),
):
    """
    Interactive chat interface for case research.

    Start an interactive session to query case evidence using natural language.
    Available commands:
      - search <query>: Search transcripts for keywords
      - threats: Show threat statements
      - violence: Show violence statements
      - witnesses: List witnesses
      - case: Show case info
      - timeline: Show timeline
      - propositions: List propositions (if extracted)
      - tools: List all available tools
      - help: Show help
      - quit: Exit

    Example:
      third-chair chat ./case_output
      third-chair chat ./case_output --query "search knife"
    """
    from rich.panel import Panel
    from rich.markdown import Markdown

    from ..models import Case
    from ..chat import ToolRegistry

    # Load case
    case_file = case_dir / "case.json"
    if not case_file.exists():
        console.print(f"[red]Error: case.json not found in {case_dir}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[dim]Loading case from {case_file}...[/dim]")
    case = Case.load(case_file)

    # Create registry
    registry = ToolRegistry(case)

    # Show header
    console.print(Panel(
        f"[bold]Third Chair Chat[/bold]\n"
        f"Case: {case.case_id}\n"
        f"Evidence: {case.evidence_count} items | "
        f"Witnesses: {len(case.witnesses.witnesses)} | "
        f"Propositions: {case.proposition_count}",
        title="Research Assistant",
        border_style="blue",
    ))

    # Single query mode
    if query:
        _process_chat_command(registry, query, console)
        return

    # Interactive mode
    console.print("\n[dim]Type 'help' for commands, 'quit' to exit[/dim]\n")

    while True:
        try:
            cmd = console.input("[bold blue]>[/bold blue] ").strip()

            if not cmd:
                continue

            if cmd.lower() in ("quit", "exit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break

            _process_chat_command(registry, cmd, console)

        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye![/dim]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


def _process_chat_command(registry, cmd: str, console) -> None:
    """Process a chat command."""
    from rich.table import Table

    cmd_lower = cmd.lower()

    if cmd_lower == "help":
        console.print("""
[bold]Available Commands:[/bold]
  [cyan]search <query>[/cyan]    Search transcripts for keywords
  [cyan]threats[/cyan]           Show statements with threat keywords
  [cyan]violence[/cyan]          Show statements with violence keywords
  [cyan]witnesses[/cyan]         List all witnesses
  [cyan]case[/cyan]              Show case information
  [cyan]timeline[/cyan]          Show case timeline
  [cyan]propositions[/cyan]      List propositions (Skanda framework)
  [cyan]tools[/cyan]             List all available tools
  [cyan]who said <quote>[/cyan]  Find who said a specific quote
  [cyan]quit[/cyan]              Exit the chat
""")

    elif cmd_lower == "tools":
        table = Table(title="Available Tools")
        table.add_column("Tool", style="cyan")
        table.add_column("Description")
        for tool in registry.list_tools():
            table.add_row(tool.name, tool.description[:60] + "...")
        console.print(table)

    elif cmd_lower == "case":
        result = registry.invoke("get_case_info")
        if result.success:
            table = Table(title="Case Information")
            table.add_column("Field", style="cyan")
            table.add_column("Value")
            for k, v in result.data.items():
                table.add_row(k, str(v) if v else "-")
            console.print(table)
        else:
            console.print(f"[red]Error: {result.error}[/red]")

    elif cmd_lower == "witnesses":
        result = registry.invoke("get_witness_list")
        if result.success:
            table = Table(title="Witnesses")
            table.add_column("ID", style="dim")
            table.add_column("Name", style="cyan")
            table.add_column("Role")
            table.add_column("Verified")
            for w in result.data:
                table.add_row(
                    w["id"],
                    w["name"] or "-",
                    str(w["role"]).replace("WitnessRole.", ""),
                    "[green]Yes[/green]" if w["verified"] else "[dim]No[/dim]",
                )
            console.print(table)
        else:
            console.print(f"[red]Error: {result.error}[/red]")

    elif cmd_lower == "threats":
        result = registry.invoke("get_flagged_statements", flag_type="THREAT_KEYWORD")
        if result.success:
            console.print(f"\n[bold]Threat Statements ({len(result.data)} found)[/bold]\n")
            for i, r in enumerate(result.data[:15], 1):
                console.print(f"[cyan]{i}.[/cyan] {r['filename']} @ [yellow]{r['timestamp']}[/yellow]")
                console.print(f"   [{r['speaker']}]: {r['text'][:100]}...")
                console.print()
        else:
            console.print(f"[red]Error: {result.error}[/red]")

    elif cmd_lower == "violence":
        result = registry.invoke("get_flagged_statements", flag_type="VIOLENCE_KEYWORD")
        if result.success:
            console.print(f"\n[bold]Violence Statements ({len(result.data)} found)[/bold]\n")
            for i, r in enumerate(result.data[:15], 1):
                console.print(f"[cyan]{i}.[/cyan] {r['filename']} @ [yellow]{r['timestamp']}[/yellow]")
                console.print(f"   [{r['speaker']}]: {r['text'][:100]}...")
                console.print()
        else:
            console.print(f"[red]Error: {result.error}[/red]")

    elif cmd_lower == "timeline":
        result = registry.invoke("get_timeline")
        if result.success:
            console.print(f"\n[bold]Timeline ({len(result.data)} events)[/bold]\n")
            for i, e in enumerate(result.data[:20], 1):
                console.print(f"[cyan]{e['timestamp'][:19]}[/cyan] - {e['description'][:80]}...")
        else:
            console.print(f"[red]Error: {result.error}[/red]")

    elif cmd_lower == "propositions":
        result = registry.invoke("list_propositions")
        if result.success:
            if not result.data:
                console.print("[dim]No propositions extracted yet. Run proposition extraction first.[/dim]")
            else:
                table = Table(title="Propositions")
                table.add_column("ID", style="cyan")
                table.add_column("Statement")
                table.add_column("Holds", style="bold")
                table.add_column("Weight")
                table.add_column("Proposits")
                for p in result.data:
                    holds = p.get("holds_under_scrutiny", "?")
                    holds_style = {"holds": "[green]", "fails": "[red]", "uncertain": "[yellow]"}.get(holds, "")
                    table.add_row(
                        p["id"],
                        p["statement"][:40] + "...",
                        f"{holds_style}{holds}[/]",
                        f"{p.get('weight', 0):.2f}" if p.get('weight') else "-",
                        str(p.get("proposit_count", 0)),
                    )
                console.print(table)
        else:
            console.print(f"[red]Error: {result.error}[/red]")

    elif cmd_lower.startswith("search "):
        query = cmd[7:].strip()
        if not query:
            console.print("[yellow]Usage: search <query>[/yellow]")
            return
        result = registry.invoke("search_transcripts", query=query)
        if result.success:
            console.print(f"\n[bold]Search Results for '{query}' ({len(result.data)} found)[/bold]\n")
            for i, r in enumerate(result.data[:15], 1):
                console.print(f"[cyan]{i}.[/cyan] {r['filename']} @ [yellow]{r['timestamp']}[/yellow]")
                console.print(f"   [{r['speaker']}]: {r['text'][:100]}...")
                console.print()
        else:
            console.print(f"[red]Error: {result.error}[/red]")

    elif cmd_lower.startswith("who said "):
        quote = cmd[9:].strip().strip('"\'')
        if not quote:
            console.print("[yellow]Usage: who said <quote>[/yellow]")
            return
        result = registry.invoke("who_said", quote=quote)
        if result.success:
            if "error" in result.data:
                console.print(f"[yellow]{result.data['error']}[/yellow]")
            else:
                console.print(f"\n[bold]Found:[/bold]")
                console.print(f"  Speaker: [cyan]{result.data['speaker']}[/cyan] ({result.data.get('speaker_role', 'unknown')})")
                console.print(f"  File: {result.data['filename']} @ [yellow]{result.data['timestamp']}[/yellow]")
                console.print(f"  Full text: \"{result.data['full_text']}\"")
        else:
            console.print(f"[red]Error: {result.error}[/red]")

    else:
        console.print(f"[yellow]Unknown command: {cmd}[/yellow]")
        console.print("[dim]Type 'help' for available commands[/dim]")


# =============================================================================
# Vault Commands (Encryption)
# =============================================================================


@app.command("vault-init")
def vault_init(
    case_dir: Path = typer.Argument(..., help="Path to case directory to encrypt"),
    timeout: int = typer.Option(
        30,
        "--timeout", "-t",
        help="Session timeout in minutes (0 = no timeout)",
    ),
):
    """
    Encrypt an existing case directory.

    Creates a vault with AES-256 encryption for all case files.
    After encryption, case data can only be accessed through Third Chair
    interfaces (TUI, CLI) with the correct password.

    Files encrypted:
    - case.json (case metadata)
    - extracted/* (evidence files)

    The original unencrypted files are removed after successful encryption.

    Example:
        third-chair vault-init ./my_case
    """
    from getpass import getpass
    from ..vault import (
        encrypt_existing_case,
        is_vault_encrypted,
        VaultAlreadyExistsError,
    )

    case_file = case_dir / "case.json"
    if not case_file.exists():
        console.print(f"[red]Error: case.json not found in {case_dir}[/red]")
        raise typer.Exit(1)

    if is_vault_encrypted(case_dir):
        console.print(f"[yellow]Case is already encrypted.[/yellow]")
        console.print("Use 'vault-status' to check encryption status.")
        raise typer.Exit(1)

    console.print(f"\n[bold]Third Chair Vault - Encrypt Case[/bold]\n")
    console.print(f"Case directory: {case_dir}")
    console.print()
    console.print("[yellow]Warning: This will encrypt all case files.[/yellow]")
    console.print("[yellow]Original files will be removed after encryption.[/yellow]")
    console.print()

    # Get password
    password = getpass("Enter master password: ")
    if len(password) < 8:
        console.print("[red]Error: Password must be at least 8 characters[/red]")
        raise typer.Exit(1)

    confirm = getpass("Confirm password: ")
    if password != confirm:
        console.print("[red]Error: Passwords do not match[/red]")
        raise typer.Exit(1)

    console.print()
    console.print("[bold]Encrypting case...[/bold]")

    try:
        stats = encrypt_existing_case(
            case_dir=case_dir,
            password=password,
            show_progress=True,
        )

        console.print()
        console.print(f"[bold green]Case encrypted successfully![/bold green]")
        console.print(f"  Files encrypted: {stats['files_encrypted']}")
        console.print(f"  Bytes encrypted: {stats['bytes_encrypted']:,}")

        if stats['errors']:
            console.print(f"[yellow]  Errors: {len(stats['errors'])}[/yellow]")

        console.print()
        console.print("[dim]Case is now protected. Use 'vault-unlock' to access.[/dim]")

    except VaultAlreadyExistsError:
        console.print("[red]Error: Case is already encrypted[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command("vault-unlock")
def vault_unlock(
    case_dir: Path = typer.Argument(..., help="Path to encrypted case directory"),
    timeout: int = typer.Option(
        30,
        "--timeout", "-t",
        help="Session timeout in minutes (0 = no timeout)",
    ),
):
    """
    Unlock an encrypted case for this session.

    After unlocking, the case can be accessed through Third Chair
    commands (tui, chat, status, etc.) without re-entering the password.

    Session automatically expires after the timeout period of inactivity.

    Example:
        third-chair vault-unlock ./my_case
        third-chair vault-unlock ./my_case --timeout 60
    """
    from getpass import getpass
    from ..vault import (
        VaultManager,
        is_vault_encrypted,
        is_vault_unlocked,
        InvalidPasswordError,
        VaultNotFoundError,
    )

    if not case_dir.exists():
        console.print(f"[red]Error: Directory not found: {case_dir}[/red]")
        raise typer.Exit(1)

    if not is_vault_encrypted(case_dir):
        console.print("[yellow]Case is not encrypted.[/yellow]")
        raise typer.Exit(0)

    if is_vault_unlocked(case_dir):
        console.print("[green]Vault is already unlocked.[/green]")
        raise typer.Exit(0)

    console.print(f"\n[bold]Third Chair Vault - Unlock[/bold]\n")
    console.print(f"Case: {case_dir.name}")

    password = getpass("Enter password: ")

    try:
        vm = VaultManager(case_dir)
        session = vm.unlock(password, timeout_minutes=timeout)

        console.print()
        console.print(f"[bold green]Vault unlocked![/bold green]")

        if timeout > 0:
            console.print(f"[dim]Session expires in {timeout} minutes of inactivity.[/dim]")
        else:
            console.print("[dim]Session has no timeout.[/dim]")

    except InvalidPasswordError:
        console.print("[red]Error: Invalid password[/red]")
        raise typer.Exit(1)
    except VaultNotFoundError:
        console.print("[red]Error: Not an encrypted vault[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command("vault-lock")
def vault_lock(
    case_dir: Optional[Path] = typer.Argument(
        None,
        help="Case directory to lock (omit to lock all)",
    ),
    all_vaults: bool = typer.Option(
        False,
        "--all", "-a",
        help="Lock all unlocked vaults",
    ),
):
    """
    Lock an encrypted case (clear session).

    Clears the encryption keys from memory, requiring the password
    to be re-entered for further access.

    Use --all to lock all currently unlocked vaults.

    Example:
        third-chair vault-lock ./my_case
        third-chair vault-lock --all
    """
    from ..vault import lock_vault, lock_all_vaults, is_vault_unlocked

    if all_vaults or case_dir is None:
        count = lock_all_vaults()
        if count > 0:
            console.print(f"[green]Locked {count} vault(s)[/green]")
        else:
            console.print("[dim]No vaults were unlocked[/dim]")
        return

    if not case_dir.exists():
        console.print(f"[red]Error: Directory not found: {case_dir}[/red]")
        raise typer.Exit(1)

    if not is_vault_unlocked(case_dir):
        console.print("[dim]Vault is already locked[/dim]")
        return

    if lock_vault(case_dir):
        console.print(f"[green]Vault locked: {case_dir.name}[/green]")
    else:
        console.print("[dim]Vault was not unlocked[/dim]")


@app.command("vault-status")
def vault_status(
    case_dir: Path = typer.Argument(..., help="Path to case directory"),
):
    """
    Show encryption status of a case.

    Displays whether the case is encrypted, locked/unlocked,
    and session timeout information.

    Example:
        third-chair vault-status ./my_case
    """
    from ..vault import (
        VaultManager,
        is_vault_encrypted,
        get_vault_session,
    )

    if not case_dir.exists():
        console.print(f"[red]Error: Directory not found: {case_dir}[/red]")
        raise typer.Exit(1)

    case_file = case_dir / "case.json"
    enc_case_file = case_dir / "case.json.enc"

    console.print(f"\n[bold]Vault Status: {case_dir.name}[/bold]\n")

    if not is_vault_encrypted(case_dir):
        console.print("  Encrypted: [yellow]No[/yellow]")
        console.print("  Status: [dim]Unprotected[/dim]")
        console.print()
        console.print("[dim]Use 'vault-init' to encrypt this case.[/dim]")
        return

    # Load metadata
    vm = VaultManager(case_dir)
    metadata = vm.metadata

    console.print("  Encrypted: [green]Yes[/green]")
    console.print(f"  Algorithm: {metadata.algorithm}")
    console.print(f"  Key derivation: {metadata.key_derivation}")
    console.print(f"  Iterations: {metadata.iterations:,}")
    console.print(f"  Created: {metadata.created_at}")

    # Check session
    session = get_vault_session(case_dir)
    if session:
        remaining = session.time_remaining()
        if remaining:
            minutes = int(remaining.total_seconds() / 60)
            seconds = int(remaining.total_seconds() % 60)
            console.print(f"\n  Session: [green]Unlocked[/green]")
            console.print(f"  Time remaining: {minutes}m {seconds}s")
        else:
            console.print(f"\n  Session: [green]Unlocked[/green] (no timeout)")
    else:
        console.print(f"\n  Session: [red]Locked[/red]")
        console.print("  [dim]Use 'vault-unlock' to access case data.[/dim]")


@app.command("vault-export")
def vault_export(
    case_dir: Path = typer.Argument(..., help="Path to encrypted case directory"),
    output: Path = typer.Option(
        ...,
        "--output", "-o",
        help="Output directory for decrypted copy",
    ),
):
    """
    Export a decrypted copy of an encrypted case.

    Creates a new directory with fully decrypted files.
    The original encrypted vault remains unchanged.

    Useful for:
    - Creating backups
    - Sharing with users who don't have Third Chair
    - Court filing requirements

    Example:
        third-chair vault-export ./my_case -o ./my_case_decrypted
    """
    from getpass import getpass
    from ..vault import (
        decrypt_case_for_export,
        is_vault_encrypted,
        is_vault_unlocked,
        VaultManager,
        InvalidPasswordError,
        VaultNotFoundError,
    )

    if not case_dir.exists():
        console.print(f"[red]Error: Directory not found: {case_dir}[/red]")
        raise typer.Exit(1)

    if not is_vault_encrypted(case_dir):
        console.print("[yellow]Case is not encrypted. Use 'cp -r' to copy.[/yellow]")
        raise typer.Exit(1)

    if output.exists():
        console.print(f"[red]Error: Output directory already exists: {output}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Third Chair Vault - Export Decrypted[/bold]\n")
    console.print(f"Source: {case_dir}")
    console.print(f"Output: {output}")
    console.print()

    # Get password if not unlocked
    password = None
    if not is_vault_unlocked(case_dir):
        password = getpass("Enter password: ")

        # Verify password
        vm = VaultManager(case_dir)
        if not vm.verify_password(password):
            console.print("[red]Error: Invalid password[/red]")
            raise typer.Exit(1)
    else:
        # Get password from session - need to re-enter for export
        console.print("[dim]Vault is unlocked, but password required for export.[/dim]")
        password = getpass("Enter password: ")

        vm = VaultManager(case_dir)
        if not vm.verify_password(password):
            console.print("[red]Error: Invalid password[/red]")
            raise typer.Exit(1)

    console.print()
    console.print("[bold]Exporting decrypted files...[/bold]")

    try:
        stats = decrypt_case_for_export(
            case_dir=case_dir,
            password=password,
            output_dir=output,
            show_progress=True,
        )

        console.print()
        console.print(f"[bold green]Export complete![/bold green]")
        console.print(f"  Files decrypted: {stats['files_decrypted']}")
        console.print(f"  Files copied: {stats['files_copied']}")
        console.print(f"  Output: {output}")

        if stats['errors']:
            console.print(f"[yellow]  Errors: {len(stats['errors'])}[/yellow]")

    except InvalidPasswordError:
        console.print("[red]Error: Invalid password[/red]")
        raise typer.Exit(1)
    except VaultNotFoundError:
        console.print("[red]Error: Not an encrypted vault[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command("vault-verify")
def vault_verify(
    case_dir: Path = typer.Argument(..., help="Path to encrypted case directory"),
):
    """
    Verify integrity of an encrypted vault.

    Tests that all encrypted files can be successfully decrypted.
    Does not write any files - only verifies decryption works.

    Example:
        third-chair vault-verify ./my_case
    """
    from getpass import getpass
    from ..vault import (
        verify_vault_integrity,
        is_vault_encrypted,
        is_vault_unlocked,
        VaultManager,
        InvalidPasswordError,
    )

    if not case_dir.exists():
        console.print(f"[red]Error: Directory not found: {case_dir}[/red]")
        raise typer.Exit(1)

    if not is_vault_encrypted(case_dir):
        console.print("[yellow]Case is not encrypted.[/yellow]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Third Chair Vault - Verify Integrity[/bold]\n")
    console.print(f"Case: {case_dir.name}")
    console.print()

    # Get password if not unlocked
    password = None
    if not is_vault_unlocked(case_dir):
        password = getpass("Enter password: ")
    else:
        # Use existing session - still need password for verification
        password = getpass("Enter password to verify: ")

    try:
        vm = VaultManager(case_dir)
        if not vm.verify_password(password):
            console.print("[red]Error: Invalid password[/red]")
            raise typer.Exit(1)

        console.print("[bold]Verifying encrypted files...[/bold]")

        stats = verify_vault_integrity(
            case_dir=case_dir,
            password=password,
            show_progress=True,
        )

        console.print()
        if stats['files_failed'] == 0:
            console.print(f"[bold green]Vault integrity verified![/bold green]")
            console.print(f"  Files verified: {stats['files_verified']}")
        else:
            console.print(f"[bold red]Integrity check failed![/bold red]")
            console.print(f"  Files verified: {stats['files_verified']}")
            console.print(f"  Files failed: {stats['files_failed']}")
            for error in stats['errors'][:5]:
                console.print(f"    [red]- {error}[/red]")
            raise typer.Exit(1)

    except InvalidPasswordError:
        console.print("[red]Error: Invalid password[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command("vault-rotate")
def vault_rotate(
    case_dir: Path = typer.Argument(..., help="Path to encrypted case directory"),
):
    """
    Change the vault password.

    Re-encrypts all files with a new key derived from the new password.
    Requires current password for verification.

    Example:
        third-chair vault-rotate ./my_case
    """
    from getpass import getpass
    from ..vault import (
        rotate_password,
        is_vault_encrypted,
        VaultManager,
        InvalidPasswordError,
    )

    if not case_dir.exists():
        console.print(f"[red]Error: Directory not found: {case_dir}[/red]")
        raise typer.Exit(1)

    if not is_vault_encrypted(case_dir):
        console.print("[yellow]Case is not encrypted.[/yellow]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Third Chair Vault - Change Password[/bold]\n")
    console.print(f"Case: {case_dir.name}")
    console.print()
    console.print("[yellow]Warning: This will re-encrypt all files with a new key.[/yellow]")
    console.print()

    # Get current password
    old_password = getpass("Enter current password: ")

    vm = VaultManager(case_dir)
    if not vm.verify_password(old_password):
        console.print("[red]Error: Invalid current password[/red]")
        raise typer.Exit(1)

    # Get new password
    console.print()
    new_password = getpass("Enter new password: ")
    if len(new_password) < 8:
        console.print("[red]Error: New password must be at least 8 characters[/red]")
        raise typer.Exit(1)

    confirm = getpass("Confirm new password: ")
    if new_password != confirm:
        console.print("[red]Error: Passwords do not match[/red]")
        raise typer.Exit(1)

    if new_password == old_password:
        console.print("[yellow]New password is the same as old password.[/yellow]")
        raise typer.Exit(0)

    console.print()
    console.print("[bold]Re-encrypting files with new key...[/bold]")

    try:
        stats = rotate_password(
            case_dir=case_dir,
            old_password=old_password,
            new_password=new_password,
            show_progress=True,
        )

        console.print()
        console.print(f"[bold green]Password changed successfully![/bold green]")
        console.print(f"  Files re-encrypted: {stats['files_rotated']}")

        if stats['errors']:
            console.print(f"[yellow]  Errors: {len(stats['errors'])}[/yellow]")
            for error in stats['errors'][:3]:
                console.print(f"    [red]- {error}[/red]")

    except InvalidPasswordError:
        console.print("[red]Error: Invalid password[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# Work Item Commands
# =============================================================================

work_app = typer.Typer(
    name="work",
    help="Manage work items (investigations, legal questions, actions, etc.)",
    no_args_is_help=True,
)
app.add_typer(work_app, name="work")


@work_app.command("list")
def work_list(
    case_dir: Path = typer.Argument(..., help="Path to case directory"),
    status: Optional[str] = typer.Option(
        None,
        "--status", "-s",
        help="Filter by status (pending, in_progress, completed, blocked)",
    ),
    item_type: Optional[str] = typer.Option(
        None,
        "--type", "-t",
        help="Filter by type (investigation, legal_question, objective, action, fact)",
    ),
    assigned_to: Optional[str] = typer.Option(
        None,
        "--assigned", "-a",
        help="Filter by assignee",
    ),
):
    """List work items for a case."""
    from ..work import WorkStorage, WorkItemType, WorkItemStatus

    if not case_dir.exists():
        console.print(f"[red]Error: Case directory not found: {case_dir}[/red]")
        raise typer.Exit(1)

    storage = WorkStorage(case_dir)

    # Parse filters
    status_filter = WorkItemStatus(status) if status else None
    type_filter = WorkItemType(item_type) if item_type else None

    items = storage.list_items(
        status=status_filter,
        item_type=type_filter,
        assigned_to=assigned_to,
    )

    if not items:
        console.print("[yellow]No work items found.[/yellow]")
        return

    # Create table
    table = Table(title=f"Work Items ({len(items)})")
    table.add_column("ID", style="cyan")
    table.add_column("Type", style="dim")
    table.add_column("Title")
    table.add_column("Status")
    table.add_column("Priority")
    table.add_column("Assigned")
    table.add_column("Due")

    status_colors = {
        "pending": "yellow",
        "in_progress": "blue",
        "completed": "green",
        "blocked": "red",
    }

    priority_colors = {
        "critical": "red bold",
        "high": "red",
        "medium": "yellow",
        "low": "dim",
    }

    for item in items:
        status_style = status_colors.get(item.status.value, "")
        priority_style = priority_colors.get(item.priority.value, "")

        due_str = ""
        if item.due_date:
            due_str = item.due_date.strftime("%Y-%m-%d")
            if item.is_overdue:
                due_str = f"[red]{due_str} OVERDUE[/red]"

        table.add_row(
            item.id,
            item.item_type.value[:3].upper(),
            item.title[:40] + "..." if len(item.title) > 40 else item.title,
            f"[{status_style}]{item.status.value}[/{status_style}]",
            f"[{priority_style}]{item.priority.value}[/{priority_style}]",
            item.assigned_to or "-",
            due_str or "-",
        )

    console.print(table)


@work_app.command("add")
def work_add(
    case_dir: Path = typer.Argument(..., help="Path to case directory"),
    title: str = typer.Option(..., "--title", "-T", help="Title of the work item"),
    item_type: str = typer.Option(
        "action",
        "--type", "-t",
        help="Type: investigation, legal_question, objective, action, fact",
    ),
    description: str = typer.Option("", "--description", "-d", help="Description"),
    priority: str = typer.Option("medium", "--priority", "-p", help="Priority: low, medium, high, critical"),
    assigned_to: Optional[str] = typer.Option(None, "--assigned", "-a", help="Assignee"),
    due_date: Optional[str] = typer.Option(None, "--due", help="Due date (YYYY-MM-DD)"),
    tags: Optional[str] = typer.Option(None, "--tags", help="Comma-separated tags"),
):
    """Add a new work item."""
    from ..work import WorkStorage, WorkItemType

    if not case_dir.exists():
        console.print(f"[red]Error: Case directory not found: {case_dir}[/red]")
        raise typer.Exit(1)

    storage = WorkStorage(case_dir)

    # Parse type
    try:
        work_type = WorkItemType(item_type)
    except ValueError:
        console.print(f"[red]Invalid type: {item_type}[/red]")
        console.print("Valid types: investigation, legal_question, objective, action, fact")
        raise typer.Exit(1)

    # Parse tags
    tag_list = [t.strip() for t in tags.split(",")] if tags else []

    # Create item
    item = storage.create_item(
        item_type=work_type,
        title=title,
        description=description,
        priority=priority,
        assigned_to=assigned_to,
        tags=tag_list,
        due_date=due_date,
    )

    console.print(f"[green]Created work item:[/green] {item.id}")
    console.print(f"  Title: {item.title}")
    console.print(f"  Type: {item.item_type.value}")
    console.print(f"  Priority: {item.priority.value}")
    if item.assigned_to:
        console.print(f"  Assigned to: {item.assigned_to}")
    if item.due_date:
        console.print(f"  Due: {item.due_date.strftime('%Y-%m-%d')}")


@work_app.command("update")
def work_update(
    case_dir: Path = typer.Argument(..., help="Path to case directory"),
    item_id: str = typer.Argument(..., help="Work item ID (e.g., INV-0001)"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="New status"),
    priority: Optional[str] = typer.Option(None, "--priority", "-p", help="New priority"),
    assigned_to: Optional[str] = typer.Option(None, "--assigned", "-a", help="New assignee"),
    note: Optional[str] = typer.Option(None, "--note", "-n", help="Add a note"),
    due_date: Optional[str] = typer.Option(None, "--due", help="New due date"),
):
    """Update an existing work item."""
    from ..work import WorkStorage

    if not case_dir.exists():
        console.print(f"[red]Error: Case directory not found: {case_dir}[/red]")
        raise typer.Exit(1)

    storage = WorkStorage(case_dir)

    item = storage.update_item(
        item_id=item_id,
        status=status,
        priority=priority,
        assigned_to=assigned_to,
        note=note,
        due_date=due_date,
    )

    if not item:
        console.print(f"[red]Work item not found: {item_id}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Updated:[/green] {item.id}")
    console.print(f"  Status: {item.status.value}")
    console.print(f"  Priority: {item.priority.value}")
    if note:
        console.print(f"  Note added: {note[:50]}...")


@work_app.command("status")
def work_status(
    case_dir: Path = typer.Argument(..., help="Path to case directory"),
):
    """Show work item dashboard for a case."""
    from ..work import WorkStorage

    if not case_dir.exists():
        console.print(f"[red]Error: Case directory not found: {case_dir}[/red]")
        raise typer.Exit(1)

    storage = WorkStorage(case_dir)
    summary = storage.get_summary()

    console.print(f"\n[bold]Work Items Dashboard[/bold]")
    console.print(f"Case: [cyan]{summary['case_id']}[/cyan]")

    if summary['attorney']:
        console.print(f"Attorney: {summary['attorney']}")
    if summary['resolution_path']:
        console.print(f"Resolution path: {summary['resolution_path']}")

    console.print(f"\nLast touch: [dim]{summary['last_touch']}[/dim]")
    if summary['last_action']:
        console.print(f"Last action: {summary['last_action']}")

    # Stats
    stats = summary['stats']
    console.print(f"\n[bold]Statistics[/bold]")
    console.print(f"  Total: {stats['total']}")
    console.print(f"  Pending: [yellow]{stats['pending']}[/yellow]")
    console.print(f"  In Progress: [blue]{stats['in_progress']}[/blue]")
    console.print(f"  Completed: [green]{stats['completed']}[/green]")
    console.print(f"  Blocked: [red]{stats['blocked']}[/red]")
    if stats['overdue'] > 0:
        console.print(f"  [red bold]OVERDUE: {stats['overdue']}[/red bold]")

    # Overdue items
    if summary['overdue']:
        console.print(f"\n[red bold]Overdue Items:[/red bold]")
        for item in summary['overdue'][:5]:
            console.print(f"  {item.id}: {item.title}")

    # Recent pending
    if summary['recent_pending']:
        console.print(f"\n[yellow]Recent Pending:[/yellow]")
        for item in summary['recent_pending'][:5]:
            console.print(f"  {item.id}: {item.title}")


@work_app.command("show")
def work_show(
    case_dir: Path = typer.Argument(..., help="Path to case directory"),
    item_id: str = typer.Argument(..., help="Work item ID"),
):
    """Show details of a specific work item."""
    from ..work import WorkStorage

    if not case_dir.exists():
        console.print(f"[red]Error: Case directory not found: {case_dir}[/red]")
        raise typer.Exit(1)

    storage = WorkStorage(case_dir)
    item = storage.load_item(item_id)

    if not item:
        console.print(f"[red]Work item not found: {item_id}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]{item.id}: {item.title}[/bold]")
    console.print(f"Type: {item.item_type.value}")
    console.print(f"Status: {item.status.value}")
    console.print(f"Priority: {item.priority.value}")

    if item.description:
        console.print(f"\n[dim]Description:[/dim]")
        console.print(f"  {item.description}")

    if item.assigned_to:
        console.print(f"\nAssigned to: {item.assigned_to}")
    if item.due_date:
        due_str = item.due_date.strftime("%Y-%m-%d")
        if item.is_overdue:
            console.print(f"Due: [red]{due_str} (OVERDUE)[/red]")
        else:
            console.print(f"Due: {due_str}")

    if item.tags:
        console.print(f"Tags: {', '.join(item.tags)}")

    if item.blocked_by:
        console.print(f"[red]Blocked by: {', '.join(item.blocked_by)}[/red]")

    if item.supports_propositions:
        console.print(f"Supports propositions: {', '.join(item.supports_propositions)}")

    if item.notes:
        console.print(f"\n[dim]Notes ({len(item.notes)}):[/dim]")
        for note in item.notes[-5:]:
            date_str = note.date.strftime("%Y-%m-%d") if hasattr(note.date, 'strftime') else str(note.date)
            console.print(f"  [{date_str}] {note.text}")

    console.print(f"\nCreated: {item.created}")
    console.print(f"Updated: {item.updated}")


@work_app.command("complete")
def work_complete(
    case_dir: Path = typer.Argument(..., help="Path to case directory"),
    item_id: str = typer.Argument(..., help="Work item ID"),
    note: Optional[str] = typer.Option(None, "--note", "-n", help="Completion note"),
):
    """Mark a work item as completed."""
    from ..work import WorkStorage

    if not case_dir.exists():
        console.print(f"[red]Error: Case directory not found: {case_dir}[/red]")
        raise typer.Exit(1)

    storage = WorkStorage(case_dir)
    item = storage.load_item(item_id)

    if not item:
        console.print(f"[red]Work item not found: {item_id}[/red]")
        raise typer.Exit(1)

    item.mark_completed(note)
    storage.save_item(item)

    # Update index
    index = storage.load_index()
    index.touch(f"Completed {item_id}")
    all_items = storage.load_all_items()
    index.update_stats(all_items)
    storage.save_index()

    console.print(f"[green]Completed:[/green] {item.id} - {item.title}")


@work_app.command("init")
def work_init(
    case_dir: Path = typer.Argument(..., help="Path to case directory"),
    attorney: Optional[str] = typer.Option(None, "--attorney", "-a", help="Attorney name"),
    resolution_path: Optional[str] = typer.Option(
        None,
        "--resolution", "-r",
        help="Resolution path: trial, plea, dismissal",
    ),
):
    """Initialize work items for a case."""
    from ..work import init_work_storage

    if not case_dir.exists():
        console.print(f"[red]Error: Case directory not found: {case_dir}[/red]")
        raise typer.Exit(1)

    # Load case ID from case.json if available
    case_id = case_dir.name
    case_json = case_dir / "case.json"
    if case_json.exists():
        import json
        with open(case_json) as f:
            data = json.load(f)
            case_id = data.get("case_id", case_id)

    storage = init_work_storage(case_dir, case_id)
    index = storage.load_index(case_id)

    if attorney:
        index.attorney = attorney
    if resolution_path:
        index.resolution_path = resolution_path

    index.touch("Initialized work items")
    storage.save_index()

    console.print(f"[green]Initialized work items for case:[/green] {case_id}")
    console.print(f"Work directory: {storage.work_dir}")
    if attorney:
        console.print(f"Attorney: {attorney}")
    if resolution_path:
        console.print(f"Resolution path: {resolution_path}")


@work_app.command("suggest")
def work_suggest(
    case_dir: Path = typer.Argument(..., help="Path to case directory"),
    max_suggestions: int = typer.Option(5, "--max", "-m", help="Maximum suggestions"),
    auto_create: bool = typer.Option(False, "--create", "-c", help="Auto-create all suggestions"),
    model: str = typer.Option("gemma2:2b", "--model", help="Ollama model to use"),
):
    """AI-suggest work items based on case analysis."""
    from ..work import WorkStorage, suggest_work_items, create_suggested_items
    from ..models import Case

    if not case_dir.exists():
        console.print(f"[red]Error: Case directory not found: {case_dir}[/red]")
        raise typer.Exit(1)

    case_json = case_dir / "case.json"
    if not case_json.exists():
        console.print(f"[red]Error: case.json not found in {case_dir}[/red]")
        raise typer.Exit(1)

    console.print(f"[dim]Analyzing case with {model}...[/dim]")

    case = Case.load(case_json)
    storage = WorkStorage(case_dir)

    suggestions = suggest_work_items(storage, case, max_suggestions, model)

    if not suggestions:
        console.print("[yellow]No suggestions generated. Is Ollama running?[/yellow]")
        console.print(f"[dim]Try: ollama pull {model}[/dim]")
        return

    console.print(f"\n[bold]Suggested Work Items ({len(suggestions)})[/bold]\n")

    for i, suggestion in enumerate(suggestions, 1):
        console.print(f"[cyan]{i}.[/cyan] [{suggestion.get('type', 'action')}] {suggestion.get('title', 'Untitled')}")
        console.print(f"   [dim]{suggestion.get('description', '')[:80]}...[/dim]")
        console.print(f"   Priority: {suggestion.get('priority', 'medium')}")
        console.print()

    if auto_create:
        created = create_suggested_items(storage, suggestions)
        console.print(f"[green]Created {len(created)} work items:[/green]")
        for item in created:
            console.print(f"  {item.id}: {item.title}")
    else:
        console.print("[dim]Use --create to automatically create these items[/dim]")


@work_app.command("create")
def work_create(
    case_dir: Path = typer.Argument(..., help="Path to case directory"),
    description: str = typer.Argument(..., help="Natural language description of work item"),
    model: str = typer.Option("gemma2:2b", "--model", help="Ollama model to use"),
):
    """Create work item from natural language description using AI."""
    from ..work import WorkStorage, create_work_item_from_text
    from ..models import Case

    if not case_dir.exists():
        console.print(f"[red]Error: Case directory not found: {case_dir}[/red]")
        raise typer.Exit(1)

    console.print(f"[dim]Processing with {model}...[/dim]")

    # Load case if available for context
    case = None
    case_json = case_dir / "case.json"
    if case_json.exists():
        from ..models import Case
        case = Case.load(case_json)

    storage = WorkStorage(case_dir)
    item = create_work_item_from_text(storage, description, case, model)

    if not item:
        console.print("[yellow]Failed to create work item. Is Ollama running?[/yellow]")
        console.print(f"[dim]Try: ollama pull {model}[/dim]")
        raise typer.Exit(1)

    console.print(f"[green]Created work item:[/green] {item.id}")
    console.print(f"  Title: {item.title}")
    console.print(f"  Type: {item.item_type.value}")
    console.print(f"  Priority: {item.priority.value}")
    if item.description:
        console.print(f"  Description: {item.description[:100]}...")


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

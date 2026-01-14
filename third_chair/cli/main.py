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

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
    4. Generate reports
    """
    from ..ingest import ingest_axon_package
    from ..transcription import transcribe_case
    from ..translation import translate_case

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
def version():
    """Show version information."""
    console.print("Third Chair v0.1.0")
    console.print("Legal Discovery Processing Tool")


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()

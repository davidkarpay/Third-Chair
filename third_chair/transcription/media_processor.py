"""Media processing utilities for audio/video normalization."""

import subprocess
import tempfile
from pathlib import Path
from typing import Optional


def normalize_audio(
    input_path: Path,
    output_path: Optional[Path] = None,
    sample_rate: int = 16000,
    mono: bool = True,
) -> Path:
    """
    Normalize audio/video to WAV format suitable for transcription.

    Whisper requires 16kHz mono audio. This function converts any
    audio or video file to the correct format.

    Args:
        input_path: Path to input audio/video file
        output_path: Optional output path (creates temp file if not provided)
        sample_rate: Target sample rate (default 16000 for Whisper)
        mono: Whether to convert to mono (default True)

    Returns:
        Path to normalized WAV file
    """
    input_path = Path(input_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Generate output path if not provided
    if output_path is None:
        output_path = Path(tempfile.mktemp(suffix=".wav"))
    else:
        output_path = Path(output_path)

    # Build FFmpeg command
    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output
        "-i", str(input_path),
        "-vn",  # No video
        "-acodec", "pcm_s16le",  # 16-bit PCM
        "-ar", str(sample_rate),  # Sample rate
    ]

    if mono:
        cmd.extend(["-ac", "1"])  # Mono

    cmd.append(str(output_path))

    # Run FFmpeg
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFmpeg failed: {e.stderr}")
    except FileNotFoundError:
        raise RuntimeError("FFmpeg not found. Please install FFmpeg.")

    return output_path


def get_media_duration(file_path: Path) -> Optional[float]:
    """
    Get the duration of a media file in seconds.

    Args:
        file_path: Path to media file

    Returns:
        Duration in seconds, or None if unable to determine
    """
    file_path = Path(file_path)

    if not file_path.exists():
        return None

    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return None


def get_media_info(file_path: Path) -> dict:
    """
    Get detailed information about a media file.

    Args:
        file_path: Path to media file

    Returns:
        Dict with media information
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(file_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        import json
        return json.loads(result.stdout)
    except subprocess.CalledProcessError:
        return {}


def has_audio_stream(file_path: Path) -> bool:
    """
    Check if a media file has an audio stream.

    Args:
        file_path: Path to media file

    Returns:
        True if file has audio, False otherwise
    """
    info = get_media_info(file_path)
    streams = info.get("streams", [])

    for stream in streams:
        if stream.get("codec_type") == "audio":
            return True

    return False


def extract_audio_segment(
    input_path: Path,
    output_path: Path,
    start_time: float,
    end_time: float,
    sample_rate: int = 16000,
) -> Path:
    """
    Extract a segment of audio from a media file.

    Args:
        input_path: Path to input file
        output_path: Path for output segment
        start_time: Start time in seconds
        end_time: End time in seconds
        sample_rate: Target sample rate

    Returns:
        Path to extracted segment
    """
    duration = end_time - start_time

    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(start_time),
        "-i", str(input_path),
        "-t", str(duration),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", str(sample_rate),
        "-ac", "1",
        str(output_path),
    ]

    try:
        subprocess.run(cmd, capture_output=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFmpeg segment extraction failed: {e}")

    return output_path

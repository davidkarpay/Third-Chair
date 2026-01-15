"""Integration tests for CLI commands."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from third_chair.cli.main import app


runner = CliRunner()


class TestStatusCommand:
    """Tests for the status command."""

    def test_status_valid_case(self, sample_case_dir: Path, sample_case):
        """'status' command shows case info without errors."""
        # Save the case
        sample_case.save()

        result = runner.invoke(app, ["status", str(sample_case_dir)])

        assert result.exit_code == 0
        assert "TEST-001" in result.stdout

    def test_status_missing_case_file(self, tmp_path: Path):
        """'status' on missing case.json exits with error."""
        result = runner.invoke(app, ["status", str(tmp_path)])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower() or "error" in result.stdout.lower()


class TestWorkInitCommand:
    """Tests for work init command."""

    def test_work_init_creates_directory(self, sample_case_dir: Path, sample_case):
        """'work init' creates work directory and index."""
        sample_case.save()

        result = runner.invoke(app, ["work", "init", str(sample_case_dir)])

        assert result.exit_code == 0
        assert (sample_case_dir / "work").exists()
        assert (sample_case_dir / "work" / "_index.yaml").exists()

    def test_work_init_idempotent(self, sample_case_dir: Path, sample_case):
        """'work init' is idempotent (can run multiple times)."""
        sample_case.save()

        # Run twice
        runner.invoke(app, ["work", "init", str(sample_case_dir)])
        result = runner.invoke(app, ["work", "init", str(sample_case_dir)])

        assert result.exit_code == 0


class TestWorkAddCommand:
    """Tests for work add command."""

    def test_work_add_creates_item(self, sample_case_dir: Path, sample_case):
        """'work add' creates a work item."""
        sample_case.save()
        runner.invoke(app, ["work", "init", str(sample_case_dir)])

        result = runner.invoke(app, [
            "work", "add", str(sample_case_dir),
            "--type", "investigation",
            "--title", "Interview witness",
            "--priority", "high",
        ])

        assert result.exit_code == 0
        assert "INV-0001" in result.stdout

        # Verify file was created
        assert (sample_case_dir / "work" / "INV-0001.yaml").exists()

    def test_work_add_different_types(self, sample_case_dir: Path, sample_case):
        """'work add' creates items with correct type prefixes."""
        sample_case.save()
        runner.invoke(app, ["work", "init", str(sample_case_dir)])

        # Add different types
        runner.invoke(app, [
            "work", "add", str(sample_case_dir),
            "--type", "investigation", "--title", "Investigate"
        ])
        runner.invoke(app, [
            "work", "add", str(sample_case_dir),
            "--type", "legal_question", "--title", "Research"
        ])
        runner.invoke(app, [
            "work", "add", str(sample_case_dir),
            "--type", "action", "--title", "File motion"
        ])

        assert (sample_case_dir / "work" / "INV-0001.yaml").exists()
        assert (sample_case_dir / "work" / "LEG-0001.yaml").exists()
        assert (sample_case_dir / "work" / "ACT-0001.yaml").exists()


class TestWorkListCommand:
    """Tests for work list command."""

    def test_work_list_shows_items(self, sample_case_dir: Path, sample_case):
        """'work list' shows all work items."""
        sample_case.save()
        runner.invoke(app, ["work", "init", str(sample_case_dir)])
        runner.invoke(app, [
            "work", "add", str(sample_case_dir),
            "--type", "investigation", "--title", "Test Item"
        ])

        result = runner.invoke(app, ["work", "list", str(sample_case_dir)])

        assert result.exit_code == 0
        assert "INV-0001" in result.stdout
        assert "Test Item" in result.stdout

    def test_work_list_empty(self, sample_case_dir: Path, sample_case):
        """'work list' handles empty work directory."""
        sample_case.save()
        runner.invoke(app, ["work", "init", str(sample_case_dir)])

        result = runner.invoke(app, ["work", "list", str(sample_case_dir)])

        assert result.exit_code == 0
        # Should not error, just show empty or "no items"

    def test_work_list_filter_by_status(self, sample_case_dir: Path, sample_case):
        """'work list' filters by status."""
        sample_case.save()
        runner.invoke(app, ["work", "init", str(sample_case_dir)])

        # Add items
        runner.invoke(app, [
            "work", "add", str(sample_case_dir),
            "--type", "action", "--title", "Item 1"
        ])
        runner.invoke(app, [
            "work", "add", str(sample_case_dir),
            "--type", "action", "--title", "Item 2"
        ])

        # Update one to completed
        runner.invoke(app, [
            "work", "update", str(sample_case_dir), "ACT-0001",
            "--status", "completed"
        ])

        # List pending only
        result = runner.invoke(app, [
            "work", "list", str(sample_case_dir),
            "--status", "pending"
        ])

        assert result.exit_code == 0
        assert "ACT-0002" in result.stdout
        # ACT-0001 should not appear (it's completed)


class TestWorkUpdateCommand:
    """Tests for work update command."""

    def test_work_update_changes_status(self, sample_case_dir: Path, sample_case):
        """'work update' modifies item status."""
        sample_case.save()
        runner.invoke(app, ["work", "init", str(sample_case_dir)])
        runner.invoke(app, [
            "work", "add", str(sample_case_dir),
            "--type", "action", "--title", "Test"
        ])

        result = runner.invoke(app, [
            "work", "update", str(sample_case_dir), "ACT-0001",
            "--status", "in_progress"
        ])

        assert result.exit_code == 0
        assert "in_progress" in result.stdout.lower() or "updated" in result.stdout.lower()

    def test_work_update_adds_note(self, sample_case_dir: Path, sample_case):
        """'work update' adds note to item."""
        sample_case.save()
        runner.invoke(app, ["work", "init", str(sample_case_dir)])
        runner.invoke(app, [
            "work", "add", str(sample_case_dir),
            "--type", "investigation", "--title", "Interview"
        ])

        result = runner.invoke(app, [
            "work", "update", str(sample_case_dir), "INV-0001",
            "--note", "Scheduled for Monday"
        ])

        assert result.exit_code == 0

    def test_work_update_nonexistent_item(self, sample_case_dir: Path, sample_case):
        """'work update' handles nonexistent item."""
        sample_case.save()
        runner.invoke(app, ["work", "init", str(sample_case_dir)])

        result = runner.invoke(app, [
            "work", "update", str(sample_case_dir), "NONEXISTENT-0001",
            "--status", "completed"
        ])

        assert result.exit_code == 1


class TestWorkCompleteCommand:
    """Tests for work complete command."""

    def test_work_complete_marks_item(self, sample_case_dir: Path, sample_case):
        """'work complete' marks item as completed."""
        sample_case.save()
        runner.invoke(app, ["work", "init", str(sample_case_dir)])
        runner.invoke(app, [
            "work", "add", str(sample_case_dir),
            "--type", "action", "--title", "Test"
        ])

        result = runner.invoke(app, [
            "work", "complete", str(sample_case_dir), "ACT-0001",
            "--note", "Done successfully"
        ])

        assert result.exit_code == 0
        assert "completed" in result.stdout.lower()


class TestWorkStatusCommand:
    """Tests for work status command."""

    def test_work_status_shows_summary(self, sample_case_dir: Path, sample_case):
        """'work status' shows summary of work items."""
        sample_case.save()
        runner.invoke(app, ["work", "init", str(sample_case_dir)])

        # Add some items
        runner.invoke(app, [
            "work", "add", str(sample_case_dir),
            "--type", "investigation", "--title", "Item 1"
        ])
        runner.invoke(app, [
            "work", "add", str(sample_case_dir),
            "--type", "action", "--title", "Item 2"
        ])

        result = runner.invoke(app, ["work", "status", str(sample_case_dir)])

        assert result.exit_code == 0
        # Should show stats
        assert "2" in result.stdout or "pending" in result.stdout.lower()


class TestWorkShowCommand:
    """Tests for work show command."""

    def test_work_show_displays_item(self, sample_case_dir: Path, sample_case):
        """'work show' displays item details."""
        sample_case.save()
        runner.invoke(app, ["work", "init", str(sample_case_dir)])
        runner.invoke(app, [
            "work", "add", str(sample_case_dir),
            "--type", "investigation",
            "--title", "Interview witness Maria",
            "--description", "Interview Maria Garcia about the incident",
            "--priority", "high",
        ])

        result = runner.invoke(app, ["work", "show", str(sample_case_dir), "INV-0001"])

        assert result.exit_code == 0
        assert "INV-0001" in result.stdout
        assert "Interview witness Maria" in result.stdout

    def test_work_show_nonexistent(self, sample_case_dir: Path, sample_case):
        """'work show' handles nonexistent item."""
        sample_case.save()
        runner.invoke(app, ["work", "init", str(sample_case_dir)])

        result = runner.invoke(app, ["work", "show", str(sample_case_dir), "NONEXISTENT-0001"])

        assert result.exit_code == 1

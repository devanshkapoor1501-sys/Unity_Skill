"""Phase 11 CLI routes preserve zero-side-effect planning and truthful results."""

import json

from polyforge.cli import main
from polyforge.contracts.results import Result


def test_historical_builtin_benchmark_dry_run_does_not_write(tmp_path, capsys):
    output = tmp_path / "results"
    code = main(
        [
            "benchmark",
            "run",
            "--suite",
            "benchmark_core",
            "--arm",
            "D",
            "--output",
            str(output),
            "--dry-run",
            "--json",
        ]
    )
    assert code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["data"]["dry_run"] is True
    assert not output.exists()


def test_platformer_cli_only_dispatches_typed_workspace_input(tmp_path, monkeypatch, capsys):
    from polyforge.unity import platformer

    inputs = {
        "schema_version": "1.0.0",
        "scene_id": "course",
        "seed": 42,
        "layout": "checkpoint_course_v1",
        "sprite_receipt": "runs/sprite/bindings.json",
    }
    (tmp_path / "request.json").write_text(json.dumps(inputs))
    calls = []

    def build(workspace, value, **options):
        calls.append((workspace, value, options))
        return Result(data={"dry_run": True})

    monkeypatch.setattr(platformer, "build_platformer", build)
    assert (
        main(
            [
                "platformer",
                "build",
                "--workspace",
                str(tmp_path),
                "--input",
                "request.json",
                "--dry-run",
                "--json",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["data"]["dry_run"]
    assert calls[0][1] == inputs and calls[0][2]["dry_run"] is True
    assert calls[0][2]["standalone"] is False


def test_profile_cli_dry_run_is_explicit_and_does_not_launch(tmp_path, monkeypatch, capsys):
    from polyforge.unity import performance

    calls = []

    def profile(workspace, player, *, dry_run=False):
        calls.append((workspace, player, dry_run))
        return Result(data={"dry_run": dry_run, "execution_status": "NOT_RUN"})

    monkeypatch.setattr(performance, "profile_player", profile)
    assert (
        main(
            [
                "profile-player",
                "--workspace",
                str(tmp_path),
                "--player",
                "player/arena.exe",
                "--dry-run",
                "--json",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["data"]["execution_status"] == "NOT_RUN"
    assert calls[0][2] is True

# tests/test_interface/test_cli.py
from typer.testing import CliRunner
from interface.cli.main import app
from unittest.mock import patch

runner = CliRunner()

def test_list_no_episodes():
    with patch("interface.cli.commands.EpisodesRepository") as mock_repo:
        mock_repo.return_value.list_all.return_value = []
        result = runner.invoke(app, ["episode", "list"])
    assert result.exit_code == 0
    assert "No episodes found" in result.output
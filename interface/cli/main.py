import typer
from interface.cli import commands

app = typer.Typer(
    name="transcrire",
    help="Transcrire — podcast episode repurposing tool.",
    no_args_is_help=True,
)

app.add_typer(commands.app, name="episode")


def run():
    app()


if __name__ == "__main__":
    run()
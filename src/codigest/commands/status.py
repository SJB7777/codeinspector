from pathlib import Path

import typer
from rich.console import Console

from ..core import common

app: typer.Typer = typer.Typer()
console: Console = Console()

@app.callback(invoke_without_command=True)
def handle(
    target: Path = typer.Argument(Path.cwd(), help="Target directory"),
):
    ctx: common.ProjectContext = common.ProjectContext(target)
    root_path: Path = ctx.root_path

    
import typer

from dawri import ingest, load

app = typer.Typer()


@app.command("load")
def load_() -> None:
    load.main()


@app.command("ingest")
def ingest_(season: ingest.Season) -> None:
    ingest.main(season.value)

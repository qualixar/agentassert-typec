from __future__ import annotations

import sys
from pathlib import Path

import click
import uvicorn


@click.group()
def cli():
    pass


@cli.command()
@click.option("--contract", "-c", required=True, help="Path to contract YAML")
@click.option("--port", "-p", default=9000, help="Port to listen on")
@click.option("--host", "-h", default="127.0.0.1", help="Host to bind to")
def start(contract: str, port: int, host: str) -> None:
    contract_path = Path(contract).resolve()
    if not contract_path.exists():
        click.echo(f"Error: Contract file not found: {contract_path}", err=True)
        sys.exit(1)

    click.echo("AgentAssert Type-C Proxy v0.4.2")
    click.echo(f"Contract: {contract_path}")
    click.echo(f"Listening on http://{host}:{port}")
    click.echo()
    click.echo("Set these env vars in your agent environment:")
    click.echo(f"  export ANTHROPIC_BASE_URL=http://{host}:{port}/anthropic")
    click.echo(f"  export OPENAI_BASE_URL=http://{host}:{port}/openai")
    click.echo()
    if sys.stdout.isatty():
        click.echo("⭐  If AgentAssert Type-C is useful, please star the repo:")
        click.echo("    https://github.com/qualixar/agentassert-typec")
        click.echo()

    uvicorn.run(
        "agentassert_typec_proxy.server:create_app",
        host=host,
        port=port,
        factory=True,
        kwargs={"contract_path": str(contract_path)},
        loop="uvloop",
        log_level="info",
    )


@cli.command()
@click.option("--port", "-p", default=9000, help="Port of running proxy")
@click.option("--host", "-h", default="127.0.0.1", help="Host of running proxy")
def status(port: int, host: str) -> None:
    import httpx
    try:
        resp = httpx.get(f"http://{host}:{port}/health", timeout=2.0)
        click.echo(resp.text)
    except Exception as e:
        click.echo(f"Proxy not reachable: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()

import click
from flask import Flask
from werkzeug.security import generate_password_hash

from .models import User, db


def register_cli_commands(app: Flask) -> None:
    """Register maintenance commands on the Flask application."""

    @app.cli.command("create-admin")
    @click.option("--username", prompt=True)
    @click.option(
        "--password",
        prompt=True,
        hide_input=True,
        confirmation_prompt=True,
    )
    @click.option("--realname", prompt="Anzeigename")
    def create_admin(username: str, password: str, realname: str) -> None:
        """Create the first local administrator account."""
        if User.query.filter_by(username=username).first():
            raise click.ClickException(
                f"Der Benutzername '{username}' ist bereits vergeben."
            )

        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            role="admin",
            realname=realname,
        )
        db.session.add(user)
        db.session.commit()
        click.echo(f"Administrator '{username}' wurde angelegt.")

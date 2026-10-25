from app.models import User


def test_create_admin_command(app):
    runner = app.test_cli_runner()

    result = runner.invoke(
        args=[
            "create-admin",
            "--username",
            "local-admin",
            "--password",
            "secret-password",
            "--realname",
            "Lokale Administration",
        ]
    )

    assert result.exit_code == 0
    assert "Administrator 'local-admin' wurde angelegt." in result.output

    with app.app_context():
        user = User.query.filter_by(username="local-admin").one()
        assert user.role == "admin"


def test_create_admin_command_rejects_duplicate_username(app):
    runner = app.test_cli_runner()
    args = [
        "create-admin",
        "--username",
        "local-admin",
        "--password",
        "secret-password",
        "--realname",
        "Lokale Administration",
    ]

    assert runner.invoke(args=args).exit_code == 0
    duplicate_result = runner.invoke(args=args)

    assert duplicate_result.exit_code == 1
    assert "ist bereits vergeben" in duplicate_result.output

# Contributing to PlexPipe

Thank you for your interest in PlexPipe. Bug reports, questions and ideas are welcome on the [issue tracker](https://github.com/plexpipe/plex-pipe/issues); please open an issue before starting larger changes, so we can agree on the approach first.

## Development setup

PlexPipe uses [uv](https://docs.astral.sh/uv/) for environments and supports Python 3.12–3.14.

```bash
git clone https://github.com/plexpipe/plex-pipe.git
cd plex-pipe
uv sync --extra all --group dev
uv run pre-commit install
```

`--group dev` adds the test, lint and documentation tools. On a machine with an NVIDIA GPU, use `--extra all-cuda` instead of `--extra all` (see the [installation guide](https://plexpipe.github.io/plex-pipe/latest/usage/installation/)).

## Checks

Run these before opening a pull request:

```bash
uv run pytest                      # tests
uv run pre-commit run --all-files  # ruff, black, mypy and file checks
uv run mkdocs build --strict       # documentation, if you changed docs/ or docstrings
```

GitHub runs the tests on Linux, macOS and Windows with Python 3.12–3.14 for every pull request.

## Pull requests

- Work on a branch and open a pull request against `main`.
- Keep a pull request to one topic, and add or update tests for changed behaviour.
- Update the documentation in `docs/` when you change what users see.

## Changing the config file format

The config YAML file is versioned (`schema_version`). If your change adds, renames, moves or removes a config key, follow the rules at the top of `src/plex_pipe/config/config_migrations.py` (new optional key: bump the MINOR version; breaking change: bump the MAJOR version and add a migration), and add an entry to `docs/configuration/schema_changelog.md`.

## License

By contributing, you agree that your contributions are licensed under the project's [BSD-3-Clause license](LICENSE).

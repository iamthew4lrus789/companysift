"""
Main CLI entry point for Company Website Discovery Tool (Click implementation).
"""

import click
from typing import Optional

from src.cli.commands_click import process_companies, manage_blocklist, config_commands


@click.group()
@click.version_option(version='1.0.0', message='Company Website Discovery Tool v1.0.0')
def main():
    """Company Website Discovery Tool - Find company websites from UK registry data."""
    pass


# Add commands
main.add_command(process_companies)
main.add_command(manage_blocklist)
main.add_command(config_commands)


if __name__ == '__main__':
    main()
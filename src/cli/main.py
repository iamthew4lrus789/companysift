"""Main CLI entry point for Company Website Discovery Tool."""

import argparse
import sys
from pathlib import Path
from typing import Optional

from core.config import Config
from utils.logging_config import setup_logging, get_logger


def create_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser.
    
    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog='company-sift',
        description='Automatically discover websites for UK companies from registry data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process companies from CSV file
  company-sift process input.csv -o output.csv
  
  # Resume interrupted processing
  company-sift process input.csv -o output.csv --resume
  
  # Add domain to blocklist
  company-sift blocklist add example-aggregator.com
  
  # List blocked domains
  company-sift blocklist list
  
  # Use custom configuration
  company-sift process input.csv -o output.csv -c custom-config.yaml
        """
    )
    
    # Global options
    parser.add_argument(
        '-c', '--config',
        type=str,
        default='config/config.yaml',
        help='Path to configuration file (default: config/config.yaml)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Process command
    process_parser = subparsers.add_parser(
        'process',
        help='Process companies from CSV file to discover websites'
    )
    
    process_parser.add_argument(
        'input',
        type=str,
        help='Path to input CSV file with company data'
    )
    
    process_parser.add_argument(
        '-o', '--output',
        type=str,
        required=True,
        help='Path to output CSV file for results'
    )
    
    process_parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume from last checkpoint (if available)'
    )
    
    process_parser.add_argument(
        '--restart',
        action='store_true',
        help='Restart from beginning (ignore checkpoint)'
    )
    
    # Blocklist management command
    blocklist_parser = subparsers.add_parser(
        'blocklist',
        help='Manage aggregator site blocklist'
    )
    
    blocklist_subparsers = blocklist_parser.add_subparsers(dest='blocklist_action')
    
    # Add to blocklist
    add_parser = blocklist_subparsers.add_parser('add', help='Add domain to blocklist')
    add_parser.add_argument('domain', help='Domain to add to blocklist')
    
    # Remove from blocklist
    remove_parser = blocklist_subparsers.add_parser('remove', help='Remove domain from blocklist')
    remove_parser.add_argument('domain', help='Domain to remove from blocklist')
    
    # List blocklist
    list_parser = blocklist_subparsers.add_parser('list', help='List blocked domains')
    
    return parser


def validate_args(args: argparse.Namespace) -> bool:
    """Validate command line arguments.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        True if arguments are valid
        
    Raises:
        ValueError: If arguments are invalid
    """
    # Validate config file exists
    config_path = Path(args.config)
    if not config_path.exists():
        raise ValueError(f"Configuration file not found: {args.config}")
    
    if args.command == 'process':
        # Validate input file exists
        input_path = Path(args.input)
        if not input_path.exists():
            raise ValueError(f"Input file not found: {args.input}")
        
        if not input_path.suffix.lower() == '.csv':
            raise ValueError(f"Input file must be CSV format: {args.input}")
        
        # Validate output path
        output_path = Path(args.output)
        if not output_path.suffix.lower() == '.csv':
            raise ValueError(f"Output file must be CSV format: {args.output}")
        
        # Check for conflicting resume/restart options
        if args.resume and args.restart:
            raise ValueError("Cannot use both --resume and --restart options")
    
    return True


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        # Validate arguments
        validate_args(args)
        
        # Load configuration
        config = Config(args.config)
        config.validate()
        
        # Set up logging
        logger = setup_logging(config.logging_config)
        if args.verbose:
            logger.setLevel('DEBUG')
        
        logger.info(f"Starting Company Website Discovery Tool - Command: {args.command}")
        
        # Route to appropriate command handler
        if args.command == 'process':
            from cli.commands import process_companies
            process_companies(args, config, logger)
        
        elif args.command == 'blocklist':
            from cli.commands import manage_blocklist
            manage_blocklist(args, config, logger)
        
        logger.info("Command completed successfully")
        
    except KeyboardInterrupt:
        print("\nOperation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
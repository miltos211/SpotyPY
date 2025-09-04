"""
Shared CLI utilities for spotifyToYT project.
Reduces code duplication across scripts.
"""
import argparse
import sys
from pathlib import Path
from typing import Optional, Callable, Any

def add_common_arguments(parser: argparse.ArgumentParser, script_type: str = "general"):
    """
    Add common CLI arguments that are shared across scripts.
    
    Args:
        parser: ArgumentParser instance to add arguments to
        script_type: Type of script ("input", "output", "io") to determine which args to add
    """
    
    if script_type in ["input", "io"]:
        parser.add_argument('-i', '--input', type=str,
                            help='Input file path')
    
    if script_type in ["output", "io"]:
        parser.add_argument('-o', '--output', type=str,
                            help='Output file/directory path')
    
    # Quiet flag for all scripts
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Suppress verbose output')
    
    # Debug flag for all scripts
    parser.add_argument('--debug', action='store_true',
                        help='Enable detailed debug logging (default: INFO level)')
    
    # Threading support for applicable scripts
    if script_type in ["threaded", "io"]:
        parser.add_argument('-t', '--threads', type=int, default=0,
                            help='Number of concurrent threads (0=sequential, default: 0)')

def validate_thread_count(thread_count: int, max_threads: int = 8) -> tuple[bool, str]:
    """
    Validate thread count argument.
    
    Args:
        thread_count: Number of threads requested
        max_threads: Maximum allowed threads
    
    Returns:
        (is_valid, error_message)
    """
    if thread_count < 0 or thread_count > max_threads:
        return False, f"Thread count must be between 0-{max_threads} (0 = sequential)"
    return True, ""

def setup_script_environment(script_name: str, args: argparse.Namespace, 
                            logger_factory: Callable = None) -> Any:
    """
    Common script setup: logging, error handling, etc.
    
    Args:
        script_name: Name of the script for logging
        args: Parsed arguments
        logger_factory: Function to create logger (e.g., create_logger)
    
    Returns:
        Logger instance or None
    """
    if logger_factory:
        logger = logger_factory(script_name, quiet=getattr(args, 'quiet', False))
        logger.info(f"{script_name} started")
        logger.debug(f"Arguments: {vars(args)}")
        return logger
    return None

def handle_script_exit(logger: Any, success: bool, script_name: str = "Script"):
    """
    Common script exit handling.
    
    Args:
        logger: Logger instance
        success: Whether script completed successfully
        script_name: Name of script for logging
    """
    if logger:
        status = "success" if success else "failure"
        logger.info(f"{script_name} completed: {status}")
    
    sys.exit(0 if success else 1)

def create_standard_parser(description: str, epilog: str = None) -> argparse.ArgumentParser:
    """
    Create a standardized ArgumentParser with consistent formatting.
    
    Args:
        description: Description of the script
        epilog: Examples and additional help text
    
    Returns:
        Configured ArgumentParser
    """
    return argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog
    )

def prompt_user_choice(prompt: str, valid_choices: list, default: str = None) -> str:
    """
    Prompt user for input with validation.
    
    Args:
        prompt: Prompt message
        valid_choices: List of valid choices
        default: Default choice if user presses enter
    
    Returns:
        User's choice
    """
    while True:
        if default:
            user_input = input(f"{prompt} (default: {default}): ").strip()
            if not user_input:
                return default
        else:
            user_input = input(f"{prompt}: ").strip()
        
        if user_input in valid_choices:
            return user_input
        
        print(f"Invalid choice. Please choose from: {', '.join(valid_choices)}")

def prompt_number_range(prompt: str, min_val: int, max_val: int, default: int = None) -> int:
    """
    Prompt user for a number within a range.
    
    Args:
        prompt: Prompt message
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        default: Default value if user presses enter
    
    Returns:
        User's number choice
    """
    while True:
        try:
            if default is not None:
                user_input = input(f"{prompt} ({min_val}-{max_val}, default {default}): ").strip()
                if not user_input:
                    return default
            else:
                user_input = input(f"{prompt} ({min_val}-{max_val}): ").strip()
            
            value = int(user_input)
            if min_val <= value <= max_val:
                return value
            
            print(f"Please enter a number between {min_val} and {max_val}")
            
        except ValueError:
            print("Please enter a valid number")

class CLIContext:
    """
    Context manager for consistent CLI script structure.
    Handles setup, error handling, and cleanup.
    """
    
    def __init__(self, script_name: str, args: argparse.Namespace, 
                 logger_factory: Callable = None):
        self.script_name = script_name
        self.args = args
        self.logger = None
        self.success = False
        
        if logger_factory:
            self.logger = logger_factory(script_name, quiet=getattr(args, 'quiet', False))
    
    def __enter__(self):
        if self.logger:
            self.logger.info(f"{self.script_name} started")
            self.logger.debug(f"Arguments: {vars(self.args)}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is KeyboardInterrupt:
            if self.logger:
                self.logger.info("Script interrupted by user")
            sys.exit(1)
        elif exc_type is not None:
            if self.logger:
                self.logger.error(f"Unexpected error: {exc_val}")
            sys.exit(1)
        else:
            if self.logger:
                status = "success" if self.success else "failure"
                self.logger.info(f"{self.script_name} completed: {status}")
            sys.exit(0 if self.success else 1)
    
    def set_success(self, success: bool = True):
        """Mark the script as successful or failed"""
        self.success = success

# Common argument patterns for easy reuse
COMMON_EPILOGS = {
    "exporter": '''
Examples:
  {script} -l                                 # List items
  {script} -p "Item Name" -o output.json     # Export by name
  {script} -p 1 -o output.json               # Export by index
''',
    
    "processor": '''
Examples:
  {script} -i input.json -o output.json      # Sequential processing  
  {script} -i input.json -t 5                # With 5 threads
  {script} -i input.json -t 3 -q             # Quiet mode
''',
    
    "downloader": '''
Examples:
  {script} -i input.json -o output_dir/      # Sequential download
  {script} -i input.json -o output_dir/ -t 5 # With 5 threads  
  {script} -i input.json -o output_dir/ -q   # Quiet mode
'''
}
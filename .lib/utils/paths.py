"""
Centralized path handling utilities for spotifyToYT project.
Provides consistent, robust path operations across all scripts.
"""
import os
import sys
from pathlib import Path
from typing import Union, Optional

def resolve_path(path_input: Union[str, Path], must_exist: bool = False, 
                create_parent: bool = False) -> Optional[Path]:
    """
    Resolve and validate a path with comprehensive error handling.
    
    Args:
        path_input: String or Path object to resolve
        must_exist: If True, path must exist or returns None
        create_parent: If True, create parent directories if they don't exist
    
    Returns:
        Resolved Path object or None if invalid/doesn't exist
    """
    if not path_input:
        return None
    
    try:
        # Convert to Path and resolve (handles ~, .., relative paths)
        path = Path(path_input).expanduser().resolve()
        
        # Check existence if required
        if must_exist and not path.exists():
            return None
        
        # Create parent directories if requested
        if create_parent and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        
        return path
        
    except (OSError, ValueError, RuntimeError) as e:
        # Handle invalid paths, permission errors, etc.
        return None

def validate_input_file(path_input: Union[str, Path], extensions: list = None) -> tuple[bool, Optional[Path], str]:
    """
    Validate an input file path.
    
    Args:
        path_input: File path to validate
        extensions: List of allowed extensions (e.g., ['.json', '.txt'])
    
    Returns:
        (is_valid, resolved_path, error_message)
    """
    if not path_input:
        return False, None, "Path cannot be empty"
    
    path = resolve_path(path_input, must_exist=True)
    if not path:
        return False, None, f"File not found: {path_input}"
    
    if not path.is_file():
        return False, None, f"Path is not a file: {path}"
    
    if extensions:
        if path.suffix.lower() not in [ext.lower() for ext in extensions]:
            return False, None, f"File must have one of these extensions: {extensions}"
    
    # Check if file is readable
    try:
        with path.open('r', encoding='utf-8') as f:
            f.read(1)  # Try to read one character
    except (PermissionError, UnicodeDecodeError, OSError) as e:
        return False, None, f"Cannot read file: {e}"
    
    return True, path, ""

def validate_output_file(path_input: Union[str, Path], create_parent: bool = True) -> tuple[bool, Optional[Path], str]:
    """
    Validate an output file path.
    
    Args:
        path_input: Output file path to validate
        create_parent: If True, create parent directories
    
    Returns:
        (is_valid, resolved_path, error_message)
    """
    if not path_input:
        return False, None, "Output path cannot be empty"
    
    path = resolve_path(path_input, create_parent=create_parent)
    if not path:
        return False, None, f"Invalid output path: {path_input}"
    
    # Check if parent directory exists or can be created
    if not path.parent.exists():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as e:
            return False, None, f"Cannot create output directory: {e}"
    
    # Check if we can write to the directory
    try:
        # Try creating a temporary file in the directory
        temp_file = path.parent / f".test_write_{os.getpid()}"
        temp_file.touch()
        temp_file.unlink()
    except (PermissionError, OSError) as e:
        return False, None, f"Cannot write to output directory: {e}"
    
    # Warn if file exists (but don't fail)
    if path.exists():
        # This is just a warning, not an error
        pass
    
    return True, path, ""

def validate_directory(path_input: Union[str, Path], create: bool = True, 
                      must_exist: bool = False) -> tuple[bool, Optional[Path], str]:
    """
    Validate a directory path.
    
    Args:
        path_input: Directory path to validate
        create: If True, create directory if it doesn't exist
        must_exist: If True, directory must already exist
    
    Returns:
        (is_valid, resolved_path, error_message)
    """
    if not path_input:
        return False, None, "Directory path cannot be empty"
    
    path = resolve_path(path_input)
    if not path:
        return False, None, f"Invalid directory path: {path_input}"
    
    # Check existence
    if path.exists():
        if not path.is_dir():
            return False, None, f"Path exists but is not a directory: {path}"
    else:
        if must_exist:
            return False, None, f"Directory does not exist: {path}"
        
        if create:
            try:
                path.mkdir(parents=True, exist_ok=True)
            except (PermissionError, OSError) as e:
                return False, None, f"Cannot create directory: {e}"
    
    # Check if directory is writable
    try:
        temp_file = path / f".test_write_{os.getpid()}"
        temp_file.touch()
        temp_file.unlink()
    except (PermissionError, OSError) as e:
        return False, None, f"Directory is not writable: {e}"
    
    return True, path, ""

def safe_filename(filename: str, max_length: int = 255) -> str:
    """
    Convert a string to a safe filename by removing/replacing problematic characters.
    
    Args:
        filename: Original filename
        max_length: Maximum length for the filename
    
    Returns:
        Safe filename string
    """
    if not filename:
        return "unnamed_file"
    
    # Remove or replace problematic characters
    unsafe_chars = '<>:"/\\|?*'
    safe_name = filename
    
    for char in unsafe_chars:
        safe_name = safe_name.replace(char, '_')
    
    # Remove control characters
    safe_name = ''.join(char for char in safe_name if ord(char) >= 32)
    
    # Trim whitespace and dots (problematic on Windows)
    safe_name = safe_name.strip(' .')
    
    # Ensure not empty
    if not safe_name:
        safe_name = "unnamed_file"
    
    # Truncate if too long, keeping extension if possible
    if len(safe_name) > max_length:
        if '.' in safe_name:
            name, ext = safe_name.rsplit('.', 1)
            max_name_length = max_length - len(ext) - 1
            safe_name = name[:max_name_length] + '.' + ext
        else:
            safe_name = safe_name[:max_length]
    
    return safe_name

def get_unique_filename(base_path: Union[str, Path], extension: str = "") -> Path:
    """
    Generate a unique filename by adding numbers if the file already exists.
    
    Args:
        base_path: Base path for the file
        extension: File extension (with or without dot)
    
    Returns:
        Path object with unique filename
    """
    base_path = Path(base_path)
    
    # Ensure extension starts with dot
    if extension and not extension.startswith('.'):
        extension = '.' + extension
    
    # Start with original name
    counter = 0
    while True:
        if counter == 0:
            candidate = base_path.with_suffix(extension) if extension else base_path
        else:
            stem = base_path.stem
            candidate = base_path.parent / f"{stem}_{counter}{extension}"
        
        if not candidate.exists():
            return candidate
        
        counter += 1
        
        # Prevent infinite loop
        if counter > 9999:
            raise RuntimeError(f"Cannot generate unique filename for {base_path}")

class PathValidator:
    """
    Context manager for validating multiple paths with consistent error reporting.
    """
    
    def __init__(self, logger=None):
        self.logger = logger
        self.errors = []
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    
    def validate_input(self, path: Union[str, Path], name: str = "input file", 
                      extensions: list = None) -> Optional[Path]:
        """Validate input file and track errors"""
        is_valid, resolved_path, error = validate_input_file(path, extensions)
        
        if not is_valid:
            error_msg = f"Invalid {name}: {error}"
            self.errors.append(error_msg)
            if self.logger:
                self.logger.error(error_msg)
            return None
        
        if self.logger:
            self.logger.debug(f"Validated {name}: {resolved_path}")
        
        return resolved_path
    
    def validate_output(self, path: Union[str, Path], name: str = "output file") -> Optional[Path]:
        """Validate output file and track errors"""
        is_valid, resolved_path, error = validate_output_file(path)
        
        if not is_valid:
            error_msg = f"Invalid {name}: {error}"
            self.errors.append(error_msg)
            if self.logger:
                self.logger.error(error_msg)
            return None
        
        if self.logger:
            self.logger.debug(f"Validated {name}: {resolved_path}")
        
        return resolved_path
    
    def validate_dir(self, path: Union[str, Path], name: str = "directory", 
                    create: bool = True) -> Optional[Path]:
        """Validate directory and track errors"""
        is_valid, resolved_path, error = validate_directory(path, create=create)
        
        if not is_valid:
            error_msg = f"Invalid {name}: {error}"
            self.errors.append(error_msg)
            if self.logger:
                self.logger.error(error_msg)
            return None
        
        if self.logger:
            self.logger.debug(f"Validated {name}: {resolved_path}")
        
        return resolved_path
    
    def has_errors(self) -> bool:
        """Check if any validation errors occurred"""
        return len(self.errors) > 0
    
    def get_errors(self) -> list:
        """Get list of all validation errors"""
        return self.errors.copy()
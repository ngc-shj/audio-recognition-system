#!/usr/bin/env python3
"""
Script to convert print() statements to logger calls in Python files.
"""

import re
import sys
from pathlib import Path


def convert_file(file_path: Path) -> bool:
    """
    Convert print statements to logger calls in a single file.

    Returns:
        True if file was modified, False otherwise
    """
    content = file_path.read_text(encoding='utf-8')
    original_content = content

    # Check if logging is already imported
    has_logger_import = 'from utils.logger import' in content or 'import utils.logger' in content
    has_logger_setup = 'logger = setup_logger' in content or 'logger = get_logger' in content

    if not has_logger_import:
        # Add import after other imports
        import_match = re.search(r'(from\s+\w+.*?import.*?\n)+', content)
        if import_match:
            insert_pos = import_match.end()
            content = (content[:insert_pos] +
                      '\n# Logging\nfrom utils.logger import setup_logger\n' +
                      content[insert_pos:])

    if not has_logger_setup:
        # Add logger setup after imports, before first class/function
        class_or_func_match = re.search(r'\n(class |def |async def )', content)
        if class_or_func_match:
            insert_pos = class_or_func_match.start()
            content = (content[:insert_pos] +
                      '\n# Setup logger\nlogger = setup_logger(__name__)\n' +
                      content[insert_pos:])

    # Replace print statements with appropriate logger calls
    # Error patterns
    content = re.sub(
        r'print\(f?"?エラー:',
        'logger.error(f"',
        content
    )
    content = re.sub(
        r'print\(f?"?Error:',
        'logger.error(f"',
        content
    )
    content = re.sub(
        r'print\(f?"?WARNING:',
        'logger.warning(f"',
        content
    )
    content = re.sub(
        r'print\(f?"?Warning:',
        'logger.warning(f"',
        content
    )

    # Regular print statements (default to logger.info)
    content = re.sub(
        r'(\s+)print\(f"',
        r'\1logger.info(f"',
        content
    )
    content = re.sub(
        r'(\s+)print\("',
        r'\1logger.info("',
        content
    )
    content = re.sub(
        r'(\s+)print\(\'',
        r'\1logger.info(\'',
        content
    )

    # Handle print with format strings and variables
    content = re.sub(
        r'(\s+)print\(([^)]+)\)',
        r'\1logger.info(\2)',
        content
    )

    if content != original_content:
        file_path.write_text(content, encoding='utf-8')
        return True
    return False


def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python convert_print_to_logger.py <file_or_directory>")
        sys.exit(1)

    target = Path(sys.argv[1])

    if target.is_file():
        files = [target]
    elif target.is_directory():
        files = list(target.rglob('*.py'))
    else:
        print(f"Error: {target} is not a file or directory")
        sys.exit(1)

    modified_count = 0
    for file_path in files:
        # Skip this script itself and __pycache__
        if 'convert_print_to_logger.py' in str(file_path) or '__pycache__' in str(file_path):
            continue

        try:
            if convert_file(file_path):
                print(f"Converted: {file_path}")
                modified_count += 1
        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    print(f"\nTotal files modified: {modified_count}")


if __name__ == '__main__':
    main()

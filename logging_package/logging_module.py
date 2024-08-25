"""
logging_module

This module configures the logging setup for the application. It sets up the logging
format, level, and file handling to capture and record log messages.

Dependencies:
- logging: Provides the logging functionality for tracking application events.

Configuration:
- Logging Level: DEBUG - Logs all messages of level DEBUG and above.
- Format: Includes timestamp, log level, and message.
- File Handling: Appends log messages to 'main.log'.

Example Usage:
- This configuration should be imported and used across the application to ensure
  consistent logging practices.
"""

import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    filemode='a', filename='main.log')
"""
Configures the logging settings for the application.

Sets up logging to capture messages at DEBUG level and above. The log messages
are formatted to include the timestamp, log level, and message content. The
log messages are appended to the 'main.log' file.

Configuration:
- Level: DEBUG - Captures all log messages with severity DEBUG and above.
- Format: The log messages include the timestamp, log level, and the actual message.
- File Handling: Appends messages to 'main.log', creating the file if it does not exist.
"""

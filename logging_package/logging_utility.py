"""
Logging Utilities Module

This module provides utility functions for logging informational, error, and debug messages
using a centralized logging setup.

Functions:
    log_info(message): Logs an informational message.
    log_error(message): Logs an error message.
    log_debug(message): Logs a debug message.
"""

# Local imports
from logging_package.logging_module import logging

LOG_SWITCH = True


def log_info(message):
    """
    Logs an informational message.

    :param message: Message to log.
    :return: None
    """
    if LOG_SWITCH:
        logging.info(message)


def log_error(message):
    """
    Logs an error message.

    :param message: Message to log.
    :return: None
    """
    if LOG_SWITCH:
        logging.error(message)


def log_debug(message):
    """
    Logs a debug message.

    :param message: Message to log.
    :return: None
    """
    if LOG_SWITCH:
        logging.debug(message)


def log_warning(message):
    """
    Logs a warning message.

    :param message: Message to log.
    :return: None
    """
    if LOG_SWITCH:
        logging.warning(message)

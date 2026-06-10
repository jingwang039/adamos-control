"""Shared test utilities used across all test modules."""

import logging

from src.Thorlabs_PTC1_Breadboard import thorlabs_ptc1
from src.simulator import MockPTC1Serial


def make_logger():
    logger = logging.getLogger("test")
    logger.handlers = []
    logger.addHandler(logging.NullHandler())
    return logger


def make_plate(logger=None, **kwargs):
    """Return a driver instance wired to a fresh MockPTC1Serial."""
    return thorlabs_ptc1(
        port="SIM",
        logger=logger or make_logger(),
        ser=MockPTC1Serial(),
        **kwargs,
    )

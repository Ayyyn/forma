"""Normalize malformed-envelope failures at the public contract boundary."""
import xml.etree.ElementTree as ET
from bugproof_pilot_v2.adapter import decode as original_decode


def decode(message):
    try:
        return original_decode(message)
    except ET.ParseError as error:
        raise ValueError('Malformed public contract XML') from error

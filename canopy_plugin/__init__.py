"""
Canopy Plugin Python Implementation

A Python implementation of the Canopy blockchain plugin that implements
"send" transaction functionality with modern Python architecture.
"""

__version__ = "1.0.0"
__author__ = "Canopy Team"
__email__ = "team@canopy.com"
__description__ = "Python implementation of the Canopy blockchain plugin"

# Public API exports
from .config import Config
from .contract import Contract
from .errors import PluginError
from .socket_client import SocketClient

__all__ = [
    "Config",
    "Contract", 
    "PluginError",
    "SocketClient",
]
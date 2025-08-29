"""
State key generation functions for the Canopy blockchain plugin.

Provides functions for generating state database keys with proper prefixes.
"""

from typing import Union
from .proto_utils import join_len_prefix, format_uint64


# State key prefixes
ACCOUNT_PREFIX = b'\x01'  # store key prefix for accounts
POOL_PREFIX = b'\x02'     # store key prefix for pools
PARAMS_PREFIX = b'\x07'   # store key prefix for governance parameters

# Type definitions
Address = Union[bytes, str]
ChainId = Union[int, str]
Amount = Union[int, str]


def key_for_account(address: Address) -> bytes:
    """
    Generate state database key for an account.
    
    Args:
        address: Account address (must be 20 bytes when converted to bytes)
        
    Returns:
        State key bytes
        
    Raises:
        ValueError: If address is invalid
    """
    address_bytes = address if isinstance(address, bytes) else address.encode()
    return join_len_prefix(ACCOUNT_PREFIX, address_bytes)


def key_for_fee_params() -> bytes:
    """
    Generate state database key for governance controlled fee parameters.
    
    Returns:
        Fee parameters key bytes
    """
    suffix = b'/f/'
    return join_len_prefix(PARAMS_PREFIX, suffix)


def key_for_fee_pool(chain_id: ChainId) -> bytes:
    """
    Generate state database key for fee pool.
    
    Args:
        chain_id: Chain identifier
        
    Returns:
        Fee pool key bytes
    """
    chain_id_bytes = format_uint64(chain_id)
    return join_len_prefix(POOL_PREFIX, chain_id_bytes)


def validate_address(address: Address) -> bool:
    """
    Validate that an address is exactly 20 bytes.
    Used in transaction validation.
    
    Args:
        address: Address to validate
        
    Returns:
        True if address is valid (exactly 20 bytes)
    """
    try:
        if isinstance(address, str):
            # Handle hex strings
            if address.startswith('0x'):
                address_bytes = bytes.fromhex(address[2:])
            else:
                address_bytes = address.encode()
        else:
            address_bytes = address
        
        return len(address_bytes) == 20
    except Exception:
        return False


def validate_amount(amount: Amount) -> bool:
    """
    Validate that an amount is greater than 0.
    Used in transaction validation.
    
    Args:
        amount: Amount to validate
        
    Returns:
        True if amount is valid (greater than 0)
    """
    try:
        if isinstance(amount, str):
            amount_int = int(amount)
        else:
            amount_int = amount
        
        return isinstance(amount_int, int) and amount_int > 0
    except (ValueError, TypeError):
        return False


def normalize_address(address: Address) -> bytes:
    """
    Convert various address formats to bytes.
    
    Args:
        address: Address in various formats
        
    Returns:
        Bytes representation of the address
        
    Raises:
        ValueError: If address cannot be converted or is invalid length
    """
    if not validate_address(address):
        raise ValueError("Invalid address: must be exactly 20 bytes")
    
    if isinstance(address, str):
        if address.startswith('0x'):
            return bytes.fromhex(address[2:])
        else:
            return address.encode()
    
    return address


def normalize_amount(amount: Amount) -> int:
    """
    Convert various amount formats to int for arithmetic.
    
    Args:
        amount: Amount in various formats
        
    Returns:
        Int representation of the amount
        
    Raises:
        ValueError: If amount cannot be converted or is invalid
    """
    if not validate_amount(amount):
        raise ValueError("Invalid amount: must be greater than 0")
    
    if isinstance(amount, str):
        return int(amount)
    
    return amount
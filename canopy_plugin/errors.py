"""
Error handling for the Canopy blockchain plugin.

Provides standardized error codes and messages for consistent error handling.
"""

from typing import Union, Dict, Any


DEFAULT_MODULE = "plugin"


class PluginErrorCode:
    """Error code constants for plugin errors."""
    PLUGIN_TIMEOUT = 1
    MARSHAL = 2
    UNMARSHAL = 3
    FAILED_PLUGIN_READ = 4
    FAILED_PLUGIN_WRITE = 5
    INVALID_PLUGIN_RESP_ID = 6
    UNEXPECTED_FSM_TO_PLUGIN = 7
    INVALID_FSM_TO_PLUGIN_MESSAGE = 8
    INSUFFICIENT_FUNDS = 9
    FROM_ANY = 10
    INVALID_MESSAGE_CAST = 11
    INVALID_ADDRESS = 12
    INVALID_AMOUNT = 13
    TX_FEE_BELOW_STATE_LIMIT = 14


class PluginError(Exception):
    """
    Plugin Error class for blockchain plugin errors.
    
    Example:
        error = PluginError(1, 'auth', 'Authentication failed')
        print(str(error))  # Formatted error string
        proto_error = error.to_proto_error()  # For FSM communication
    """
    
    def __init__(self, code: int, module: str, message: str):
        """
        Initialize PluginError.
        
        Args:
            code: Numeric error code
            module: Module name where error occurred
            message: Human-readable error message
        """
        super().__init__(message)
        self.code = code
        self.module = module
        self.msg = message
    
    def __str__(self) -> str:
        """
        Format error string for display.
        
        Returns:
            Formatted error string with module, code, and message
        """
        return f"\nModule:  {self.module}\nCode:    {self.code}\nMessage: {self.msg}"
    
    def to_proto_error(self) -> Dict[str, Any]:
        """
        Convert to protobuf error format for FSM communication.
        
        Returns:
            Dict compatible with protobuf error message format
        """
        return {
            "code": self.code,
            "module": self.module,
            "msg": self.msg,
        }


def new_error(code: int, module: str, message: str) -> PluginError:
    """
    Create a new plugin error.
    
    Args:
        code: Numeric error code
        module: Module name where error occurred
        message: Human-readable error message
        
    Returns:
        New PluginError instance
    """
    return PluginError(code, module, message)


# Error factory functions for common error types


def err_plugin_timeout() -> PluginError:
    """
    Plugin timeout error.
    
    Returns:
        PluginError with timeout message
    """
    return new_error(
        PluginErrorCode.PLUGIN_TIMEOUT,
        DEFAULT_MODULE,
        "a plugin timeout occurred"
    )


def err_marshal(err: Union[Exception, str]) -> PluginError:
    """
    Marshal operation failed error.
    
    Args:
        err: The underlying error that caused marshal failure
        
    Returns:
        PluginError with marshal failure message
    """
    error_msg = str(err) if isinstance(err, (str, Exception)) else str(err)
    return new_error(
        PluginErrorCode.MARSHAL,
        DEFAULT_MODULE,
        f"marshal() failed with err: {error_msg}"
    )


def err_unmarshal(err: Union[Exception, str]) -> PluginError:
    """
    Unmarshal operation failed error.
    
    Args:
        err: The underlying error that caused unmarshal failure
        
    Returns:
        PluginError with unmarshal failure message
    """
    error_msg = str(err) if isinstance(err, (str, Exception)) else str(err)
    return new_error(
        PluginErrorCode.UNMARSHAL,
        DEFAULT_MODULE,
        f"unmarshal() failed with err: {error_msg}"
    )


def err_failed_plugin_read(err: Union[Exception, str]) -> PluginError:
    """
    Plugin read operation failed error.
    
    Args:
        err: The underlying error that caused read failure
        
    Returns:
        PluginError with read failure message
    """
    error_msg = str(err) if isinstance(err, (str, Exception)) else str(err)
    return new_error(
        PluginErrorCode.FAILED_PLUGIN_READ,
        DEFAULT_MODULE,
        f"a plugin read failed with err: {error_msg}"
    )


def err_failed_plugin_write(err: Union[Exception, str]) -> PluginError:
    """
    Plugin write operation failed error.
    
    Args:
        err: The underlying error that caused write failure
        
    Returns:
        PluginError with write failure message
    """
    error_msg = str(err) if isinstance(err, (str, Exception)) else str(err)
    return new_error(
        PluginErrorCode.FAILED_PLUGIN_WRITE,
        DEFAULT_MODULE,
        f"a plugin write failed with err: {error_msg}"
    )


def err_invalid_plugin_resp_id() -> PluginError:
    """
    Invalid plugin response ID error.
    
    Returns:
        PluginError indicating invalid response ID
    """
    return new_error(
        PluginErrorCode.INVALID_PLUGIN_RESP_ID,
        DEFAULT_MODULE,
        "plugin response id is invalid"
    )


def err_unexpected_fsm_to_plugin(msg_type: Union[str, int]) -> PluginError:
    """
    Unexpected FSM to plugin message type error.
    
    Args:
        msg_type: The unexpected message type received
        
    Returns:
        PluginError indicating unexpected FSM message
    """
    return new_error(
        PluginErrorCode.UNEXPECTED_FSM_TO_PLUGIN,
        DEFAULT_MODULE,
        f"unexpected FSM to plugin: {msg_type}"
    )


def err_invalid_fsm_to_plugin_message(msg_type: Union[str, int]) -> PluginError:
    """
    Invalid FSM to plugin message type error.
    
    Args:
        msg_type: The invalid message type received
        
    Returns:
        PluginError indicating invalid FSM message
    """
    return new_error(
        PluginErrorCode.INVALID_FSM_TO_PLUGIN_MESSAGE,
        DEFAULT_MODULE,
        f"invalid FSM to plugin: {msg_type}"
    )


def err_insufficient_funds() -> PluginError:
    """
    Insufficient funds error.
    
    Returns:
        PluginError indicating insufficient funds
    """
    return new_error(
        PluginErrorCode.INSUFFICIENT_FUNDS,
        DEFAULT_MODULE,
        "insufficient funds"
    )


def err_from_any(err: Union[Exception, str]) -> PluginError:
    """
    fromAny operation failed error.
    
    Args:
        err: The underlying error that caused fromAny failure
        
    Returns:
        PluginError with fromAny failure message
    """
    error_msg = str(err) if isinstance(err, (str, Exception)) else str(err)
    return new_error(
        PluginErrorCode.FROM_ANY,
        DEFAULT_MODULE,
        f"fromAny() failed with err: {error_msg}"
    )


def err_invalid_message_cast() -> PluginError:
    """
    Invalid message cast error.
    
    Returns:
        PluginError indicating message cast failure
    """
    return new_error(
        PluginErrorCode.INVALID_MESSAGE_CAST,
        DEFAULT_MODULE,
        "the message cast failed"
    )


def err_invalid_address() -> PluginError:
    """
    Invalid address error.
    
    Returns:
        PluginError indicating invalid address
    """
    return new_error(
        PluginErrorCode.INVALID_ADDRESS,
        DEFAULT_MODULE,
        "address is invalid"
    )


def err_invalid_amount() -> PluginError:
    """
    Invalid amount error.
    
    Returns:
        PluginError indicating invalid amount
    """
    return new_error(
        PluginErrorCode.INVALID_AMOUNT,
        DEFAULT_MODULE,
        "amount is invalid"
    )


def err_tx_fee_below_state_limit() -> PluginError:
    """
    Transaction fee below state limit error.
    
    Returns:
        PluginError indicating fee is below state limit
    """
    return new_error(
        PluginErrorCode.TX_FEE_BELOW_STATE_LIMIT,
        DEFAULT_MODULE,
        "tx.fee is below state limit"
    )
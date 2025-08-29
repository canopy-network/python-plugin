"""
Protobuf bindings for Canopy Plugin Protocol

This module contains the generated protobuf classes for communication
between the plugin and FSM.
"""

try:
    # Import generated protobuf classes
    from .account_pb2 import Account, Pool
    from .tx_pb2 import Transaction, MessageSend, FeeParams, Signature
    
    # Import plugin proto classes with error handling for missing fields
    from . import plugin_pb2
    
    # Create safe attribute access
    def get_proto_class(module, class_name, default=None):
        return getattr(module, class_name, default)
    
    # Plugin communication types
    FSMToPlugin = get_proto_class(plugin_pb2, 'FSMToPlugin')
    PluginToFSM = get_proto_class(plugin_pb2, 'PluginToFSM')
    PluginConfig = get_proto_class(plugin_pb2, 'PluginConfig')
    PluginFSMConfig = get_proto_class(plugin_pb2, 'PluginFSMConfig')
    
    # Request/Response types
    PluginGenesisRequest = get_proto_class(plugin_pb2, 'PluginGenesisRequest')
    PluginGenesisResponse = get_proto_class(plugin_pb2, 'PluginGenesisResponse')
    PluginBeginRequest = get_proto_class(plugin_pb2, 'PluginBeginRequest')
    PluginBeginResponse = get_proto_class(plugin_pb2, 'PluginBeginResponse')
    PluginCheckRequest = get_proto_class(plugin_pb2, 'PluginCheckRequest')
    PluginCheckResponse = get_proto_class(plugin_pb2, 'PluginCheckResponse')
    PluginDeliverRequest = get_proto_class(plugin_pb2, 'PluginDeliverRequest')
    PluginDeliverResponse = get_proto_class(plugin_pb2, 'PluginDeliverResponse')
    PluginEndRequest = get_proto_class(plugin_pb2, 'PluginEndRequest')
    PluginEndResponse = get_proto_class(plugin_pb2, 'PluginEndResponse')
    PluginError = get_proto_class(plugin_pb2, 'PluginError')
    
    # State management types
    PluginStateReadRequest = get_proto_class(plugin_pb2, 'PluginStateReadRequest')
    PluginStateReadResponse = get_proto_class(plugin_pb2, 'PluginStateReadResponse')
    PluginStateWriteRequest = get_proto_class(plugin_pb2, 'PluginStateWriteRequest')
    PluginStateWriteResponse = get_proto_class(plugin_pb2, 'PluginStateWriteResponse')
    PluginKeyRead = get_proto_class(plugin_pb2, 'PluginKeyRead')
    PluginRangeRead = get_proto_class(plugin_pb2, 'PluginRangeRead')
    PluginReadResult = get_proto_class(plugin_pb2, 'PluginReadResult')
    PluginSetOp = get_proto_class(plugin_pb2, 'PluginSetOp')
    PluginDeleteOp = get_proto_class(plugin_pb2, 'PluginDeleteOp')
    PluginStateEntry = get_proto_class(plugin_pb2, 'PluginStateEntry')

except ImportError as e:
    # Fallback for missing protobuf dependencies
    print(f"Warning: Could not import protobuf classes: {e}")
    
    # Create placeholder classes
    class Account: pass
    class Pool: pass
    class Transaction: pass
    class MessageSend: pass
    class FeeParams: pass
    class Signature: pass
    class FSMToPlugin: pass
    class PluginToFSM: pass
    class PluginConfig: pass
    class PluginFSMConfig: pass
    class PluginGenesisRequest: pass
    class PluginGenesisResponse: pass
    class PluginBeginRequest: pass
    class PluginBeginResponse: pass
    class PluginCheckRequest: pass
    class PluginCheckResponse: pass
    class PluginDeliverRequest: pass
    class PluginDeliverResponse: pass
    class PluginEndRequest: pass
    class PluginEndResponse: pass
    class PluginError: pass
    class PluginStateReadRequest: pass
    class PluginStateReadResponse: pass
    class PluginStateWriteRequest: pass
    class PluginStateWriteResponse: pass
    class PluginKeyRead: pass
    class PluginRangeRead: pass
    class PluginReadResult: pass
    class PluginSetOp: pass
    class PluginDeleteOp: pass
    class PluginStateEntry: pass

__all__ = [
    # Account types
    "Account",
    "Pool",
    # Plugin communication types
    "FSMToPlugin",
    "PluginToFSM",
    "PluginConfig",
    "PluginFSMConfig",
    # Request/Response types
    "PluginGenesisRequest",
    "PluginGenesisResponse", 
    "PluginBeginRequest",
    "PluginBeginResponse",
    "PluginCheckRequest",
    "PluginCheckResponse",
    "PluginDeliverRequest",
    "PluginDeliverResponse",
    "PluginEndRequest",
    "PluginEndResponse",
    "PluginError",
    # State management types
    "PluginStateReadRequest",
    "PluginStateReadResponse",
    "PluginStateWriteRequest", 
    "PluginStateWriteResponse",
    "PluginKeyRead",
    "PluginRangeRead",
    "PluginReadResult",
    "PluginSetOp",
    "PluginDeleteOp",
    "PluginStateEntry",
    # Transaction types
    "Transaction",
    "MessageSend",
    "FeeParams",
    "Signature",
]
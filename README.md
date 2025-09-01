# Canopy Python Plugin

## Overview

This is a Python implementation of the Canopy blockchain plugin that provides "send" transaction functionality. The plugin communicates with the Canopy FSM (Finite State Machine) via Unix socket connections using length-prefixed protobuf messages.

Key features:
- **Socket Communication**: Unix socket connection to Canopy FSM with automatic retry logic
- **Transaction Processing**: Complete send transaction validation and execution
- **State Management**: Efficient read/write operations with batch processing
- **Error Handling**: 14 standardized error types

## Configuration

### Installation

```bash
# Install Python dependencies
pip install -r requirements.txt

# Generate protobuf bindings from .proto files
make proto
```

### Environment Setup

The plugin uses a configuration system that can load settings from JSON files or environment variables:

```python
from plugin.config import Config

# Default configuration
config = Config()
print(f"Chain ID: {config.chain_id}")  # Default: 1
print(f"Data Directory: {config.data_dir}")  # Default: "/tmp/plugin/"
```

### Basic Configuration

Default settings:
- **ChainID**: 1
- **DataDir**: "/tmp/plugin/"
- **Socket**: "plugin.sock" in DataDir
- **Plugin**: name="send", id=1, version=1

Configuration can be customized through environment variables or by modifying the `plugin/config.py` file.

## Check Transaction

The transaction validation process ensures all transactions meet protocol requirements before execution.

### Validation Rules

- **Address Format**: Must be exactly 20 bytes
- **Amount Validation**: Must be greater than 0 (positive integers only)
- **Fee Validation**: Must meet or exceed state-defined minimum fee
- **Balance Check**: Sender must have sufficient funds (amount + fee)
- **Self-Transfer**: Optimized handling for same address transfers

### Example

```python
from plugin.core.contract import Contract
from plugin.proto.tx_pb2 import MessageSend

# Initialize contract
contract = Contract()

# Create transaction
tx = MessageSend()
tx.from_address = bytes.fromhex("1234567890123456789012345678901234567890")  # 20 bytes
tx.to_address = bytes.fromhex("abcdefabcdefabcdefabcdefabcdefabcdefabcd")    # 20 bytes  
tx.amount = 1000

# Validate transaction
try:
    result = contract.check_tx(tx)
    print("✅ Transaction valid")
except PluginError as e:
    print(f"❌ Validation failed: {e.message} (code: {e.code})")
```

## Deliver Transaction

The transaction execution process handles the actual state changes and balance transfers.

### Execution Process

1. **Pre-execution Validation**: Re-validate transaction parameters
2. **Balance Verification**: Ensure sender has sufficient funds
3. **State Updates**: Update sender and receiver balances atomically
4. **Fee Collection**: Deduct transaction fee to fee pool
5. **Account Cleanup**: Remove zero-balance accounts for efficiency

### Example

```python
from plugin.core.contract import Contract
from plugin.proto.tx_pb2 import MessageSend

# Initialize contract with FSM connection
contract = Contract()

# Execute transaction
tx = MessageSend()
tx.from_address = bytes.fromhex("1234567890123456789012345678901234567890")
tx.to_address = bytes.fromhex("abcdefabcdefabcdefabcdefabcdefabcdefabcd")
tx.amount = 1000

try:
    result = contract.deliver_tx(tx)
    print("✅ Transaction executed successfully")
    print(f"Gas used: {result.gas_used}")
except PluginError as e:
    print(f"❌ Execution failed: {e.message} (code: {e.code})")
```

## How to add custom transactions

To extend the system with custom transaction types, follow these steps:

### 1. Define New Transaction Type

Create a new protobuf message in `proto/tx.proto`:

```protobuf
message CustomTransaction {
  bytes from_address = 1;
  string custom_data = 2;
  uint64 amount = 3;
}
```

### 2. Regenerate Protobuf Bindings

```bash
make proto
```

### 3. Update Contract Logic

Modify `plugin/core/contract.py` to handle the new transaction type:

```python
from plugin.proto.tx_pb2 import CustomTransaction

class Contract:
    def check_tx(self, tx_data):
        # Existing MessageSend handling
        if tx_data.type_url == "/types.MessageSend":
            return self._check_send_tx(tx_data)
        # Add custom transaction handling
        elif tx_data.type_url == "/types.CustomTransaction":
            return self._check_custom_tx(tx_data)
        else:
            raise PluginError("Unknown transaction type", 12)
    
    def deliver_tx(self, tx_data):
        # Existing MessageSend handling
        if tx_data.type_url == "/types.MessageSend":
            return self._deliver_send_tx(tx_data)
        # Add custom transaction handling  
        elif tx_data.type_url == "/types.CustomTransaction":
            return self._deliver_custom_tx(tx_data)
        else:
            raise PluginError("Unknown transaction type", 12)
    
    def _check_custom_tx(self, tx_data):
        # Implement custom validation logic
        custom_tx = CustomTransaction()
        custom_tx.ParseFromString(tx_data.value)
        
        # Add your validation rules here
        if len(custom_tx.from_address) != 20:
            raise PluginError("Invalid address length", 12)
            
        return CheckTxResult(code=0, gas_wanted=100)
    
    def _deliver_custom_tx(self, tx_data):
        # Implement custom execution logic
        custom_tx = CustomTransaction()
        custom_tx.ParseFromString(tx_data.value)
        
        # Add your execution logic here
        # Update state, handle business logic, etc.
        
        return DeliverTxResult(code=0, gas_used=100)
```

### 4. Register Transaction Type

Ensure your new transaction type is properly registered in the type registry and can be marshaled/unmarshaled by the protobuf system. The key locations to modify are:

- **PluginCheckRequest handling**: Look for where "/types.MessageSend" is processed in the check_tx flow
- **PluginDeliverRequest handling**: Look for where "/types.MessageSend" is processed in the deliver_tx flow

New transactions will use a new type identifier, for example "/types.CustomTransaction".

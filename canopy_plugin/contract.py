"""
Contract implementation for Canopy blockchain plugin.

Handles send transaction validation and execution with state management.
"""

import random
from typing import Optional, Dict, Any, List, Union, Protocol
from dataclasses import dataclass
from .config import Config
from .proto_utils import marshal, unmarshal, from_any
from .keys import (
    key_for_account,
    key_for_fee_pool,
    key_for_fee_params,
    validate_address,
    validate_amount,
    normalize_address,
    normalize_amount,
)
from .errors import (
    err_invalid_address,
    err_invalid_amount,
    err_insufficient_funds,
    err_invalid_message_cast,
    err_tx_fee_below_state_limit,
    err_from_any,
    err_marshal,
    err_unmarshal,
    PluginError,
)
from .proto import Account, Pool, FeeParams


class SocketClientPlugin(Protocol):
    """Protocol for socket client plugin interface."""

    async def state_read(
        self, contract: "Contract", request: "StateReadRequest"
    ) -> "StateReadResponse": ...

    async def state_write(
        self, contract: "Contract", request: "StateWriteRequest"
    ) -> "StateWriteResponse": ...


@dataclass
class ContractOptions:
    """Options for creating a Contract instance."""

    config: Optional[Config] = None
    fsm_config: Optional[Any] = None
    plugin: Optional[SocketClientPlugin] = None
    fsm_id: Optional[Union[int, str]] = None


@dataclass
class ProtoError:
    """Protobuf error format."""

    code: int
    module: str
    msg: str


@dataclass
class TransactionRequest:
    """Transaction request structure."""

    tx: Dict[str, Any]


@dataclass
class MessageSend:
    """MessageSend transaction structure."""

    from_address: bytes
    to_address: bytes
    amount: int


@dataclass
class StateKeyQuery:
    """State key query for batch reads."""

    query_id: int
    key: bytes


@dataclass
class StateReadRequest:
    """State read request structure."""

    keys: List[StateKeyQuery]


@dataclass
class StateEntry:
    """State entry for read results."""

    key: Optional[bytes]
    value: Optional[bytes]


@dataclass
class StateQueryResult:
    """State query result structure."""

    query_id: int
    entries: List[StateEntry]


@dataclass
class StateReadResponse:
    """State read response structure."""

    error: Optional[ProtoError]
    results: List[StateQueryResult]


@dataclass
class StateSetOperation:
    """State set operation for writes."""

    key: bytes
    value: bytes


@dataclass
class StateDeleteOperation:
    """State delete operation for writes."""

    key: bytes


@dataclass
class StateWriteRequest:
    """State write request structure."""

    sets: Optional[List[StateSetOperation]] = None
    deletes: Optional[List[StateDeleteOperation]] = None


@dataclass
class StateWriteResponse:
    """State write response structure."""

    error: Optional[ProtoError]


@dataclass
class GenesisResponse:
    """Genesis response structure."""

    error: Optional[ProtoError]


@dataclass
class BeginBlockResponse:
    """Begin block response structure."""

    error: Optional[ProtoError]


@dataclass
class EndBlockResponse:
    """End block response structure."""

    error: Optional[ProtoError]


@dataclass
class CheckTxResponse:
    """Check transaction response structure."""

    recipient: Optional[bytes] = None
    authorized_signers: Optional[List[bytes]] = None
    error: Optional[ProtoError] = None


@dataclass
class DeliverTxResponse:
    """Deliver transaction response structure."""

    error: Optional[ProtoError]


# Plugin configuration
CONTRACT_CONFIG = {
    "name": "send",
    "id": 1,
    "version": 1,
    "supported_transactions": ["send"],
}


class Contract:
    """
    Contract class for blockchain transaction validation and execution.
    """

    def __init__(self, options: Optional[ContractOptions] = None):
        """Initialize contract with optional configuration."""
        if options is None:
            options = ContractOptions()

        self.config = options.config
        self.fsm_config = options.fsm_config
        self.plugin = options.plugin
        self.fsm_id = options.fsm_id

    def genesis(self, _request: Any) -> GenesisResponse:
        """Genesis block processing implementation."""
        return GenesisResponse(error=None)

    def begin_block(self, _request: Any) -> BeginBlockResponse:
        """Begin block processing implementation."""
        return BeginBlockResponse(error=None)

    async def check_tx(self, id, request: TransactionRequest) -> CheckTxResponse:
        """
        CheckTx - validate transaction without state changes.

        Args:
            request: Transaction validation request

        Returns:
            Validation result with authorized signers
        """
        print("check_tx request")
        print(request)
        try:
            if not self.plugin or not self.config:
                return CheckTxResponse(
                    error=ProtoError(
                        code=1,
                        module="contract",
                        msg="Plugin or config not initialized",
                    )
                )

            print("state_read")
            # Validate fee against state parameters
            fee_params_response = await self.plugin.state_read(
                self,
                StateReadRequest(
                    keys=[
                        StateKeyQuery(
                            query_id=id,
                            key=key_for_fee_params(),
                        )
                    ]
                ),
            )
            print("state_read done")

            if fee_params_response.error:
                return CheckTxResponse(error=fee_params_response.error)

            # Convert bytes into fee parameters
            if (
                not fee_params_response.results
                or not fee_params_response.results[0].entries
            ):
                return CheckTxResponse(
                    error=ProtoError(
                        code=1, module="contract", msg="Fee parameters not found"
                    )
                )

            fee_params_bytes = fee_params_response.results[0].entries[0].value
            if not fee_params_bytes:
                return CheckTxResponse(
                    error=ProtoError(
                        code=1, module="contract", msg="Fee parameters not found"
                    )
                )

            min_fees = unmarshal(FeeParams, fee_params_bytes)
            if not min_fees:
                return CheckTxResponse(
                    error=err_unmarshal(
                        "Failed to decode fee parameters"
                    ).to_proto_error()
                )

            # Check for minimum fee
            try:
                request_fee = normalize_amount(request.tx["fee"])
                min_send_fee = normalize_amount(min_fees.send_fee)
            except Exception as error:
                return CheckTxResponse(
                    error=ProtoError(
                        code=1,
                        module="contract",
                        msg=f"Failed to normalize fee: {error}",
                    )
                )

            if request_fee < min_send_fee:
                return CheckTxResponse(
                    error=err_tx_fee_below_state_limit().to_proto_error()
                )

            # Get the message from protobuf Any type
            try:
                msg = from_any(request.tx["msg"])
            except Exception as err:
                return CheckTxResponse(error=err_from_any(str(err)).to_proto_error())

            # Handle the message based on type
            if self._is_message_send(msg):
                return self._check_message_send(msg)
            else:
                return CheckTxResponse(
                    error=err_invalid_message_cast().to_proto_error()
                )

        except Exception as err:
            print(err)
            return CheckTxResponse(error=err_unmarshal(str(err)).to_proto_error())

    async def deliver_tx(self, request: TransactionRequest) -> DeliverTxResponse:
        """
        DeliverTx - execute transaction with state changes.

        Args:
            request: Transaction execution request

        Returns:
            Execution result
        """
        try:
            # Get the message from protobuf Any type
            try:
                msg = from_any(request.tx["msg"])
            except Exception as err:
                return DeliverTxResponse(error=err_from_any(str(err)).to_proto_error())

            # Handle the message based on type
            if self._is_message_send(msg):
                try:
                    response = await self._deliver_message_send(msg, request.tx["fee"])
                    return response
                except Exception as error:
                    return DeliverTxResponse(
                        error=ProtoError(code=1, module="contract", msg=str(error))
                    )
            else:
                return DeliverTxResponse(
                    error=err_invalid_message_cast().to_proto_error()
                )

        except Exception as err:
            return DeliverTxResponse(error=err_unmarshal(str(err)).to_proto_error())

    def end_block(self, _request: Any) -> EndBlockResponse:
        """End block processing implementation."""
        return EndBlockResponse(error=None)

    def _is_message_send(self, msg: Any) -> bool:
        """
        Type guard to check if message is MessageSend.

        Args:
            msg: Message to check

        Returns:
            True if message is MessageSend
        """
        if isinstance(msg, dict):
            return (
                "from_address" in msg
                or "fromAddress" in msg
                and "to_address" in msg
                or "toAddress" in msg
                and "amount" in msg
            )
        return (
            hasattr(msg, "from_address")
            and hasattr(msg, "to_address")
            and hasattr(msg, "amount")
        )

    def _check_message_send(self, msg: Any) -> CheckTxResponse:
        """
        Validate MessageSend without state changes.

        Args:
            msg: MessageSend to validate

        Returns:
            Validation result with authorized signers
        """
        # Extract addresses and amount from message (handle both dict and object formats)
        if isinstance(msg, dict):
            from_addr = msg.get("from_address") or msg.get("fromAddress")
            to_addr = msg.get("to_address") or msg.get("toAddress")
            amount = msg.get("amount")
        else:
            from_addr = getattr(msg, "from_address", None)
            to_addr = getattr(msg, "to_address", None)
            amount = getattr(msg, "amount", None)

        # Check sender address (must be exactly 20 bytes)
        if not validate_address(from_addr):
            return CheckTxResponse(error=err_invalid_address().to_proto_error())

        # Check recipient address (must be exactly 20 bytes)
        if not validate_address(to_addr):
            return CheckTxResponse(error=err_invalid_address().to_proto_error())

        # Check amount (must be greater than 0)
        if not validate_amount(amount):
            return CheckTxResponse(error=err_invalid_amount().to_proto_error())

        # Return authorized signers (sender must sign)
        return CheckTxResponse(
            recipient=to_addr, authorized_signers=[from_addr], error=None
        )

    def _generate_query_ids(self) -> Dict[str, int]:
        """
        Generate random query IDs for batch state operations.

        Returns:
            Dict containing fromQueryId, toQueryId, and feeQueryId
        """
        return {
            "from_query_id": random.randint(0, 2**53 - 1),
            "to_query_id": random.randint(0, 2**53 - 1),
            "fee_query_id": random.randint(0, 2**53 - 1),
        }

    async def _read_accounts_and_fee_pool(self, msg: Any) -> Dict[str, Optional[bytes]]:
        """
        Read accounts and fee pool from state.

        Args:
            msg: MessageSend containing addresses

        Returns:
            Dict with account and fee pool bytes
        """
        if not self.plugin or not self.config:
            raise ValueError("Plugin or config not initialized")

        query_ids = self._generate_query_ids()

        # Extract addresses from message
        if isinstance(msg, dict):
            from_addr = msg.get("from_address") or msg.get("fromAddress")
            to_addr = msg.get("to_address") or msg.get("toAddress")
        else:
            from_addr = getattr(msg, "from_address", None)
            to_addr = getattr(msg, "to_address", None)

        # Calculate state keys
        from_key = key_for_account(from_addr)
        to_key = key_for_account(to_addr)
        fee_pool_key = key_for_fee_pool(self.config.chain_id)

        # Batch read accounts and fee pool from state
        response = await self.plugin.state_read(
            self,
            StateReadRequest(
                keys=[
                    StateKeyQuery(query_id=query_ids["fee_query_id"], key=fee_pool_key),
                    StateKeyQuery(query_id=query_ids["from_query_id"], key=from_key),
                    StateKeyQuery(query_id=query_ids["to_query_id"], key=to_key),
                ]
            ),
        )

        if response.error:
            raise ValueError(f"State read error: {response.error.msg}")

        # Parse response results by query ID
        from_bytes = None
        to_bytes = None
        fee_pool_bytes = None

        for result in response.results:
            if result.query_id == query_ids["from_query_id"]:
                from_bytes = result.entries[0].value if result.entries else None
            elif result.query_id == query_ids["to_query_id"]:
                to_bytes = result.entries[0].value if result.entries else None
            elif result.query_id == query_ids["fee_query_id"]:
                fee_pool_bytes = result.entries[0].value if result.entries else None

        return {
            "from_bytes": from_bytes,
            "to_bytes": to_bytes,
            "fee_pool_bytes": fee_pool_bytes,
        }

    def _unmarshal_accounts_and_pool(
        self,
        from_bytes: Optional[bytes],
        to_bytes: Optional[bytes],
        fee_pool_bytes: Optional[bytes],
        msg: Any,
    ) -> Dict[str, Any]:
        """
        Unmarshal account and pool data from state bytes.

        Args:
            from_bytes: From account bytes
            to_bytes: To account bytes
            fee_pool_bytes: Fee pool bytes
            msg: MessageSend containing addresses

        Returns:
            Dict with unmarshaled accounts, pool, and normalized fromAmount
        """
        from_account = unmarshal(Account, from_bytes) if from_bytes else None

        # Extract to address from message
        if isinstance(msg, dict):
            to_addr = msg.get("to_address") or msg.get("toAddress")
        else:
            to_addr = getattr(msg, "to_address", None)

        try:
            to_account = unmarshal(Account, to_bytes) if to_bytes else None
            if not to_account:
                to_account = Account(address=to_addr, amount=0)
        except Exception:
            to_account = Account(address=to_addr, amount=0)

        try:
            fee_pool = unmarshal(Pool, fee_pool_bytes) if fee_pool_bytes else None
            if not fee_pool:
                fee_pool = Pool(amount=0)
        except Exception:
            fee_pool = Pool(amount=0)

        from_amount = from_account.amount if from_account else 0

        return {
            "from_account": from_account,
            "to_account": to_account,
            "fee_pool": fee_pool,
            "from_amount": from_amount,
        }

    async def _deliver_message_send(
        self, msg: Any, fee: Union[int, str]
    ) -> DeliverTxResponse:
        """
        Process MessageSend with state changes.

        Args:
            msg: MessageSend to execute
            fee: Transaction fee

        Returns:
            Execution result
        """
        try:
            transaction_fee = normalize_amount(fee)

            if not self.plugin or not self.config:
                return DeliverTxResponse(
                    error=ProtoError(
                        code=1,
                        module="contract",
                        msg="Plugin or config not initialized",
                    )
                )

            # Read accounts and fee pool from state
            state_data = await self._read_accounts_and_fee_pool(msg)

            # Unmarshal account and pool data
            unmarshaled_data = self._unmarshal_accounts_and_pool(
                state_data["from_bytes"],
                state_data["to_bytes"],
                state_data["fee_pool_bytes"],
                msg,
            )

            from_account = unmarshaled_data["from_account"]
            to_account = unmarshaled_data["to_account"]
            fee_pool = unmarshaled_data["fee_pool"]
            from_amount = unmarshaled_data["from_amount"]

            # Extract amount from message
            if isinstance(msg, dict):
                message_amount = msg.get("amount", 0)
            else:
                message_amount = getattr(msg, "amount", 0)

            message_amount = normalize_amount(message_amount)
            amount_to_deduct = message_amount + transaction_fee

            # Check sufficient funds
            if from_amount < amount_to_deduct:
                return DeliverTxResponse(
                    error=err_insufficient_funds().to_proto_error()
                )

            # Calculate state keys
            if isinstance(msg, dict):
                from_addr = msg.get("from_address") or msg.get("fromAddress")
                to_addr = msg.get("to_address") or msg.get("toAddress")
            else:
                from_addr = getattr(msg, "from_address")
                to_addr = getattr(msg, "to_address")

            from_key = key_for_account(from_addr)
            to_key = key_for_account(to_addr)
            fee_pool_key = key_for_fee_pool(self.config.chain_id)

            # Calculate updated balances
            updated_from_account = Account(
                address=normalize_address(from_addr),
                amount=from_amount - amount_to_deduct,
            )

            # Handle self-transfer optimization
            is_self_transfer = from_key == to_key

            if is_self_transfer:
                updated_to_account = Account(
                    address=normalize_address(to_addr),
                    amount=from_amount
                    - transaction_fee,  # Only deduct fee for self-transfer
                )
            else:
                updated_to_account = Account(
                    address=normalize_address(to_addr),
                    amount=to_account.amount + message_amount,
                )

            # Update fee pool
            updated_fee_pool = Pool(
                id=self.config.chain_id, amount=fee_pool.amount + transaction_fee
            )

            # Prepare state write operations
            sets = [
                StateSetOperation(key=fee_pool_key, value=marshal(updated_fee_pool))
            ]
            deletes = []

            # Handle account deletion when balance reaches zero
            if updated_from_account.amount == 0 and not is_self_transfer:
                deletes.append(StateDeleteOperation(key=from_key))
            else:
                sets.append(
                    StateSetOperation(key=from_key, value=marshal(updated_from_account))
                )

            if not is_self_transfer:
                sets.append(
                    StateSetOperation(key=to_key, value=marshal(updated_to_account))
                )

            # Execute batch state write
            write_response = await self.plugin.state_write(
                self, StateWriteRequest(sets=sets, deletes=deletes)
            )

            return DeliverTxResponse(error=write_response.error)

        except Exception as err:
            return DeliverTxResponse(error=err_marshal(str(err)).to_proto_error())

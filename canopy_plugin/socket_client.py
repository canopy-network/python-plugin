"""
Unix socket client that communicates with Canopy FSM using length-prefixed protobuf messages.

Provides async socket communication with automatic reconnection and message handling.
"""

import asyncio
import os
import socket
import struct
import logging
from typing import Optional, Dict, Any, Callable, Awaitable
from dataclasses import dataclass

from .config import Config
from .contract import Contract, CONTRACT_CONFIG
from .proto import (
    FSMToPlugin,
    PluginToFSM,
    PluginConfig,
    PluginError,
    PluginStateReadRequest,
    PluginStateReadResponse,
    PluginStateWriteRequest,
    PluginStateWriteResponse,
)


@dataclass
class SocketClientOptions:
    """Socket client configuration options."""

    config: Config
    reconnect_interval: float = 3.0
    request_timeout: float = 10.0
    connection_timeout: float = 5.0


class SocketClient:
    """
    Unix socket client for FSM communication with automatic reconnection and message handling.
    """

    def __init__(self, options: SocketClientOptions):
        """Initialize socket client with configuration."""
        self.config = options.config
        self.logger = logging.getLogger("SocketClient")
        self.socket_path = os.path.join(self.config.data_dir_path, "plugin.sock")
        self.reconnect_interval = options.reconnect_interval
        self.request_timeout = options.request_timeout
        self.connection_timeout = options.connection_timeout

        self._sock: Optional[socket.socket] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._pending: Dict[int, asyncio.Future] = {}
        self._request_contracts: Dict[int, Contract] = {}
        self._listen_task: Optional[asyncio.Task] = None

        self._is_connected = False
        self._is_reconnecting = False
        self._message_id_counter = 1

        # Logger will use the root logger configuration from main.py
        self.logger.setLevel(logging.DEBUG)

    async def start(self) -> None:
        """Start the socket client and connect to FSM."""
        await self._connect_with_retry()
        await self._handshake()
        self._listen_task = asyncio.create_task(self._listen_for_messages())
        self.logger.info("Socket client started and connected to FSM")

    async def close(self) -> None:
        """Close the socket connection gracefully."""
        self._is_connected = False
        
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()

        if self._sock:
            self._sock.close()

        self.logger.info("Socket client closed")

    async def state_read(self, contract: Contract, request: Any) -> Any:
        """
        Send state read request to FSM.

        Args:
            contract: Contract instance making the request
            request: State read request data

        Returns:
            State read response
        """
        # Convert request to protobuf format
        from .proto import PluginKeyRead

        proto_request = PluginStateReadRequest()

        # Convert StateKeyQuery objects to PluginKeyRead objects
        for key_query in request.keys:
            key_read = PluginKeyRead()
            key_read.query_id = key_query.query_id
            key_read.key = key_query.key
            proto_request.keys.append(key_read)

        message_id = request.keys[0].query_id
        
        # Create future before setting up request to avoid race condition
        future = asyncio.Future()
        self._pending[message_id] = future
        self._request_contracts[message_id] = contract

        plugin_message = PluginToFSM()
        plugin_message.id = message_id
        plugin_message.state_read.CopyFrom(proto_request)

        self.logger.debug(f"state_read pending set {self._pending}")
        self.logger.debug(f"plugin_message {plugin_message}")

        try:
            await self._send_message(plugin_message)

            # Wait for response with timeout
            response = await asyncio.wait_for(future, timeout=self.request_timeout)

            self.logger.info(f"response {response}")
            # Convert response to expected format
            if response.HasField("state_read"):
                return self._convert_state_read_response(response.state_read)
            else:
                from .contract import StateReadResponse, ProtoError

                return StateReadResponse(
                    error=ProtoError(
                        code=1, module="socket", msg="No state read response"
                    ),
                    results=[],
                )

        except asyncio.TimeoutError:
            self.logger.error(f"State read request {message_id} timed out")
            from .contract import StateReadResponse, ProtoError

            return StateReadResponse(
                error=ProtoError(code=1, module="socket", msg="Request timeout"),
                results=[],
            )
        except Exception:
            # If there's an error, make sure to clean up and mark future as failed
            if message_id in self._pending and not future.done():
                future.cancel()
            raise
        finally:
            # Clean up request state
            self._pending.pop(message_id, None)
            self._request_contracts.pop(message_id, None)

    async def state_write(self, contract: Contract, request: Any) -> Any:
        """
        Send state write request to FSM.

        Args:
            contract: Contract instance making the request
            request: State write request data

        Returns:
            State write response
        """
        # Convert request to protobuf format
        from .proto import PluginSetOp, PluginDeleteOp

        proto_request = PluginStateWriteRequest()

        # Convert StateSetOperation objects to PluginSetOp objects
        if request.sets:
            for set_op in request.sets:
                plugin_set_op = PluginSetOp()
                plugin_set_op.key = set_op.key
                plugin_set_op.value = set_op.value
                proto_request.sets.append(plugin_set_op)

        # Convert StateDeleteOperation objects to PluginDeleteOp objects
        if request.deletes:
            for delete_op in request.deletes:
                plugin_delete_op = PluginDeleteOp()
                plugin_delete_op.key = delete_op.key
                proto_request.deletes.append(plugin_delete_op)

        message_id = self._get_next_message_id()
        
        # Create future before setting up request to avoid race condition
        future = asyncio.Future()
        self._pending[message_id] = future
        self._request_contracts[message_id] = contract

        plugin_message = PluginToFSM()
        plugin_message.id = message_id
        plugin_message.state_write.CopyFrom(proto_request)

        try:
            await self._send_message(plugin_message)

            # Wait for response with timeout
            response = await asyncio.wait_for(future, timeout=self.request_timeout)

            # Convert response to expected format
            if response.HasField("state_write"):
                return self._convert_state_write_response(response.state_write)
            else:
                from .contract import StateWriteResponse, ProtoError

                return StateWriteResponse(
                    error=ProtoError(
                        code=1, module="socket", msg="No state write response"
                    )
                )

        except asyncio.TimeoutError:
            self.logger.error(f"State write request {message_id} timed out")
            from .contract import StateWriteResponse, ProtoError

            return StateWriteResponse(
                error=ProtoError(code=1, module="socket", msg="Request timeout")
            )
        except Exception:
            # If there's an error, make sure to clean up and mark future as failed
            if message_id in self._pending and not future.done():
                future.cancel()
            raise
        finally:
            # Clean up request state
            self._pending.pop(message_id, None)
            self._request_contracts.pop(message_id, None)

    async def _connect_with_retry(self) -> None:
        """Connect to Unix socket with retry logic."""
        if self._is_reconnecting:
            return

        self._is_reconnecting = True

        while not self._is_connected:
            try:
                await self._attempt_connection()
                self._is_reconnecting = False
                return
            except Exception as err:
                self.logger.warning(f"Error connecting to plugin socket: {err}")
                await asyncio.sleep(self.reconnect_interval)

        self._is_reconnecting = False

    async def _attempt_connection(self) -> None:
        """Attempt a single connection with proper error handling."""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_unix_connection(self.socket_path),
                timeout=self.connection_timeout,
            )

            self._is_connected = True
            self.logger.info(f"Connection established to {self.socket_path}")

        except Exception as err:
            if self._writer:
                self._writer.close()
                await self._writer.wait_closed()
            self._is_connected = False
            raise err

    async def _handshake(self) -> None:
        """Perform initial handshake with FSM."""
        plugin_config = PluginConfig()
        plugin_config.name = CONTRACT_CONFIG["name"]
        plugin_config.id = CONTRACT_CONFIG["id"]
        plugin_config.version = CONTRACT_CONFIG["version"]

        # Set supported transactions
        for tx_type in CONTRACT_CONFIG["supported_transactions"]:
            plugin_config.supported_transactions.append(tx_type)

        message_id = self._get_next_message_id()

        plugin_message = PluginToFSM()
        plugin_message.id = message_id
        plugin_message.config.CopyFrom(plugin_config)

        await self._send_message(plugin_message)
        self.logger.info("Plugin config sent")

    async def _listen_for_messages(self) -> None:
        """Listen for inbound messages from FSM with proper buffer management."""
        if not self._reader:
            raise RuntimeError("No reader available for listening")

        try:
            while self._is_connected:
                try:
                    # Read length prefix (4 bytes, big-endian) with timeout
                    length_data = await asyncio.wait_for(
                        self._reader.readexactly(4), 
                        timeout=self.request_timeout
                    )
                    message_length = struct.unpack(">I", length_data)[0]

                    # Read message data with timeout
                    message_data = await asyncio.wait_for(
                        self._reader.readexactly(message_length), 
                        timeout=self.request_timeout
                    )

                    # Handle the message
                    await self._handle_inbound_message(message_data)

                except asyncio.TimeoutError:
                    # Timeout is normal, just continue listening
                    if not self._is_connected:
                        break
                    continue

        except asyncio.IncompleteReadError:
            self.logger.info("Connection closed by FSM")
        except asyncio.CancelledError:
            self.logger.info("Message listening cancelled")
        except Exception as err:
            self.logger.error(f"Error reading from socket: {err}")
        finally:
            self._is_connected = False
            # Cancel any pending requests
            for future in self._pending.values():
                if not future.done():
                    future.cancel()

    async def _handle_inbound_message(self, message_data: bytes) -> None:
        """Handle inbound protobuf message from FSM."""
        try:
            # TODO: Decode FSMToPlugin message
            fsm_message = FSMToPlugin()
            fsm_message.ParseFromString(message_data)

            self.logger.info(f"handle inbound message pending {self._pending}")
            message_id = fsm_message.id

            # Check if this is a response to our request
            if message_id in self._pending:
                self.logger.debug(f"Handling FSM response for id: {message_id}")
                future = self._pending.pop(message_id, None)
                if future and not future.done():
                    future.set_result(fsm_message)
            else:
                self.logger.debug(f"Handling FSM request for id: {message_id}")
                await self._handle_fsm_request(fsm_message)

        except Exception as err:
            self.logger.error(f"Failed to decode FSM message: {err}")

    async def _handle_fsm_request(self, message: Any) -> None:
        """Handle new request from FSM."""
        try:
            contract = self._create_contract_instance(message.id)
            response = await self._process_request_message(message, contract)

            if response:
                await self._send_response_to_fsm(message.id, response)

        except Exception as err:
            await self._send_error_response(message.id, err)

    async def _process_request_message(
        self, message: Any, contract: Contract
    ) -> Optional[Dict[str, Any]]:
        """Process specific request message types."""
        message_id = message.id

        # Handle different message types
        if message.HasField("config"):
            self.logger.debug(f"Processing config message (id: {message_id})")
            return None  # No response needed

        if message.HasField("genesis"):
            self.logger.info(f"Processing genesis request (id: {message_id})")
            result = contract.genesis(message.genesis)
            return {"genesis": result}

        if message.HasField("begin"):
            self.logger.debug(f"Processing begin block request (id: {message_id})")
            result = contract.begin_block(message.begin)
            return {"begin": result}

        if message.HasField("check"):
            self.logger.debug(f"Processing check tx request (id: {message_id})")
            result = await contract.check_tx(message.id, {"tx": message.check.tx})
            self.logger.info(f"check result {result}")
            return {"check": result}

        if message.HasField("deliver"):
            self.logger.debug(f"Processing deliver tx request (id: {message_id})")
            result = await contract.deliver_tx({"tx": message.deliver.tx})
            return {"deliver": result}

        if message.HasField("end"):
            self.logger.debug(f"Processing end block request (id: {message_id})")
            result = contract.end_block(message.end)
            return {"end": result}

        return None

    async def _send_response_to_fsm(
        self, request_id: int, response: Dict[str, Any]
    ) -> None:
        """Send response back to FSM."""
        plugin_message = PluginToFSM()
        plugin_message.id = request_id

        # Set appropriate response field based on response type
        from .proto import (
            PluginGenesisResponse,
            PluginBeginResponse,
            PluginCheckResponse,
            PluginDeliverResponse,
            PluginEndResponse,
        )

        if "genesis" in response:
            genesis_response = PluginGenesisResponse()
            self._convert_genesis_response(genesis_response, response["genesis"])
            plugin_message.genesis.CopyFrom(genesis_response)
        elif "begin" in response:
            begin_response = PluginBeginResponse()
            self._convert_begin_response(begin_response, response["begin"])
            plugin_message.begin.CopyFrom(begin_response)
        elif "check" in response:
            check_response = PluginCheckResponse()
            self._convert_check_response(check_response, response["check"])
            plugin_message.check.CopyFrom(check_response)
        elif "deliver" in response:
            deliver_response = PluginDeliverResponse()
            self._convert_deliver_response(deliver_response, response["deliver"])
            plugin_message.deliver.CopyFrom(deliver_response)
        elif "end" in response:
            end_response = PluginEndResponse()
            self._convert_end_response(end_response, response["end"])
            plugin_message.end.CopyFrom(end_response)

        await self._send_message(plugin_message)

    async def _send_error_response(self, request_id: int, error: Exception) -> None:
        """Send error response to FSM."""
        # TODO: Create error response message
        self.logger.error(f"Sending error response for request {request_id}: {error}")

    async def _send_message(self, message: Any) -> None:
        """Send protobuf message to FSM with length prefix."""
        if not self._writer:
            raise RuntimeError("No writer available for sending")

        if not self._is_connected:
            raise RuntimeError("Socket not connected")

        # Serialize message to bytes
        message_data = message.SerializeToString()

        # Send length prefix (4 bytes, big-endian) followed by message
        length_prefix = struct.pack(">I", len(message_data))
        self._writer.write(length_prefix + message_data)
        
        # Add timeout to drain operation to prevent blocking
        try:
            await asyncio.wait_for(self._writer.drain(), timeout=self.request_timeout)
        except asyncio.TimeoutError:
            self.logger.error("Message send timeout - connection may be blocked")
            self._is_connected = False
            raise

    def _create_contract_instance(self, fsm_id: int) -> Contract:
        """Create contract instance for request processing."""
        from .contract import ContractOptions

        options = ContractOptions(config=self.config, plugin=self, fsm_id=fsm_id)
        return Contract(options)

    def _get_next_message_id(self) -> int:
        """Get next unique message ID."""
        current = self._message_id_counter
        self._message_id_counter += 1
        return current

    def _convert_state_read_response(self, proto_response: Any) -> "StateReadResponse":
        """Convert protobuf state read response to expected format."""
        from .contract import (
            StateReadResponse,
            StateQueryResult,
            StateEntry,
            ProtoError,
        )

        # Convert error if present
        error = None
        if hasattr(proto_response, "error") and proto_response.HasField("error"):
            error = ProtoError(
                code=proto_response.error.code,
                module=proto_response.error.module,
                msg=proto_response.error.msg,
            )

        # Convert results
        results = []
        for result in proto_response.results:
            entries = []
            for entry in result.entries:
                entries.append(StateEntry(key=entry.key, value=entry.value))
            results.append(StateQueryResult(query_id=result.query_id, entries=entries))

        return StateReadResponse(error=error, results=results)

    def _convert_state_write_response(
        self, proto_response: Any
    ) -> "StateWriteResponse":
        """Convert protobuf state write response to expected format."""
        from .contract import StateWriteResponse, ProtoError

        # Convert error if present
        error = None
        if hasattr(proto_response, "error") and proto_response.HasField("error"):
            error = ProtoError(
                code=proto_response.error.code,
                module=proto_response.error.module,
                msg=proto_response.error.msg,
            )

        return StateWriteResponse(error=error)

    def _convert_genesis_response(self, proto_msg: Any, contract_response: Any) -> None:
        """Convert contract GenesisResponse to protobuf PluginGenesisResponse."""
        # Always ensure we have a valid message structure
        if contract_response.error:
            proto_msg.error.code = contract_response.error.code
            proto_msg.error.module = contract_response.error.module
            proto_msg.error.msg = contract_response.error.msg
        # If no error, the message is still valid (empty error means success)

    def _convert_begin_response(self, proto_msg: Any, contract_response: Any) -> None:
        """Convert contract BeginBlockResponse to protobuf PluginBeginResponse."""
        # Always ensure we have a valid message structure
        if contract_response.error:
            proto_msg.error.code = contract_response.error.code
            proto_msg.error.module = contract_response.error.module
            proto_msg.error.msg = contract_response.error.msg
        # If no error, the message is still valid (empty error means success)

    def _convert_check_response(self, proto_msg: Any, contract_response: Any) -> None:
        """Convert contract CheckTxResponse to protobuf PluginCheckResponse."""
        # Set response data
        if contract_response.recipient:
            proto_msg.recipient = contract_response.recipient
        if contract_response.authorized_signers:
            proto_msg.authorized_signers.extend(contract_response.authorized_signers)

        # Set error if present
        if contract_response.error:
            proto_msg.error.code = contract_response.error.code
            proto_msg.error.module = contract_response.error.module
            proto_msg.error.msg = contract_response.error.msg

    def _convert_deliver_response(self, proto_msg: Any, contract_response: Any) -> None:
        """Convert contract DeliverTxResponse to protobuf PluginDeliverResponse."""
        # Always ensure we have a valid message structure
        if contract_response.error:
            proto_msg.error.code = contract_response.error.code
            proto_msg.error.module = contract_response.error.module
            proto_msg.error.msg = contract_response.error.msg
        # If no error, the message is still valid (empty error means success)

    def _convert_end_response(self, proto_msg: Any, contract_response: Any) -> None:
        """Convert contract EndBlockResponse to protobuf PluginEndResponse."""
        # Always ensure we have a valid message structure
        if contract_response.error:
            proto_msg.error.code = contract_response.error.code
            proto_msg.error.module = contract_response.error.module
            proto_msg.error.msg = contract_response.error.msg
        # If no error, the message is still valid (empty error means success)

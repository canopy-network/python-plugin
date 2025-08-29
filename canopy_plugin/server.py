"""
FastAPI HTTP server for Canopy Plugin.

Provides REST API endpoints for blockchain lifecycle operations and development tools.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .config import Config
from .contract import Contract, ContractOptions, CONTRACT_CONFIG
from .socket_client import SocketClient, SocketClientOptions
from .errors import PluginError


# Configure logging
logger = logging.getLogger('CanopyServer')


# Request/Response Models
class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    fsm_connected: bool
    plugin_name: str
    plugin_version: int


class StatusResponse(BaseModel):
    """Server status response."""
    uptime_seconds: float
    plugin_config: Dict[str, Any]
    server_config: Dict[str, Any]


class InfoResponse(BaseModel):
    """Plugin information response."""
    name: str
    id: int
    version: int
    supported_transactions: list[str]


class TransactionRequest(BaseModel):
    """Transaction request body."""
    tx: Dict[str, Any]


class TransactionResponse(BaseModel):
    """Transaction response."""
    error: Optional[Dict[str, Any]] = None
    recipient: Optional[str] = None
    authorized_signers: Optional[list[str]] = None


class GenesisRequest(BaseModel):
    """Genesis request body."""
    genesis_json: bytes = Field(..., description="Genesis JSON data")


class BeginBlockRequest(BaseModel):
    """Begin block request body."""
    pass


class EndBlockRequest(BaseModel):
    """End block request body."""
    proposer_address: bytes = Field(..., description="Proposer address")


class GenericResponse(BaseModel):
    """Generic response with optional error."""
    error: Optional[Dict[str, Any]] = None


# Global state
socket_client: Optional[SocketClient] = None
start_time: float = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global socket_client, start_time
    
    import time
    start_time = time.time()
    
    # Initialize socket client if FSM integration is enabled
    try:
        config = Config.default_config()
        options = SocketClientOptions(config=config)
        socket_client = SocketClient(options)
        
        # Try to start socket client, but don't fail if FSM is not available
        try:
            await socket_client.start()
            logger.info("FSM connection established")
        except Exception as e:
            logger.warning(f"FSM connection failed: {e}. Running in standalone mode.")
            socket_client = None
    
    except Exception as e:
        logger.error(f"Failed to initialize socket client: {e}")
        socket_client = None
    
    yield
    
    # Cleanup
    if socket_client:
        try:
            await socket_client.close()
        except Exception as e:
            logger.error(f"Error closing socket client: {e}")


# Create FastAPI app
app = FastAPI(
    title="Canopy Plugin Python",
    description="Python implementation of the Canopy blockchain plugin",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handler for plugin errors
@app.exception_handler(PluginError)
async def plugin_error_handler(request: Request, exc: PluginError):
    """Handle plugin errors with proper HTTP status codes."""
    return JSONResponse(
        status_code=400,
        content={"error": exc.to_proto_error()}
    )


# Health and status endpoints
@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        fsm_connected=socket_client is not None and socket_client._is_connected,
        plugin_name=CONTRACT_CONFIG["name"],
        plugin_version=CONTRACT_CONFIG["version"]
    )


@app.get("/status", response_model=StatusResponse)
async def status():
    """Server status and metrics."""
    import time
    uptime = time.time() - start_time
    
    return StatusResponse(
        uptime_seconds=uptime,
        plugin_config=CONTRACT_CONFIG,
        server_config={
            "fsm_integration": socket_client is not None,
            "fsm_connected": socket_client is not None and socket_client._is_connected
        }
    )


@app.get("/info", response_model=InfoResponse)
async def info():
    """Plugin metadata information."""
    return InfoResponse(
        name=CONTRACT_CONFIG["name"],
        id=CONTRACT_CONFIG["id"],
        version=CONTRACT_CONFIG["version"],
        supported_transactions=CONTRACT_CONFIG["supported_transactions"]
    )


# Blockchain lifecycle endpoints (require FSM connection)
@app.post("/genesis", response_model=GenericResponse)
async def genesis(request: GenesisRequest):
    """Process genesis block."""
    if not socket_client:
        raise HTTPException(
            status_code=503,
            detail="FSM connection not available"
        )
    
    try:
        contract = _create_contract_instance()
        result = contract.genesis(request.genesis_json)
        return GenericResponse(error=result.error)
    
    except Exception as e:
        logger.error(f"Genesis processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/begin-block", response_model=GenericResponse)
async def begin_block(request: BeginBlockRequest):
    """Handle begin block processing."""
    if not socket_client:
        raise HTTPException(
            status_code=503,
            detail="FSM connection not available"
        )
    
    try:
        contract = _create_contract_instance()
        result = contract.begin_block(request)
        return GenericResponse(error=result.error)
    
    except Exception as e:
        logger.error(f"Begin block processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/check-tx", response_model=TransactionResponse)
async def check_tx(request: TransactionRequest):
    """Validate transaction without state changes."""
    if not socket_client:
        raise HTTPException(
            status_code=503,
            detail="FSM connection not available"
        )
    
    try:
        contract = _create_contract_instance()
        result = await contract.check_tx(request.dict())
        
        return TransactionResponse(
            error=result.error,
            recipient=result.recipient.hex() if result.recipient else None,
            authorized_signers=[addr.hex() for addr in (result.authorized_signers or [])]
        )
    
    except Exception as e:
        logger.error(f"Check tx processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/deliver-tx", response_model=GenericResponse)
async def deliver_tx(request: TransactionRequest):
    """Execute transaction with state changes."""
    if not socket_client:
        raise HTTPException(
            status_code=503,
            detail="FSM connection not available"
        )
    
    try:
        contract = _create_contract_instance()
        result = await contract.deliver_tx(request.dict())
        return GenericResponse(error=result.error)
    
    except Exception as e:
        logger.error(f"Deliver tx processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/end-block", response_model=GenericResponse)
async def end_block(request: EndBlockRequest):
    """Handle end block processing."""
    if not socket_client:
        raise HTTPException(
            status_code=503,
            detail="FSM connection not available"
        )
    
    try:
        contract = _create_contract_instance()
        result = contract.end_block(request)
        return GenericResponse(error=result.error)
    
    except Exception as e:
        logger.error(f"End block processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Development endpoints
@app.post("/simulate-tx", response_model=TransactionResponse)
async def simulate_tx(request: TransactionRequest):
    """Simulate transaction without FSM (for development)."""
    try:
        # Create standalone contract for simulation
        config = Config.default_config()
        contract = Contract(ContractOptions(config=config))
        
        # Simulate check_tx without state reads
        result = contract._check_message_send(request.tx.get('msg', {}))
        
        return TransactionResponse(
            error=result.error,
            recipient=result.recipient.hex() if result.recipient else None,
            authorized_signers=[addr.hex() for addr in (result.authorized_signers or [])]
        )
    
    except Exception as e:
        logger.error(f"Simulate tx error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _create_contract_instance() -> Contract:
    """Create contract instance for request processing."""
    if not socket_client:
        raise HTTPException(
            status_code=503,
            detail="FSM connection not available"
        )
    
    config = Config.default_config()
    options = ContractOptions(
        config=config,
        plugin=socket_client,
        fsm_id=1
    )
    return Contract(options)


# Development server runner
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "canopy_plugin.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
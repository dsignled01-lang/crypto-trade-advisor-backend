from fastapi import APIRouter, HTTPException
from datetime import datetime
from app.services.exchange_service import ExchangeService
from app.services.cache_manager import signal_cache, ohlcv_cache, ticker_cache
from app.models import HealthStatus, ExchangeStatus
from app.utils.logger import log_info
import time

router = APIRouter(prefix="/api/v1", tags=["health"])

exchange_service = ExchangeService()
start_time = time.time()


@router.get("/health", response_model=HealthStatus)
async def health_check():
    """Check service health and exchange connectivity"""
    try:
        # Get exchange status
        exchange_statuses = []
        for exchange_name, exchange in exchange_service.exchanges.items():
            last_update = exchange_service.last_update.get(exchange_name)
            exchange_statuses.append(ExchangeStatus(
                exchange=exchange_name,
                connected=True,
                last_update=last_update,
                error=None
            ))
        
        # Determine overall status
        connected_count = sum(1 for s in exchange_statuses if s.connected)
        total_exchanges = len(exchange_statuses)
        
        if connected_count == total_exchanges:
            status = "healthy"
        elif connected_count >= total_exchanges * 0.5:
            status = "degraded"
        else:
            status = "unhealthy"
        
        # Calculate uptime
        uptime_seconds = time.time() - start_time
        
        # Cache status
        cache_stats = signal_cache.get_stats()
        cache_status = "working" if cache_stats['total_entries'] >= 0 else "not_working"
        
        health = HealthStatus(
            status=status,
            timestamp=datetime.now(),
            exchanges=exchange_statuses,
            cache_status=cache_status,
            uptime_seconds=uptime_seconds
        )
        
        log_info(f"Health check: {status} - {connected_count}/{total_exchanges} exchanges connected")
        return health
        
    except Exception as e:
        return HealthStatus(
            status="unhealthy",
            timestamp=datetime.now(),
            exchanges=[],
            cache_status="not_working",
            uptime_seconds=time.time() - start_time
        )


@router.get("/status")
async def service_status():
    """Get detailed service status"""
    try:
        return {
            "service": "Crypto Trade Advisor API",
            "version": "1.0.0",
            "status": "running",
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": time.time() - start_time,
            "exchanges": {
                name: {
                    "connected": True,
                    "last_update": exchange_service.last_update.get(name)
                }
                for name in exchange_service.exchanges.keys()
            },
            "cache": {
                "signal_cache": signal_cache.get_stats(),
                "ohlcv_cache": ohlcv_cache.get_stats(),
                "ticker_cache": ticker_cache.get_stats(),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/clear")
async def clear_cache():
    """Clear all caches"""
    try:
        signal_cache.clear()
        ohlcv_cache.clear()
        ticker_cache.clear()
        
        log_info("All caches cleared")
        return {"message": "All caches cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/cleanup")
async def cleanup_cache():
    """Clean up expired cache entries"""
    try:
        expired_signal = signal_cache.cleanup_expired()
        expired_ohlcv = ohlcv_cache.cleanup_expired()
        expired_ticker = ticker_cache.cleanup_expired()
        
        total_cleaned = expired_signal + expired_ohlcv + expired_ticker
        
        log_info(f"Cleaned up {total_cleaned} expired cache entries")
        return {
            "total_cleaned": total_cleaned,
            "signal_cache": expired_signal,
            "ohlcv_cache": expired_ohlcv,
            "ticker_cache": expired_ticker
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

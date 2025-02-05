from aiohttp import web
import logging

logger = logging.getLogger(__name__)

async def health_check(request):
    """Simple health check endpoint."""
    return web.Response(text='OK', status=200)

async def start_health_check():
    """Start the health check server."""
    app = web.Application()
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8000)
    await site.start()
    
    logger.info("Health check server started on http://0.0.0.0:8000/health") 
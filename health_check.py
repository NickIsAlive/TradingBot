from flask import Flask
import threading
import logging

logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/health')
def health_check():
    """Simple health check endpoint."""
    return 'OK', 200

def run_health_check_server():
    """Run the health check server."""
    try:
        app.run(host='0.0.0.0', port=8000)
    except Exception as e:
        logger.error(f"Health check server error: {str(e)}")
        # Don't let health check errors crash the main bot
        pass

def start_health_check():
    """Start the health check server in a separate thread."""
    thread = threading.Thread(target=run_health_check_server)
    thread.daemon = True  # Thread will be terminated when main program exits
    thread.start()
    logger.info("Health check server started on http://0.0.0.0:8000/health") 
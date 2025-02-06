#!/usr/bin/env python3
import os
import signal
import psutil
import logging
from notifications import SINGLETON_LOCK_FILE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup_bot():
    """Kill all bot processes and clean up lock files."""
    try:
        # Read PID from lock file if it exists
        if os.path.exists(SINGLETON_LOCK_FILE):
            try:
                with open(SINGLETON_LOCK_FILE, 'r') as f:
                    pid = int(f.read().strip())
                    try:
                        # Kill the process
                        os.kill(pid, signal.SIGTERM)
                        logger.info(f"Killed process {pid}")
                    except ProcessLookupError:
                        logger.info(f"Process {pid} not found")
            except Exception as e:
                logger.error(f"Error reading lock file: {e}")
            
            # Remove lock file
            try:
                os.remove(SINGLETON_LOCK_FILE)
                logger.info("Removed lock file")
            except Exception as e:
                logger.error(f"Error removing lock file: {e}")

        # Find and kill any python processes containing "main.py"
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and 'python' in cmdline[0] and any('main.py' in arg for arg in cmdline):
                    os.kill(proc.info['pid'], signal.SIGTERM)
                    logger.info(f"Killed process {proc.info['pid']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

if __name__ == "__main__":
    cleanup_bot() 
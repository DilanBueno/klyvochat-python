import sys
import signal
import logging
from pathlib import Path

from PySide6.QtWidgets import QApplication

from config import settings


def setup_logging():
    log_dir = Path("data")
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / "klyvochat.log"),
        ],
    )


def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting Klyvochat...")
    
    app = QApplication(sys.argv)
    app.setApplicationName("Klyvochat")
    
    from client.ui.windows.login_window import LoginWindow
    window = LoginWindow()
    window.show()
    
    def cleanup(signum, frame):
        logger.info("Shutting down...")
        app.quit()
    
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

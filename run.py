import sys
import signal

from PySide6.QtWidgets import QApplication
from qasync import QEventLoop

from config import settings


def main():
    from client.utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Starting Klyvochat...")

    app = QApplication(sys.argv)
    app.setApplicationName("Klyvochat")

    loop = QEventLoop(app)
    sys.attach_loop(loop)

    from client.main import AppController
    controller = AppController()
    controller.start()

    def cleanup(signum, frame):
        logger.info("Shutting down...")
        app.quit()

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    with loop:
        loop.run_forever()

    sys.exit(0)


if __name__ == "__main__":
    main()

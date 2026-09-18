import signal
import sys

from PySide6.QtWidgets import QApplication
from qasync import QEventLoop


def main():
    from client.utils.logger import get_logger

    logger = get_logger(__name__)
    logger.info("Starting Klyvochat...")

    app = QApplication(sys.argv)
    app.setApplicationName("Klyvochat")

    from client.ui.theme import theme

    theme.apply(app)

    loop = QEventLoop(app)
    if hasattr(sys, "attach_loop"):
        sys.attach_loop(loop)

    from client.storage import (
        models as _models,  # noqa: F401  (registra metadata antes do create_all)
    )
    from client.storage.database import init_db

    init_db()

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

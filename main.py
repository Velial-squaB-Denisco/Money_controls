import sys

from PySide6.QtWidgets import QApplication

from app.db import SessionLocal, engine
from app.db_migrations import apply_manual_migrations
from app.models import Base
from app.seed import seed_initial_data
from app.services import interest_service, recurring_service
from app.ui import theme
from app.ui.main_window import MainWindow


def init_db() -> None:
    Base.metadata.create_all(engine)


def process_recurring_rules() -> None:
    try:
        with SessionLocal() as session:
            created_count = recurring_service.generate_due_transactions(session)
            session.commit()

            if created_count > 0:
                print(f"Создано автоопераций: {created_count}")
    except Exception as exception:
        print(f"Ошибка обработки автоопераций: {exception}")


def process_interest() -> None:
    try:
        with SessionLocal() as session:
            created_count = interest_service.process_all(session)
            session.commit()

            if created_count > 0:
                print(f"Создано операций процентов и платежей: {created_count}")
    except Exception as exception:
        print(f"Ошибка обработки процентов: {exception}")


if __name__ == "__main__":
    init_db()
    apply_manual_migrations(engine)
    seed_initial_data()
    process_recurring_rules()
    process_interest()

    app = QApplication(sys.argv)

    theme.apply_theme()

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
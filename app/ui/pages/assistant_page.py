import json

from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.db import SessionLocal
from app.repositories import (
    llm_chat_repository,
    llm_insight_repository,
)
from app.services import llm_context_builder, llm_service
from app.ui import theme
from app.ui.helpers import markdown_helper
from app.ui.widgets.loading_dots import LoadingDotsWidget
from app.ui.helpers.form_style import style_table, style_toolbar


REQUEST_TYPE_LABELS = {
    "month_analysis": "Анализ месяца",
    "anomaly": "Поиск аномалий",
    "budget_recommendations": "Рекомендации по бюджетам",
    "debt_deposit_analysis": "Анализ долгов и вкладов",
}


class LLMWorker(QThread):
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        messages: list[dict],
        request_type: str,
        context: dict,
        model_name: str,
        parent=None,
    ):
        super().__init__(parent)

        self.messages = messages
        self.request_type = request_type
        self.context = context
        self.model_name = model_name

    def run(self):
        try:
            with SessionLocal() as session:
                settings = llm_service.get_llm_settings(session)

            response_text = llm_service.complete(
                settings=settings,
                messages=self.messages,
            )

            context_json = json.dumps(
                self.context,
                ensure_ascii=False,
                indent=2,
            )

            period = self.context.get("period")

            with SessionLocal() as session:
                llm_insight_repository.create_insight(
                    session=session,
                    request_type=self.request_type,
                    period=period,
                    context_json=context_json,
                    response_text=response_text,
                    model_name=self.model_name,
                )

                session.commit()

            self.finished_ok.emit(response_text)
        except Exception as exception:
            self.failed.emit(str(exception))


class ChatWorker(QThread):
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, messages: list[dict], parent=None):
        super().__init__(parent)

        self.messages = messages

    def run(self):
        try:
            with SessionLocal() as session:
                settings = llm_service.get_llm_settings(session)

            response_text = llm_service.complete(
                settings=settings,
                messages=self.messages,
            )

            self.finished_ok.emit(response_text)
        except Exception as exception:
            self.failed.emit(str(exception))


class AssistantPage(QWidget):
    def __init__(self):
        super().__init__()

        self._llm_worker: LLMWorker | None = None
        self._chat_worker: ChatWorker | None = None
        self._last_response_text: str | None = None

        layout = QVBoxLayout(self)

        title_label = QLabel("Ассистент")
        title_label.setObjectName("pageTitle")

        self.tabs = QTabWidget()

        assistant_tab = self.build_assistant_tab()
        chat_tab = self.build_chat_tab()
        history_tab = self.build_history_tab()

        self.tabs.addTab(assistant_tab, "Ассистент")
        self.tabs.addTab(chat_tab, "Чат")
        self.tabs.addTab(history_tab, "История")

        layout.addWidget(title_label)
        layout.addWidget(self.tabs)

        self.load_settings()
        self.load_history()
        self.load_sessions()

        self.show_response_placeholder("Нажми одну из кнопок, чтобы получить рекомендации")

    # =========================
    # Assistant tab
    # =========================

    def build_assistant_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        settings_group = QGroupBox("Настройки LLM")
        settings_form = QFormLayout(settings_group)

        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText(
            "Например: http://localhost:11434/v1"
        )

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("API key, если требуется")

        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("Например: llama3.1, gpt-4o-mini")

        save_settings_button = QPushButton("Сохранить настройки")
        save_settings_button.clicked.connect(self.save_settings)

        settings_form.addRow("Base URL", self.base_url_edit)
        settings_form.addRow("API key", self.api_key_edit)
        settings_form.addRow("Модель", self.model_edit)
        settings_form.addRow("", save_settings_button)

        buttons_layout = QHBoxLayout()

        self.quick_buttons = []

        analyze_button = QPushButton("Проанализировать текущий месяц")
        analyze_button.clicked.connect(
            lambda _: self.run_prompt(
                llm_context_builder.build_month_analysis_messages,
                "month_analysis",
            )
        )

        anomaly_button = QPushButton("Найти аномалии")
        anomaly_button.clicked.connect(
            lambda _: self.run_prompt(
                llm_context_builder.build_anomaly_messages,
                "anomaly",
            )
        )

        budget_button = QPushButton("Рекомендации по бюджетам")
        budget_button.clicked.connect(
            lambda _: self.run_prompt(
                llm_context_builder.build_budget_recommendation_messages,
                "budget_recommendations",
            )
        )

        debt_button = QPushButton("Анализ долгов и вкладов")
        debt_button.clicked.connect(
            lambda _: self.run_prompt(
                llm_context_builder.build_debt_and_deposit_messages,
                "debt_deposit_analysis",
            )
        )

        self.quick_buttons.append(analyze_button)
        self.quick_buttons.append(anomaly_button)
        self.quick_buttons.append(budget_button)
        self.quick_buttons.append(debt_button)

        buttons_layout.addWidget(analyze_button)
        buttons_layout.addWidget(anomaly_button)
        buttons_layout.addWidget(budget_button)
        buttons_layout.addWidget(debt_button)
        buttons_layout.addStretch()

        self.response_view = QWebEngineView()
        self.response_loading = LoadingDotsWidget("Ассистент готовит ответ")

        self.response_stack = QStackedWidget()
        self.response_stack.addWidget(self.response_view)
        self.response_stack.addWidget(self.response_loading)

        layout.addWidget(settings_group)
        layout.addLayout(buttons_layout)
        layout.addWidget(self.response_stack)

        return widget

    def current_theme(self) -> str:
        return theme.get_theme()

    def show_response_placeholder(self, text: str) -> None:
        html = markdown_helper.plain_page_html(text, self.current_theme())
        self.response_view.setHtml(html)
        self.response_stack.setCurrentWidget(self.response_view)

    def show_response_markdown(self, markdown_text: str) -> None:
        html = markdown_helper.markdown_page_html(markdown_text, self.current_theme())
        self.response_view.setHtml(html)
        self.response_stack.setCurrentWidget(self.response_view)

    def show_response_loading(self) -> None:
        self.response_loading.start()
        self.response_stack.setCurrentWidget(self.response_loading)

    def hide_response_loading(self) -> None:
        self.response_loading.stop()

    def set_quick_buttons_enabled(self, enabled: bool) -> None:
        for button in self.quick_buttons:
            button.setEnabled(enabled)

    def load_settings(self) -> None:
        with SessionLocal() as session:
            settings = llm_service.get_llm_settings(session)

        self.base_url_edit.setText(settings.get("base_url") or "")
        self.api_key_edit.setText(settings.get("api_key") or "")
        self.model_edit.setText(settings.get("model") or "")

    def save_settings(self) -> None:
        base_url = self.base_url_edit.text().strip()
        api_key = self.api_key_edit.text().strip()
        model = self.model_edit.text().strip()

        with SessionLocal() as session:
            llm_service.save_llm_settings(
                session=session,
                base_url=base_url,
                api_key=api_key,
                model=model,
            )

            session.commit()

        QMessageBox.information(
            self,
            "Настройки сохранены",
            "Настройки LLM сохранены",
        )

    def run_prompt(self, message_builder, request_type: str) -> None:
        if self._llm_worker is not None and self._llm_worker.isRunning():
            QMessageBox.information(
                self,
                "Запрос уже выполняется",
                "Дождись завершения текущего запроса",
            )
            return

        self.set_quick_buttons_enabled(False)
        self.show_response_loading()

        try:
            with SessionLocal() as session:
                context = llm_context_builder.build_month_context(session)
                settings = llm_service.get_llm_settings(session)

            messages = message_builder(context)
        except Exception as exception:
            self.hide_response_loading()
            self.set_quick_buttons_enabled(True)
            self.show_response_placeholder(f"Ошибка:\n{exception}")
            return

        worker = LLMWorker(
            messages=messages,
            request_type=request_type,
            context=context,
            model_name=settings.get("model") or "",
            parent=self,
        )

        worker.finished_ok.connect(self.on_llm_success)
        worker.failed.connect(self.on_llm_failed)

        self._llm_worker = worker
        worker.start()

    def on_llm_success(self, response_text: str) -> None:
        self._last_response_text = response_text

        self.hide_response_loading()
        self.set_quick_buttons_enabled(True)

        self.show_response_markdown(response_text)
        self.load_history()

    def on_llm_failed(self, error_text: str) -> None:
        self.hide_response_loading()
        self.set_quick_buttons_enabled(True)

        self.show_response_placeholder(f"Ошибка:\n{error_text}")

    # =========================
    # Chat tab
    # =========================

    def build_chat_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        toolbar_layout = QHBoxLayout()
        style_toolbar(toolbar_layout)

        chat_label = QLabel("Чат:")

        self.session_combo = QComboBox()
        self.session_combo.setMinimumWidth(320)

        new_chat_button = QPushButton("＋  Новый чат")
        new_chat_button.setObjectName("secondaryButton")
        new_chat_button.clicked.connect(self.new_chat)

        delete_chat_button = QPushButton("Удалить чат")
        delete_chat_button.setObjectName("dangerButton")
        delete_chat_button.clicked.connect(self.delete_current_chat)

        toolbar_layout.addWidget(chat_label)
        toolbar_layout.addWidget(self.session_combo)
        toolbar_layout.addWidget(new_chat_button)
        toolbar_layout.addWidget(delete_chat_button)
        toolbar_layout.addStretch()

        self.chat_view = QWebEngineView()

        self.chat_loading = LoadingDotsWidget("Ассистент печатает")
        self.chat_loading.setVisible(False)

        input_layout = QHBoxLayout()

        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText(
            "Например: Где я могу сэкономить?"
        )

        self.send_chat_button = QPushButton("Отправить")
        self.send_chat_button.clicked.connect(self.send_chat_message)

        self.chat_input.returnPressed.connect(self.send_chat_message)

        input_layout.addWidget(self.chat_input)
        input_layout.addWidget(self.send_chat_button)

        layout.addLayout(toolbar_layout)
        layout.addWidget(self.chat_view)
        layout.addWidget(self.chat_loading)
        layout.addLayout(input_layout)

        self.session_combo.currentIndexChanged.connect(self.on_session_changed)

        return widget

    def load_sessions(self, select_session_id: int | None = None) -> None:
        with SessionLocal() as session:
            sessions = llm_chat_repository.get_sessions(session)

            if not sessions:
                new_session = llm_chat_repository.create_session(session)
                session.commit()
                sessions = [new_session]

        self.session_combo.blockSignals(True)
        self.session_combo.clear()

        for chat_session in sessions:
            if chat_session.created_at is not None:
                created_label = chat_session.created_at.strftime("%d.%m.%Y %H:%M")
            else:
                created_label = "-"

            label = f"{created_label} — {chat_session.title}"

            self.session_combo.addItem(label, chat_session.id)

        selected_index = 0

        if select_session_id is not None:
            for index in range(self.session_combo.count()):
                if self.session_combo.itemData(index) == select_session_id:
                    selected_index = index
                    break

        self.session_combo.setCurrentIndex(selected_index)
        self.session_combo.blockSignals(False)

        self.on_session_changed(selected_index)

    def on_session_changed(self, index: int) -> None:
        if index < 0:
            return

        self.load_current_session_messages()

    def new_chat(self) -> None:
        with SessionLocal() as session:
            new_session = llm_chat_repository.create_session(session)
            session.commit()

        self.load_sessions(select_session_id=new_session.id)

    def delete_current_chat(self) -> None:
        session_id = self.session_combo.currentData()

        if session_id is None:
            QMessageBox.information(
                self,
                "Чат не выбран",
                "Выбери чат, чтобы удалить его",
            )
            return

        result = QMessageBox.question(
            self,
            "Удаление чата",
            "Удалить выбранный чат вместе с перепиской?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if result != QMessageBox.StandardButton.Yes:
            return

        session = SessionLocal()

        try:
            llm_chat_repository.delete_session(
                session=session,
                session_id=session_id,
            )

            session.commit()
        except Exception as exception:
            session.rollback()
            QMessageBox.critical(self, "Ошибка", str(exception))
            return
        finally:
            session.close()

        self.load_sessions()

    def load_current_session_messages(self) -> None:
        session_id = self.session_combo.currentData()

        if session_id is None:
            html = markdown_helper.chat_page_html([], self.current_theme())
            self.chat_view.setHtml(html)
            return

        with SessionLocal() as session:
            messages = llm_chat_repository.get_messages(
                session=session,
                chat_session_id=session_id,
            )

        message_dicts = [
            {
                "role": message.role,
                "content": message.content,
            }
            for message in messages
        ]

        html = markdown_helper.chat_page_html(message_dicts, self.current_theme())
        self.chat_view.setHtml(html)

        QTimer.singleShot(200, self.scroll_chat_to_bottom)

    def scroll_chat_to_bottom(self) -> None:
        try:
            self.chat_view.page().runJavaScript(
                "window.scrollTo(0, document.body.scrollHeight);"
            )
        except Exception:
            pass

    def _enable_chat_input(self) -> None:
        self.chat_input.setEnabled(True)
        self.send_chat_button.setEnabled(True)
        self.chat_input.setFocus()

    def send_chat_message(self) -> None:
        try:
            text = self.chat_input.text().strip()

            if not text:
                return

            if self._chat_worker is not None and self._chat_worker.isRunning():
                QMessageBox.information(
                    self,
                    "Запрос уже выполняется",
                    "Дождись ответа ассистента",
                )
                return

            chat_session_id = self.session_combo.currentData()

            if chat_session_id is None:
                self.load_sessions()
                chat_session_id = self.session_combo.currentData()

            if chat_session_id is None:
                QMessageBox.warning(
                    self,
                    "Ошибка чата",
                    "Не удалось получить или создать текущий чат",
                )
                return

            with SessionLocal() as session:
                settings = llm_service.get_llm_settings(session)

            base_url = (settings.get("base_url") or "").strip()
            model = (settings.get("model") or "").strip()

            if not base_url or not model:
                QMessageBox.warning(
                    self,
                    "Настройки LLM",
                    "Сначала укажи Base URL и модель во вкладке Ассистент",
                )
                return

            try:
                with SessionLocal() as session:
                    llm_chat_repository.add_message(
                        session=session,
                        chat_session_id=chat_session_id,
                        role="user",
                        content=text,
                    )

                    session.commit()
            except Exception as exception:
                QMessageBox.critical(
                    self,
                    "Ошибка сохранения сообщения",
                    str(exception),
                )
                return

            self.chat_input.clear()
            self.chat_input.setEnabled(False)
            self.send_chat_button.setEnabled(False)

            self.load_current_session_messages()

            self.chat_loading.setVisible(True)
            self.chat_loading.start()

            try:
                with SessionLocal() as session:
                    context = llm_context_builder.build_month_context(session)
                    db_messages = llm_chat_repository.get_messages(
                        session=session,
                        chat_session_id=chat_session_id,
                    )

                messages = [
                    {
                        "role": "system",
                        "content": llm_context_builder.build_chat_system_prompt(context),
                    }
                ]

                for message in db_messages[-30:]:
                    messages.append(
                        {
                            "role": message.role,
                            "content": message.content,
                        }
                    )
            except Exception as exception:
                self.chat_loading.stop()
                self.chat_loading.setVisible(False)
                self._enable_chat_input()
                QMessageBox.critical(
                    self,
                    "Ошибка подготовки данных",
                    str(exception),
                )
                return

            worker = ChatWorker(messages=messages, parent=self)

            worker.finished_ok.connect(self.on_chat_success)
            worker.failed.connect(self.on_chat_failed)

            self._chat_worker = worker
            worker.start()

        except Exception as exception:
            self.chat_loading.stop()
            self.chat_loading.setVisible(False)
            self._enable_chat_input()
            QMessageBox.critical(
                self,
                "Неожиданная ошибка чата",
                str(exception),
            )

    def on_chat_success(self, response_text: str) -> None:
        try:
            chat_session_id = self.session_combo.currentData()

            if chat_session_id is not None:
                try:
                    with SessionLocal() as session:
                        llm_chat_repository.add_message(
                            session=session,
                            chat_session_id=chat_session_id,
                            role="assistant",
                            content=response_text,
                        )

                        session.commit()
                except Exception as exception:
                    QMessageBox.warning(
                        self,
                        "Ответ получен, но не сохранен",
                        str(exception),
                    )

            self.chat_loading.stop()
            self.chat_loading.setVisible(False)

            self.load_current_session_messages()
        finally:
            self._enable_chat_input()

    def on_chat_failed(self, error_text: str) -> None:
        self.chat_loading.stop()
        self.chat_loading.setVisible(False)

        QMessageBox.critical(
            self,
            "Ошибка ассистента",
            error_text,
        )

        self._enable_chat_input()

    # =========================
    # History tab
    # =========================

    def build_history_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        toolbar_layout = QHBoxLayout()
        style_toolbar(toolbar_layout)

        refresh_button = QPushButton("Обновить")
        refresh_button.setObjectName("secondaryButton")
        refresh_button.clicked.connect(self.load_history)

        delete_button = QPushButton("Удалить")
        delete_button.setObjectName("dangerButton")
        delete_button.clicked.connect(self.delete_selected_insight)

        toolbar_layout.addWidget(refresh_button)
        toolbar_layout.addWidget(delete_button)
        toolbar_layout.addStretch()

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels(
            [
                "Дата",
                "Тип запроса",
                "Период",
                "Модель",
            ]
        )

        style_table(self.history_table)

        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)

        self.history_table.itemSelectionChanged.connect(
            self.load_selected_insight
        )

        self.history_response_view = QWebEngineView()

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.history_table)
        splitter.addWidget(self.history_response_view)

        layout.addLayout(toolbar_layout)
        layout.addWidget(splitter)

        return widget

    def load_history(self) -> None:
        with SessionLocal() as session:
            insights = llm_insight_repository.get_history(session)

        self.history_table.setRowCount(len(insights))

        for row_index, insight in enumerate(insights):
            if insight.created_at is not None:
                created_label = insight.created_at.strftime("%d.%m.%Y %H:%M")
            else:
                created_label = "-"

            request_type_label = REQUEST_TYPE_LABELS.get(
                insight.request_type,
                insight.request_type,
            )

            date_item = QTableWidgetItem(created_label)
            date_item.setData(Qt.UserRole, insight.id)

            type_item = QTableWidgetItem(request_type_label)
            period_item = QTableWidgetItem(insight.period or "-")
            model_item = QTableWidgetItem(insight.model_name or "-")

            self.history_table.setItem(row_index, 0, date_item)
            self.history_table.setItem(row_index, 1, type_item)
            self.history_table.setItem(row_index, 2, period_item)
            self.history_table.setItem(row_index, 3, model_item)

        self.history_table.resizeColumnsToContents()

        header = self.history_table.horizontalHeader()
        header.setStretchLastSection(True)

    def get_selected_insight_id(self) -> int | None:
        current_row = self.history_table.currentRow()

        if current_row < 0:
            return None

        item = self.history_table.item(current_row, 0)

        if item is None:
            return None

        return item.data(Qt.UserRole)

    def load_selected_insight(self) -> None:
        insight_id = self.get_selected_insight_id()

        if insight_id is None:
            html = markdown_helper.plain_page_html(
                "Выбери запись, чтобы посмотреть ответ",
                self.current_theme(),
            )
            self.history_response_view.setHtml(html)
            return

        with SessionLocal() as session:
            insight = llm_insight_repository.get_insight_by_id(
                session=session,
                insight_id=insight_id,
            )

        if insight is None:
            html = markdown_helper.plain_page_html(
                "Запись не найдена",
                self.current_theme(),
            )
            self.history_response_view.setHtml(html)
            return

        html = markdown_helper.markdown_page_html(
            insight.response_text,
            self.current_theme(),
        )

        self.history_response_view.setHtml(html)

    def delete_selected_insight(self) -> None:
        insight_id = self.get_selected_insight_id()

        if insight_id is None:
            QMessageBox.information(
                self,
                "Запись не выбрана",
                "Выбери запись истории, чтобы удалить ее",
            )
            return

        result = QMessageBox.question(
            self,
            "Удаление записи",
            "Удалить выбранную запись истории?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if result != QMessageBox.StandardButton.Yes:
            return

        session = SessionLocal()

        try:
            llm_insight_repository.delete_insight(
                session=session,
                insight_id=insight_id,
            )

            session.commit()
        except Exception as exception:
            session.rollback()
            QMessageBox.critical(self, "Ошибка", str(exception))
            return
        finally:
            session.close()

        html = markdown_helper.plain_page_html(
            "Выбери запись, чтобы посмотреть ответ",
            self.current_theme(),
        )

        self.history_response_view.setHtml(html)

        self.load_history()

    # =========================
    # Refresh for theme changes
    # =========================

    def refresh(self) -> None:
        if self._last_response_text:
            self.show_response_markdown(self._last_response_text)

        self.load_history()
        self.load_current_session_messages()
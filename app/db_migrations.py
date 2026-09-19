from sqlalchemy import inspect, text


def apply_manual_migrations(engine) -> None:
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS recurring_rules_new"))

        if "accounts" in tables:
            columns = {
                column["name"]
                for column in inspector.get_columns("accounts")
            }

            additions = [
                ("type", "VARCHAR(20) DEFAULT 'card'"),
                ("annual_rate_bp", "INTEGER"),
                ("monthly_payment_minor", "INTEGER"),
                ("payment_day", "INTEGER"),
                ("payment_from_account_id", "INTEGER"),
                ("interest_day", "INTEGER"),
                ("auto_start_date", "DATE"),
                ("next_due_date", "DATE"),
            ]

            for column_name, column_type in additions:
                if column_name not in columns:
                    connection.execute(
                        text(
                            f"ALTER TABLE accounts ADD COLUMN {column_name} {column_type}"
                        )
                    )

        if "transaction_items" in tables:
            columns = {
                column["name"]
                for column in inspector.get_columns("transaction_items")
            }

            if "quantity" not in columns:
                connection.execute(
                    text(
                        "ALTER TABLE transaction_items ADD COLUMN quantity INTEGER DEFAULT 1"
                    )
                )

            if "unit_price_minor" not in columns:
                connection.execute(
                    text(
                        "ALTER TABLE transaction_items ADD COLUMN unit_price_minor INTEGER"
                    )
                )

        if "transactions" in tables:
            columns = {
                column["name"]
                for column in inspector.get_columns("transactions")
            }

            if "transfer_to_account_id" not in columns:
                connection.execute(
                    text(
                        "ALTER TABLE transactions ADD COLUMN transfer_to_account_id INTEGER"
                    )
                )

            if "transfer_to_amount_minor" not in columns:
                connection.execute(
                    text(
                        "ALTER TABLE transactions ADD COLUMN transfer_to_amount_minor INTEGER"
                    )
                )

        if "recurring_rules" in tables:
            columns = {
                column["name"]
                for column in inspector.get_columns("recurring_rules")
            }

            if "transfer_to_account_id" not in columns:
                connection.execute(
                    text(
                        "ALTER TABLE recurring_rules ADD COLUMN transfer_to_account_id INTEGER"
                    )
                )
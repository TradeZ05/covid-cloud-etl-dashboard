from transform_load import connect_db, refresh_serving_layer
from db_config import get_db_password


def main():
    password = get_db_password(prompt=True)
    conn = connect_db(password)
    try:
        refresh_serving_layer(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()

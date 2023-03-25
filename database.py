import psycopg2


class Repository:
    """Класс для инкапсуляции работы с постгрес-базой"""
    TABLE_NAME = 'users'

    def __init__(self):
        pass

    def __enter__(self):
        self.conn = psycopg2.connect(
            database='Diploma',
            user='postgres',
            password='Ilovemy40cats',
            host='localhost',
            port='5432'
        )
        self.cursor = self.conn.cursor()
        self.__create_db()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cursor.close()
        self.conn.close()

    def __create_db(self):
        """Создаём таблицу для данных, кому кого показывали"""
        self.cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
        id_alone integer NOT NULL,
        id_partner integer NOT NULL,
        PRIMARY KEY (id_alone, id_partner) 
        );
        ''')
        self.conn.commit()

    def insert_user_pair(self, user, user_partner):
        """Записываем, кому кого показали"""
        self.cursor.execute(
            f"INSERT INTO {self.TABLE_NAME} (id_alone,id_partner) "
            f"VALUES ({user['id']},{user_partner['id']})"
        )
        self.conn.commit()

    def is_known_partner(self, user, user_partner) -> bool:
        """Проверяем показывали ли пользователю этого партнера"""
        self.cursor.execute(
            f"SELECT * FROM {self.TABLE_NAME} "
            f"WHERE id_alone = {user['id']} and id_partner = {user_partner['id']}"
        )
        if self.cursor.fetchone():
            return True
        return False

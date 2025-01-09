import mysql.connector

def get_db_connection():
    return mysql.connector.connect(
        host="58.72.151.123",
        user="human2",  # MySQL 사용자 이름
        password="Passw0rd!123",  # MySQL 비밀번호
        database="mydb"  # 데이터베이스 이름
    )

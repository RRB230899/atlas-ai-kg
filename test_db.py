import psycopg2


conn = psycopg2.connect(
    dbname="atlas_db",
    user="atlas_user",
    password="atlas_pass",
    host="localhost",
    port=5432
)

curr = conn.cursor()

curr.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
print(curr.fetchall())

curr.close()
conn.close()

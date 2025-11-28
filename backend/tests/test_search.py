from sentence_transformers import SentenceTransformer
from backend.fastapi.utils import get_conn

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
qvec = model.encode("your query here").tolist()

conn = get_conn()
cur = conn.cursor()
cur.execute("""
SELECT c.id, c.document_id, d.title, SUBSTRING(c.text FOR 400) AS excerpt,
       (c.embedding <-> %s::vector) AS score
FROM chunk c JOIN document d ON d.id = c.document_id
ORDER BY c.embedding <-> %s::vector
LIMIT 5;
""", (qvec, qvec))
rows = cur.fetchall()
for r in rows:
    print("doc:", r[2], "score:", r[4])
    print(r[3])
    print("----")
cur.close(); conn.close()

from rank_bm25 import BM25Okapi
import psycopg2
import nltk
nltk.download('punkt')

def fetch_all_chunks(conn):
    cur = conn.cursor()
    cur.execute("SELECT id, text FROM chunk")
    rows = cur.fetchall()
    cur.close()
    return rows

def build_bm25_index(rows):
    corpus = [nltk.word_tokenize(r[1].lower()) for r in rows]
    bm25 = BM25Okapi(corpus)
    return bm25

def bm25_search(query, rows, bm25, k=10):
    tokenized_q = nltk.word_tokenize(query.lower())
    scores = bm25.get_scores(tokenized_q)
    top_idxs = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
    
    results = []
    for i in top_idxs:
        chunk_id, text = rows[i]
        results.append({
            "chunk_id": chunk_id,
            "text": text,
            "bm25_score": float(scores[i])
        })
    return results

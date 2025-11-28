from colbert import ColBERT, Searcher

COLBERT_INDEX_PATH = "./colbert_index"

def get_colbert():
    return ColBERT.from_pretrained("colbert-ir/colbertv2.0")

def load_searcher():
    return Searcher(COLBERT_INDEX_PATH)

def colbert_search(query, searcher, k=10):
    results = searcher.search(query, k=k)
    # results: list of (score, doc_id)
    formatted = []
    for score, doc_id in results:
        formatted.append({
            "chunk_id": doc_id,
            "colbert_score": float(score)
        })
    return formatted

"""Vector search for memories using TF-IDF (pure Python, zero deps)."""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import List, Tuple, Dict

_STOPWORDS = {
    "the","a","an","is","are","was","were","be","been","being","to","of","and",
    "in","on","at","by","for","with","about","from","up","down","out","off","over",
    "under","again","further","then","once","here","there","when","where","why","how",
    "all","any","both","each","few","more","most","other","some","such","no","nor",
    "not","only","own","same","so","than","too","very","can","will","just","should",
    "now","this","that","these","those","it","its","as","or","if","have","has","had",
    "do","does","did","doing","done","get","use","make","go","see","know","take",
    "come","think","say","also","back","after","two","way","even","new","want",
    "because","first","well","any","work","may","give","look","find","day","could",
    "long","great","world","year","still","might","last","right","old","put","around",
    "every","part","much","el","la","lo","los","las","un","una","es","son","fue",
    "ser","sido","siendo","de","y","en","por","para","con","sobre","entre","hacia",
    "durante","antes","después","desde","hasta","que","quien","cual","cuando","donde",
    "como","porque","si","pero","o","ya","muy","mas","más","todo","todos","cada",
    "alguno","poco","muchos","mucho","muchas","otro","otros","este","esta","esto",
    "estos","estas","ese","esa","eso","esos","esas","aqui","alli","allí","ahora",
    "entonces","aun","aún","bien","mal","tan","tanto","tanta","asi","así","ni",
    "sino","sin","solo","solamente","mismo","mientras","ademas","además","tambien",
    "también","luego","sí","no","nunca","siempre","jamás","hace","hacer","hecho",
    "tenido","tenía","tenemos","tienes","tengo","haber","hay","está","estan",
    "estoy","era","eran","fui","fuimos","dar","dado","decir","dicho","ir","voy",
    "va","vengo","viene","ver","vi","saber","sé","creo","poder","puedo","puede",
    "querer","quiero","parecer","parece","deber","debo","debe","pensar","pienso",
}


def _tokenize(text: str) -> List[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 2]


def _tfidf_vectors(docs: List[str]) -> Tuple[List[Counter], Dict[str, int]]:
    vocab: Dict[str, int] = {}
    doc_tokens: List[List[str]] = []
    for doc in docs:
        tokens = _tokenize(doc)
        doc_tokens.append(tokens)
        for t in set(tokens):
            vocab[t] = vocab.get(t, 0) + 1
    n = len(docs)
    vectors: List[Counter] = []
    for tokens in doc_tokens:
        tf = Counter(tokens)
        vec = Counter()
        for term, count in tf.items():
            idf = math.log(n / (1 + vocab[term]))
            vec[term] = count * idf
        vectors.append(vec)
    return vectors, vocab


def _cosine(a: Counter, b: Counter) -> float:
    dot = sum(a[t] * b[t] for t in a if t in b)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def search_similar_memories(query: str, memories: List[Tuple[str, str]], top_k: int = 5) -> List[Tuple[str, float]]:
    """Search memories by semantic similarity.

    Args:
        query: search query text
        memories: list of (id, content) tuples
        top_k: number of results to return

    Returns:
        list of (memory_id, score) sorted by relevance
    """
    if not memories:
        return []
    contents = [content for _, content in memories]
    vectors, _ = _tfidf_vectors(contents + [query])
    query_vec = vectors[-1]
    results = []
    for i, (mem_id, _) in enumerate(memories):
        score = _cosine(query_vec, vectors[i])
        if score > 0.01:
            results.append((mem_id, score))
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_k]

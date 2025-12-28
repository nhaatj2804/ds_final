import numpy as np
import pandas as pd
import chromadb

from app.database import MOVIES, RATINGS

CHROMA_PATH = "app/chroma_db"

_client = chromadb.PersistentClient(path=CHROMA_PATH)
_collection = _client.get_collection("movies")


# ----------------------------
# Utilities
# ----------------------------
def genre_jaccard(g1, g2):
    if not g1 or not g2:
        return 0.0
    s1, s2 = set(g1.split()), set(g2.split())
    return len(s1 & s2) / len(s1 | s2)


def get_movie_embedding(movie_id: int):
    res = _collection.get(
        where={"movie_id": str(movie_id)},
        include=["embeddings"]
    )

    # ✅ Proper empty check
    if res is None:
        return None

    embeddings = res.get("embeddings")

    if embeddings is None or len(embeddings) == 0:
        return None

    return np.mean(np.array(embeddings), axis=0)


# -------------------------------------------------
# Basic search (unchanged)
# -------------------------------------------------
def search_movies(query=None, genre=None, year=None):
    df = MOVIES.copy()

    if query:
        df = df[df["title"].str.contains(query, case=False, na=False)]

    if genre:
        df = df[df["genres_parsed"].str.contains(genre, case=False, na=False)]

    if year:
        df = df[df["release_year"] == int(year)]

    return df.sort_values("release_year", ascending=False)

# ----------------------------
# User-based recommender
# ----------------------------
def recommend_for_user(user_id: int, top_n: int = 20):
    ratings = RATINGS[RATINGS["userId"] == user_id]

    liked = ratings[ratings["rating"] >= 3.5]
    if liked.empty:
        return pd.DataFrame()

    rated_ids = set(ratings["movieId"])

    embeddings = []
    weights = []

    for _, r in liked.iterrows():
        emb = get_movie_embedding(int(r["movieId"]))
        if emb is not None:
            embeddings.append(emb)
            weights.append(r["rating"] - 2.5)

    if not embeddings:
        return pd.DataFrame()

    user_embedding = np.average(embeddings, axis=0, weights=weights)

    results = _collection.query(
        query_embeddings=[user_embedding.tolist()],
        n_results=200
    )

    scores = {}

    for i, meta in enumerate(results["metadatas"][0]):
        mid = int(meta["movie_id"])
        if mid in rated_ids:
            continue

        vec_score = 1 - results["distances"][0][i]

        movie_genres = MOVIES.loc[MOVIES["id"] == mid, "genres_parsed"].values
        user_genres = MOVIES.loc[
            MOVIES["id"].isin(liked["movieId"]),
            "genres_parsed"
        ].str.cat(sep=" ")

        genre_score = genre_jaccard(
            movie_genres[0] if len(movie_genres) else "",
            user_genres
        )

        final_score = 0.8 * vec_score + 0.2 * genre_score

        scores[mid] = max(scores.get(mid, 0), final_score)

    ranked_ids = sorted(scores, key=scores.get, reverse=True)[:top_n]

    return MOVIES[MOVIES["id"].isin(ranked_ids)].assign(
        score=lambda x: x["id"].map(scores)
    ).sort_values("score", ascending=False)

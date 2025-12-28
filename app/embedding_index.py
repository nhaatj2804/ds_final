import chromadb
from sentence_transformers import SentenceTransformer
import ast
import pandas as pd

from app.database import MOVIES, KEYWORDS

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
CHROMA_PATH = "app/chroma_db"


def parse_names(raw):
    if pd.isna(raw):
        return ""
    try:
        return " ".join(i["name"] for i in ast.literal_eval(raw))
    except:
        return ""


def build_movie_features():
    df = MOVIES.copy()

    df["genres_text"] = df["genres_parsed"].apply(parse_names)

    kw_map = KEYWORDS.set_index("id")["keywords"].to_dict()
    df["keywords_text"] = df["id"].map(lambda x: parse_names(kw_map.get(x)))

    df["overview"] = df["overview"].fillna("")

    return df[["id", "overview", "keywords_text", "genres_parsed"]]


def build_chroma_index():
    print("🔄 Building Chroma index (multi-vector)...")

    model = SentenceTransformer(MODEL_NAME)
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    try:
        client.delete_collection("movies")
    except:
        pass

    collection = client.create_collection(
        name="movies",
        metadata={"hnsw:space": "cosine"}
    )

    df = build_movie_features()

    for _, row in df.iterrows():
        movie_id = str(row["id"])

        overview_emb = model.encode(row["overview"])
        keyword_emb = model.encode(row["keywords_text"])

        collection.add(
            ids=[f"{movie_id}_overview"],
            embeddings=[overview_emb.tolist()],
            metadatas=[{
                "movie_id": movie_id,
                "type": "overview",
                "genres": row["genres_parsed"]
            }]
        )

        collection.add(
            ids=[f"{movie_id}_keywords"],
            embeddings=[keyword_emb.tolist()],
            metadatas=[{
                "movie_id": movie_id,
                "type": "keywords",
                "genres": row["genres_parsed"]
            }]
        )

    print(f"✅ Stored {collection.count()} embeddings")


if __name__ == "__main__":
    build_chroma_index()

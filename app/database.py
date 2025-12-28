# app/database.py
import pandas as pd

MOVIES = pd.read_csv("data/processed/Movies.csv")
KEYWORDS = pd.read_csv("data/processed/Keywords.csv")
RATINGS = pd.read_csv("data/processed/Ratings.csv")

# clean
MOVIES["release_year"] = pd.to_datetime(
    MOVIES["release_date"], errors="coerce"
).dt.year

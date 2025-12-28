# app/main.py
from fastapi import FastAPI, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import ast
import math
from datetime import datetime, time
from app.auth import authenticate
from app.database import MOVIES, RATINGS, KEYWORDS
from app.recommender import search_movies
from app.recommender import recommend_for_user
import pandas as pd
import time


app = FastAPI()


app.add_middleware(
    SessionMiddleware,
    secret_key="super-secret-key-change-this"
)


app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


# ---------- LOGIN ----------
@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    user_id: int | None = Depends(authenticate)
):
    if user_id is None:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Invalid username or password"
            },
            status_code=401
        )

    request.session["user_id"] = user_id
    return RedirectResponse("/recommend", status_code=302)



# ---------- VISUALIZE TAB ----------
@app.get("/visualize", response_class=HTMLResponse)
def visualize(request: Request):
    return templates.TemplateResponse(
        "visualize.html",
        {"request": request, "image": "/static/visualize/chart.png"}
    )


# ---------- RECOMMENDER ----------
@app.get("/recommend", response_class=HTMLResponse)
def recommend(
    request: Request,
    query: str | None = None,
    genre: str | None = None,
    year: str | None = None
):
    year_int = int(year) if year and year.isdigit() else None
    user_id = request.session.get("user_id")

    searched_movies = search_movies(query, genre, year_int)

    # ⭐ Personalized recommendations
    if user_id:
        print(f"Generating recommendations for user {user_id}")
        personalized_df = recommend_for_user(user_id, top_n=20)

        if not personalized_df.empty:
            recommended_movies = personalized_df.to_dict("records")
        else:
            recommended_movies = search_movies(None, None, None) \
                .head(20) \
                .to_dict("records")
    else:
        recommended_movies = search_movies(None, None, None) \
            .head(20) \
            .to_dict("records")

    # Genre sections (unchanged)
    action_movies = search_movies(None, "Action", None).head(20)
    horror_movies = search_movies(None, "Horror", None).head(20)
    romance_movies = search_movies(None, "Romance", None).head(20)

    return templates.TemplateResponse(
        "recommend.html",
        {
            "request": request,

            "recommended_movies": recommended_movies,
            "action_movies": action_movies.to_dict("records"),
            "horror_movies": horror_movies.to_dict("records"),
            "romance_movies": romance_movies.to_dict("records"),

            "movies": searched_movies.to_dict("records"),
            "genres": sorted(
                MOVIES["genres_parsed"]
                .dropna()
                .str.findall(r"'name': '([^']+)'")
                .explode()
                .dropna()
                .unique()
            ),
            "years": sorted(
                MOVIES["release_year"]
                .dropna()
                .astype(int)
                .unique(),
                reverse=True
            ),
            "query": query,
            "selected_genre": genre,
            "selected_year": year_int,
        }
    )



# ---------- MOVIE DETAIL ----------
# app/main.py (Only the movie_detail function needs changing)

@app.get("/movie/{movie_id}", response_class=HTMLResponse)
def movie_detail(request: Request, movie_id: int):
    movie = MOVIES[MOVIES["id"] == movie_id].iloc[0]

    # 1. Global Average Rating
    ratings = RATINGS[RATINGS["movieId"] == movie_id]
    avg_rating = round(ratings["rating"].mean(), 1) if not ratings.empty else None

    # 2. Check if THIS user has rated the movie
    user_id = request.session.get("user_id")
    user_rating = None
    
    if user_id:
        # Filter for this user AND this movie
        existing_rating = RATINGS[
            (RATINGS["userId"] == user_id) & 
            (RATINGS["movieId"] == movie_id)
        ]
        
        # If a row is found, get the rating value
        if not existing_rating.empty:
            user_rating = existing_rating.iloc[0]["rating"]

    # 3. Genres Parsing
    raw_genres = movie["genres_parsed"]
    if isinstance(raw_genres, str):
        genres_list = ast.literal_eval(raw_genres)
        genres_str = ", ".join(g["name"] for g in genres_list)
    elif isinstance(raw_genres, list):
        genres_str = ", ".join(g["name"] for g in raw_genres)
    else:
        genres_str = "N/A"

    # 4. Keywords Parsing
    keywords_row = KEYWORDS[KEYWORDS["id"] == movie_id]
    if not keywords_row.empty:
        raw_kw = keywords_row["keywords"].iloc[0]
        kw_list = ast.literal_eval(raw_kw)
        keywords_str = ", ".join(k["name"] for k in kw_list)
    else:
        keywords_str = "N/A"

    return templates.TemplateResponse(
        "movie_detail.html",
        {
            "request": request,
            "movie": movie,
            "avg_rating": avg_rating,
            "genres": genres_str,
            "keywords": keywords_str,
            "user_rating": user_rating  # <--- Pass this to the template
        }
    )


# ---------- BROWSE ALL MOVIES (NEW) ----------
@app.get("/all-movies", response_class=HTMLResponse)
def browse_movies(request: Request, page: int = 1):
    limit = 48  # Number of movies per page
    total_movies = len(MOVIES)
    total_pages = math.ceil(total_movies / limit)

    # Ensure page is within valid range
    if page < 1: page = 1
    if page > total_pages: page = total_pages

    # Calculate start and end indices
    start = (page - 1) * limit
    end = start + limit

    # Get the slice of movies
    movies_batch = MOVIES.iloc[start:end]

    return templates.TemplateResponse(
        "all_movies.html",
        {
            "request": request,
            "movies": movies_batch.to_dict("records"),
            "page": page,
            "total_pages": total_pages
        }
    )



# ---------- RATE MOVIE ----------
@app.post("/rate")
def rate_movie(
    request: Request,
    movieId: int = Form(...),
    rating: float = Form(...)
):
    user_id = request.session.get("user_id")

    if user_id is None:
        return RedirectResponse("/", status_code=302)

    # ⏱ Current timestamp (Unix time)
    # ⏱ Current timestamp (nanoseconds, MovieLens-compatible)
    timestamp = int(time.time() * 1_000_000_000)

    RATINGS.loc[len(RATINGS)] = [
        user_id,
        movieId,
        rating,
        timestamp
    ]


    # 🔁 Force recommender to re-run
    recommend_for_user(user_id, top_n=20)

    # Redirect user to recommendations
    return RedirectResponse("/recommend", status_code=302)

# app/auth.py
from fastapi import Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordRequestForm

def authenticate(
    username: str = Form(...),
    password: str = Form(...)
):
    if password != "123":
        return None

    try:
        return int(username)
    except ValueError:
        return None
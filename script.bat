@echo off
call .env\Scripts\activate
py scripts\crypto.py
py scripts\stock.py
deactivate
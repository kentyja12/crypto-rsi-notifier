@echo off
call .env\Scripts\activate
py scripts\main.py
deactivate
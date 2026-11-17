@echo off
REM KeyStow - Windows setup
python -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
echo.
echo Done! Run the app with:  python -m keystow
pause

@echo off
setlocal
SET PYTHON=python
%PYTHON% -m uvicorn admin_server:app --reload --port 8000
endlocal

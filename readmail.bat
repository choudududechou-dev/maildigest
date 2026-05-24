@echo off
title Mail Digest
echo.
echo =========================================
echo   Mail Digest - reading all mailboxes...
echo =========================================
echo.
cd /d C:\Users\84395\mail-digest
python mail_digest.py
echo.
echo =========================================
echo   Done! Window closes in 10 seconds...
echo =========================================
timeout /t 10 /nobreak

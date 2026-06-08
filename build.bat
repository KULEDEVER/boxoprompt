@echo off
setlocal

cd /d "%~dp0"

where javac >nul 2>nul
if errorlevel 1 (
    echo Java compiler not found.
    echo Install a free JDK, then run this script again.
    echo BOXOPROMPT source supports Java 8 or newer.
    exit /b 1
)

if not exist build mkdir build
if not exist download\v2.x mkdir download\v2.x

javac -encoding UTF-8 -d build src\BoxoPrompt.java
if errorlevel 1 exit /b 1

echo Main-Class: BoxoPrompt> build\manifest.txt
jar cfm download\v2.x\BOXOPROMPT-v2.0.jar build\manifest.txt -C build .
if errorlevel 1 exit /b 1

echo Built download\v2.x\BOXOPROMPT-v2.0.jar

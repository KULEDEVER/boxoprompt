@echo off
setlocal

cd /d "%~dp0"

if exist download\v2.x\BOXOPROMPT-v2.0.jar (
    java -jar download\v2.x\BOXOPROMPT-v2.0.jar
) else (
    echo JAR not found. Run build.bat after installing a free JDK.
    exit /b 1
)

@echo off
rem dsh-pet — launch the dsh-pet-lulu capybara pet from this checkout (Windows).
rem Usage: bin\dsh-pet.cmd [pet options...]
setlocal
set "DIR=%~dp0.."
pushd "%DIR%"
python -m dsh_pet %*
set "CODE=%ERRORLEVEL%"
popd
endlocal & exit /b %CODE%

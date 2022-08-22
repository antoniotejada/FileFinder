REM Best way to install Python 2.7 PyQt5 on 32-bit Windows XP is through Anaconda,
REM try that path first. On systems without Anaconda this will fail and assumes
REM PyQt5 is installed via the regular pip installation
call anaconda.bat 2> NUL
REM anaconda.bat sets ERRORLEVEL to 1, check 9009 explicitly (bad command or 
REM filename).
REM %ERRORLEVEL% requires delayed expansion when used with call, use ERRORLEVEL
REM instead and since if ERRORLEVEL n means ERRORLEVEL >= n so also check < n+1
if ERRORLEVEL 9009 IF NOT ERRORLEVEL 9010 (
    REM This assumes the anaconda environment where Python 2.7 and PyQt5 are
    REM installed is called p2
    call activate p2

    REM Anaconda 2.2.0 fails to setup Qt properly, without creating a qt.conf or
    REM environment variables. 
    REM Find the Qt package and set QT_PLUGIN_PATH accordingly to fix that
    REM set QT_PLUGIN_PATH=C:\Anaconda\pkgs\qt-5.6.2-vc9_6\Library\plugins
    FOR /F "tokens=*" %%g IN ('conda list -c "^qt$"') do (SET QT_PLUGIN_PATH=%ANACONDA%\pkgs\%%g\Library\plugins)
)
echo QT_PLUGIN_PATH=%QT_PLUGIN_PATH%

set /p dirs=<"%~dp0filefinder.cfg"
echo dirs=%dirs%
"%~dp0filefinder.py" %dirs%
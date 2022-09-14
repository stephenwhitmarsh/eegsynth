REM this is a generic startup script for an EEGsynth module implemented in Python
REM it can be copied to any other file name

set rootdir=%userprofile%\eegsynth
set module=%~n0
set inidir=%~dp0
REM CALL conda activate EEGsynth
CALL %userprofile%\AppData\Local\Continuum\anaconda3\Scripts\activate EEGSynth
%rootdir%\bin\buffer.exe 1972 -new_console:t:"buffer1972"
%rootdir%\bin\buffer.exe 1973 -new_console:t:"buffer1973"
CALL TIMEOUT /T 3

REM python %rootdir%\module\inputcontrol\inputcontrol.py -i %inidir%\inputcontrol.ini -new_console:t:"inputcontrol"
REM python %rootdir%\module\plotimage\plotimage.py -i %inidir%\plotimage.ini -new_console:t:"plotimage"
REM python %rootdir%\module\lsl2ft\lsl2ft.py -i %inidir%\lsl2ft.ini -new_console:t:"lsl2ft"
REM python %rootdir%\module\preprocessing\preprocessing.py -i %inidir%\preprocessing.ini -new_console:t:"preprocessing"
REM python %rootdir%\module\plotsignal\plotsignal.py -i %inidir%\plotsignal.ini -new_console:t:"plotsignal"
REM python %rootdir%\module\recordsignal\recordsignal.py -i %inidir%\recordsignal_right.ini -new_console:t:"RIGHT_record"
REM python %rootdir%\module\recordsignal\recordsignal.py -i %inidir%\recordsignal_left.ini -new_console:t:"LEFT_record"
REM python %rootdir%\module\delaytrigger\delaytrigger.py -i %inidir%\delaytrigger.ini -new_console:t:"delaytrigger"

python %rootdir%\module\csp\csp.py -i %inidir%\csp.ini -new_console:t:"csp"

REM python %rootdir%\module\csp\csp.py -i %inidir%\csp.ini -new_console:t:"CSP"


REM python %rootdir%\module\spectral\spectral.py -i %inidir%\spectral.ini -new_console:t:"spectral"
REM python %rootdir%\module\historycontrol\historycontrol.py -i %inidir%\historycontrol.ini -new_console:t:"historycontrol"
REM python %rootdir%\module\postprocessing\postprocessing.py -i %inidir%\postprocessing.ini -new_console:t:"postprocessing"
REM python %rootdir%\module\plotcontrol\plotcontrol.py -i %inidir%\plotcontrol.ini -new_console:t:"plotsignal"
REM python %rootdir%\module\plotspectral\plotspectral.py -i %inidir%\plotspectral.ini -new_console:t:"plotspectral"
REM python %rootdir%\module\slewlimiter\slewlimiter.py -i %inidir%\slewlimiter.ini -new_console:t:"slewlimiter"
REM python %rootdir%\module\outputmidi\outputmidi.py -i %inidir%\outputmidi.ini -new_console:t:"outputmidi"
REM python %rootdir%\module\endorphines\endorphines.py -i %inidir%\endorphines.ini -new_console:t:"endorphines"
REM python %rootdir%\module\inputmidi\inputmidi.py -i %inidir%\inputmidi.ini -new_console:t:"inputmidi"
REM python %rootdir%\module\outputosc\outputosc.py -i %inidir%\outputosc.ini -new_console:t:"outputosc"
REM python %rootdir%\module\outputosc\outputosc.py -i %inidir%\outputosc2.ini -new_console:t:"outputosc2"

REM keep the command window open for debugging
pause

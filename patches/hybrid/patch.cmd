REM this is a generic startup script for an EEGsynth module implemented in Python
REM it can be copied to any other file name

set rootdir=%userprofile%\eegsynth
set module=%~n0
set inidir=%~dp0
REM CALL conda activate EEGsynth
CALL %userprofile%\AppData\Local\Continuum\anaconda3\Scripts\activate EEGSynth
%rootdir%\bin\buffer.exe 1972 -new_console:t:"buffer1972"
%rootdir%\bin\buffer.exe 1973 -new_console:t:"buffer1973"
%rootdir%\bin\buffer.exe 1974 -new_console:t:"buffer1974"
%rootdir%\bin\buffer.exe 1975 -new_console:t:"buffer1975"
CALL TIMEOUT /T 3

python %rootdir%\module\lsl2ft\lsl2ft.py -i %inidir%\lsl2ft_EEG.ini -new_console:t:"lsl2ft EEG"
python %rootdir%\module\preprocessing\preprocessing.py -i %inidir%\preprocessing_EEG.ini -new_console:t:"preproc EEG"
python %rootdir%\module\plotsignal\plotsignal.py -i %inidir%\plotsignal_EEG.ini -new_console:t:"plotsig EEG"
python %rootdir%\module\inputcontrol\inputcontrol.py -i %inidir%\inputcontrol.ini -new_console:t:"inputcontrol"
python %rootdir%\module\spectral\spectral.py -i %inidir%\spectral.ini -new_console:t:"spectral"
python %rootdir%\module\historycontrol\historycontrol.py -i %inidir%\historycontrol_EEG.ini -new_console:t:"histcont EEG"
python %rootdir%\module\plotcontrol\plotcontrol.py -i %inidir%\plotcontrol.ini -new_console:t:"plotsignal"
python %rootdir%\module\plotspectral\plotspectral.py -i %inidir%\plotspectral.ini -new_console:t:"plotspectral"
python %rootdir%\module\slewlimiter\slewlimiter.py -i %inidir%\slewlimiter.ini -new_console:t:"slewlimiter"
REM python %rootdir%\module\outputmidi\outputmidi.py -i %inidir%\outputmidi.ini -new_console:t:"outputmidi"
REM python %rootdir%\module\endorphines\endorphines.py -i %inidir%\endorphines.ini -new_console:t:"endorphines"
REM python %rootdir%\module\inputmidi\inputmidi.py -i %inidir%\inputmidi.ini -new_console:t:"inputmidi"
python %rootdir%\module\outputosc\outputosc.py -i %inidir%\outputosc.ini -new_console:t:"outputosc"

python %rootdir%\module\lsl2ft\lsl2ft.py -i %inidir%\lsl2ft_EMG.ini -new_console:t:"lsl2ft EMG"
python %rootdir%\module\preprocessing\preprocessing.py -i %inidir%\preprocessing_EMG.ini -new_console:t:"preproc EMG"
python %rootdir%\module\plotsignal\plotsignal.py -i %inidir%\plotsignal_EMG.ini -new_console:t:"plotsig EMG"
python %rootdir%\module\rms\rms.py -i %inidir%\rms.ini -new_console:t:"RMS"
python %rootdir%\module\historycontrol\historycontrol.py -i %inidir%\historycontrol_EMG.ini -new_console:t:"histcont EMG"

python %rootdir%\module\postprocessing\postprocessing.py -i %inidir%\postprocessing.ini -new_console:t:"postprocessing"

REM keep the command window open for debugging
pause

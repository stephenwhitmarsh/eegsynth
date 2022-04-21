# Patch for hybrid EEG-EMG processing

This patch is an example for using hybrid EEG-EMG processing in the EEGsynth. It outputs OSC control signals reflecting (A) power of different frequency bands at different electrodes locations (using a new montage functionality in the preprocessing), and (B) the root-mean-square (RMS) of 4 EMG channels. It was tested using LSL to transfer of EEG and EMG data from the Mentalab Explore and OpenBCI ganglion, respectively. A Pure Data patch is included to converts OSC signals to DC audio for the ES-9 in a uErorack system.

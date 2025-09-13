# Recording

Although the primary use of the EEGsynth is to perform real-time analysis and to use the control signals for direct feedback, there are cases where it can be useful to record the data to disk. One of these is when you want to optimize a certain signal processing algorithm, another is if you want to replay the control signals to try out different analog patches of a synthesizer or light system.

- The [recordsignal module](../src/module/recordsignal) reads the physiological data from the FieldTrip buffer and writes it to an EDF file, or to a WAV audio file. This module will also send a synchronization message to Redis at regular timepoints, with the current sample number in the file as the value.

- The [recordcontrol module](../src/module/recordcontrol) reads the control signals for selected channels from the Redis buffer and writes it to an EDF file, or to a WAV audio file. This module will also send a synchronization message to Redis at regular timepoints, with the current sample number in the file as the value.

- The [recordtrigger module](../src/module/recordtrigger) subscribes to specific pub/sub channels in Redis and writes a TSV file. Each row of the TSV file has the event name, event value and the timestamp of the event (as date and time according to the clock). By default, this module will also write the synchronization messages that are created by the [recordsignal module](../src/module/recordsignal) and [recordcontrol module](../src/module/recordcontrol). This allows to post-hoc synchronize the physiological and control signal to each other and to other events.

## Playing recorded signals back

You can use the [playbacksignal module](../src/module/playbacksignal) to play physiological signals from a file back to the FieldTrip buffer. This module will try to play the signals in real-time, i.e. with a speed that matches the original recording.

You can use the [playbackcontrol module](../src/module/playbackcontrol) to play control signals from a file back to the Redis buffer. This module will try to play the signals in real-time, i.e. with a speed that matches the original recording.

## Simulating physiological and control signals

You can use the [generatesignal](../src/module/generatesignal) and the [generatecontrol](../src/module/generatecontrol) modules to simulate physiological signals that are sent to the FieldTrip buffer, or control signals that are sent to the Redis buffer. Both modules allow you to patch them, such that you can use for example the LaunchControl to manipulate the properties of the signals in real-time.

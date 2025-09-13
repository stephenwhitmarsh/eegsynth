# Keyboard module

This module receives and sends MIDI commands from/to a keyboard such as a digital piano. This implementation has specifically been tested with a [Yamaha P95](http://usa.yamaha.com/products/musical-instruments/keyboards/digitalpianos/p_series/p-95_color_variation/), but should work with any keyboard that supports bi-directional MIDI communication.

The MIDI commands received from the piano corresponding to keys that are pressed are translated into a single control value representing the pitch. The force with which the key is pressed is send as trigger for each of the keys. Both the control value and the trigger are send to the Redis buffer. You can filter on key press and release events.

The MIDI commands that should be send to the keyboard correspond to pub/sub messages from the Redis buffer.

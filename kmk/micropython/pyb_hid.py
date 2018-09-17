import logging
import string

from pyb import USB_HID, delay

from kmk.common.consts import Keycodes, char_lookup


class HIDHelper:
    '''
    Wraps a HID reporting event. The structure of such events is (courtesy of
    http://wiki.micropython.org/USB-HID-Keyboard-mode-example-a-password-dongle):

    >Byte 0 is for a modifier key, or combination thereof. It is used as a
    >bitmap, each bit mapped to a modifier:
    >    bit 0: left control
    >    bit 1: left shift
    >    bit 2: left alt
    >    bit 3: left GUI (Win/Apple/Meta key)
    >    bit 4: right control
    >    bit 5: right shift
    >    bit 6: right alt
    >    bit 7: right GUI
    >
    >    Examples: 0x02 for Shift, 0x05 for Control+Alt
    >
    >Byte 1 is "reserved" (unused, actually)
    >Bytes 2-7 are for the actual key scancode(s) - up to 6 at a time ("chording").

    Most methods here return `self` upon completion, allowing chaining:

    ```python
    myhid = HIDHelper()
    myhid.send_string('testing').send_string(' ... and testing again')
    ```
    '''
    def __init__(self, log_level=logging.NOTSET):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)

        self._hid = USB_HID()
        self.clear_all()

    def send(self):
        self.logger.debug('Sending HID report: {}'.format(self._evt))
        self._hid.send(self._evt)

        return self

    def send_string(self, message):
        '''
        Clears the HID report, and sends along a string of arbitrary length.
        All keys will be released at the completion of the string. Modifiers
        are not really supported here, though Shift will be pressed if
        necessary to output the key.
        '''

        self.clear_all()
        self.send()

        for char in message:
            kc = None
            modifier = None

            if char in char_lookup:
                kc, modifier = char_lookup[char]
            elif char in string.ascii_letters + string.digits:
                kc = getattr(Keycodes.Common, 'KC_{}'.format(char.upper()))
                modifier = Keycodes.Modifiers.KC_SHIFT if char.isupper() else None

            if modifier:
                self.enable_modifier(modifier)

            self.add_key(kc)
            self.send()

            # Without this delay, events get clobbered and you'll likely end up with
            # a string like `heloooooooooooooooo` rather than `hello`. This number
            # may be able to be shrunken down. It may also make sense to use
            # time.sleep_us or time.sleep_ms or time.sleep (platform dependent)
            # on non-Pyboards.
            delay(10)

            # Release all keys or we'll forever hold whatever the last keypress was
            self.clear_all()
            self.send()

        return self

    def clear_all(self):
        self._evt = bytearray(8)
        return self

    def clear_non_modifiers(self):
        for pos in range(2, 8):
            self._evt[pos] = 0x00

        return self

    def enable_modifier(self, modifier):
        if Keycodes.Modifiers.contains(modifier):
            self._evt[0] |= modifier
            return self

        raise ValueError('Attempted to use non-modifier as a modifier')

    def add_key(self, key):
        if key and Keycodes.contains(key):
            # Try to find the first empty slot in the key report, and fill it
            placed = False
            for pos in range(2, 8):
                if self._evt[pos] == 0x00:
                    self._evt[pos] = key
                    placed = True
                    break

            if not placed:
                raise ValueError('Out of space in HID report, could not add key')

            return self

        raise ValueError('Invalid keycode?')

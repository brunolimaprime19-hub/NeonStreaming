import logging
import os

IS_WINDOWS = os.name == "nt"

if not IS_WINDOWS:
    from evdev import UInput, ecodes, AbsInfo
else:
    try:
        import vgamepad as vg
    except ImportError:
        vg = None

logger = logging.getLogger("InputManager")

class InputManager:
    def __init__(self):
        # --- GAMEPAD (Xbox Style) ---
        cap_gamepad = {
            ecodes.EV_KEY: [
                ecodes.BTN_A, ecodes.BTN_B, ecodes.BTN_X, ecodes.BTN_Y,
                ecodes.BTN_TL, ecodes.BTN_TR, ecodes.BTN_SELECT, ecodes.BTN_START,
                ecodes.BTN_MODE, ecodes.BTN_THUMBL, ecodes.BTN_THUMBR
            ],
            ecodes.EV_ABS: [
                (ecodes.ABS_X, AbsInfo(value=0, min=-32768, max=32767, fuzz=0, flat=0, resolution=0)),
                (ecodes.ABS_Y, AbsInfo(value=0, min=-32768, max=32767, fuzz=0, flat=0, resolution=0)),
                (ecodes.ABS_RX, AbsInfo(value=0, min=-32768, max=32767, fuzz=0, flat=0, resolution=0)),
                (ecodes.ABS_RY, AbsInfo(value=0, min=-32768, max=32767, fuzz=0, flat=0, resolution=0)),
                (ecodes.ABS_Z, AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)),
                (ecodes.ABS_RZ, AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)),
                (ecodes.ABS_HAT0X, AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)),
                (ecodes.ABS_HAT0Y, AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)),
            ]
        }
        
        try:
            if not IS_WINDOWS:
                self.ui_gamepad = UInput(cap_gamepad, name="NeonGamepad", version=0x1)
                logger.info("Virtual Device Created: Gamepad (evdev)")
            else:
                if vg:
                    self.ui_gamepad = vg.VX360Gamepad()
                    logger.info("Virtual Device Created: Gamepad (vgamepad)")
                else:
                    self.ui_gamepad = None
                    logger.error("vgamepad not installed. Run 'pip install vgamepad'")
        except Exception as e:
            self.ui_gamepad = None
            logger.error(f"Failed to create Virtual Gamepad: {e}")

    def handle_input(self, data):
        type_ = data.get('type')
        code = data.get('code')
        value = data.get('value')

        if not self.ui_gamepad:
            logger.error("CRITICAL: Virtual Gamepad not initialized (Check /dev/uinput permissions)")
            return

        if type_ == 'BUTTON':
            btn_map = {
                'A': ecodes.BTN_A, 'B': ecodes.BTN_B, 'X': ecodes.BTN_X, 'Y': ecodes.BTN_Y,
                'SELECT': ecodes.BTN_SELECT, 'START': ecodes.BTN_START,
                'HOME': ecodes.BTN_MODE, 'LB': ecodes.BTN_TL, 'RB': ecodes.BTN_TR,
                'L3': ecodes.BTN_THUMBL, 'R3': ecodes.BTN_THUMBR,
                'DPAD_UP': (ecodes.EV_ABS, ecodes.ABS_HAT0Y, -1),
                'DPAD_DOWN': (ecodes.EV_ABS, ecodes.ABS_HAT0Y, 1),
                'DPAD_LEFT': (ecodes.EV_ABS, ecodes.ABS_HAT0X, -1),
                'DPAD_RIGHT': (ecodes.EV_ABS, ecodes.ABS_HAT0X, 1),
                'LT': (ecodes.EV_ABS, ecodes.ABS_Z, 255),
                'RT': (ecodes.EV_ABS, ecodes.ABS_RZ, 255)
            }
            if code in btn_map:
                try:
                    mapped = btn_map[code]
                    if not IS_WINDOWS:
                        if isinstance(mapped, tuple):
                            val = mapped[2] if value else 0
                            self.ui_gamepad.write(mapped[0], mapped[1], val)
                        else:
                            self.ui_gamepad.write(ecodes.EV_KEY, mapped, 1 if value else 0)
                        self.ui_gamepad.syn()
                    else:
                        # vgamepad logic
                        vg_map = {
                            'A': vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
                            'B': vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
                            'X': vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
                            'Y': vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
                            'SELECT': vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
                            'START': vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
                            'HOME': vg.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE,
                            'LB': vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
                            'RB': vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
                            'L3': vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
                            'R3': vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
                            'DPAD_UP': vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
                            'DPAD_DOWN': vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
                            'DPAD_LEFT': vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
                            'DPAD_RIGHT': vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
                        }
                        if code in vg_map:
                            if value: self.ui_gamepad.press_button(button=vg_map[code])
                            else: self.ui_gamepad.release_button(button=vg_map[code])
                        elif code == 'LT':
                            self.ui_gamepad.left_trigger(value=int(value))
                        elif code == 'RT':
                            self.ui_gamepad.right_trigger(value=int(value))
                        self.ui_gamepad.update()
                except Exception as e:
                    logger.debug(f"Input handling error: {e}")

        elif type_ == 'AXIS':
            axis_map = {
                'LEFT_X': ecodes.ABS_X, 'LEFT_Y': ecodes.ABS_Y,
                'RIGHT_X': ecodes.ABS_RX, 'RIGHT_Y': ecodes.ABS_RY
            }
            if code in axis_map:
                try:
                    if not IS_WINDOWS:
                        self.ui_gamepad.write(ecodes.EV_ABS, axis_map[code], value)
                        self.ui_gamepad.syn()
                    else:
                        # vgamepad uses -32768 to 32767 for axes, same as we receive
                        if code == 'LEFT_X': self.ui_gamepad.left_joystick(x_value=int(value), y_value=None)
                        elif code == 'LEFT_Y': self.ui_gamepad.left_joystick(x_value=None, y_value=int(value))
                        elif code == 'RIGHT_X': self.ui_gamepad.right_joystick(x_value=int(value), y_value=None)
                        elif code == 'RIGHT_Y': self.ui_gamepad.right_joystick(x_value=None, y_value=int(value))
                        self.ui_gamepad.update()
                except Exception as e:
                    logger.debug(f"Axis handling error: {e}")

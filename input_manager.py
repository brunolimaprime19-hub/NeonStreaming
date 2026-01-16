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
        self.gamepads = {} # Map: index -> virtual_device
        
        # Capabilities template (Xbox Style)
        self.cap_gamepad = {
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
    def _get_gamepad(self, index):
        """Returns or creates a virtual gamepad for the given index."""
        if index in self.gamepads:
            return self.gamepads[index]
        
        try:
            device = None
            if not IS_WINDOWS:
                device = UInput(self.cap_gamepad, name=f"NeonGamepad P{index+1}", version=0x1)
                logger.info(f"Virtual Device Created: Gamepad P{index+1} (evdev)")
            else:
                if vg:
                    device = vg.VX360Gamepad()
                    logger.info(f"Virtual Device Created: Gamepad P{index+1} (vgamepad)")
                else:
                    logger.error("vgamepad not installed.")
            
            self.gamepads[index] = device
            return device
        except Exception as e:
            logger.error(f"Failed to create Virtual Gamepad P{index+1}: {e}")
            return None

    def handle_input(self, data):
        type_ = data.get('type')
        code = data.get('code')
        value = data.get('value')
        gp_index = data.get('gamepadIndex', 0)

        device = self._get_gamepad(gp_index)
        if not device:
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
                            device.write(mapped[0], mapped[1], val)
                        else:
                            device.write(ecodes.EV_KEY, mapped, 1 if value else 0)
                        device.syn()
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
                            if value: device.press_button(button=vg_map[code])
                            else: device.release_button(button=vg_map[code])
                        elif code == 'LT':
                            device.left_trigger(value=int(value))
                        elif code == 'RT':
                            device.right_trigger(value=int(value))
                        device.update()
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
                        device.write(ecodes.EV_ABS, axis_map[code], value)
                        device.syn()
                    else:
                        # vgamepad uses -32768 to 32767 for axes, same as we receive
                        if code == 'LEFT_X': device.left_joystick(x_value=int(value), y_value=None)
                        elif code == 'LEFT_Y': device.left_joystick(x_value=None, y_value=int(value))
                        elif code == 'RIGHT_X': device.right_joystick(x_value=int(value), y_value=None)
                        elif code == 'RIGHT_Y': device.right_joystick(x_value=None, y_value=int(value))
                        device.update()
                except Exception as e:
                    logger.debug(f"Axis handling error: {e}")

import argparse
import sys
import time

import serial


def send_command(port: serial.Serial, command: str, pause: float) -> str:
    wire = f"{command}\r".encode("ascii")
    port.reset_input_buffer()
    port.write(wire)
    time.sleep(pause)
    response = port.read_all().decode("ascii", errors="replace").strip()
    return response


def main() -> int:
    parser = argparse.ArgumentParser(description="Send direct test commands to a Coherent CUBE laser.")
    parser.add_argument("port", help="Serial port, for example COM3")
    parser.add_argument(
        "--pause",
        type=float,
        default=0.25,
        help="Seconds to wait for a reply after each command",
    )
    args = parser.parse_args()

    commands = [
        "?HID",
        "?SV",
        "?F",
        "?FL",
        "?STA",
        "?SS",
        "?SP",
        "?S",
    ]

    try:
        with serial.Serial(
            port=args.port,
            baudrate=19200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.5,
            write_timeout=0.5,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        ) as ser:
            print(f"Opened {args.port} at 19200 8N1")
            for command in commands:
                response = send_command(ser, command, args.pause)
                print(f"> {command}")
                print(f"< {response or '[no response]'}")
    except serial.SerialException as exc:
        print(f"Serial error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

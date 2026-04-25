import json
import math
import random
import socket
import time

# Network target and update rate for outgoing UDP packets.
IP = "127.0.0.1"
PORT = 5700
SEND_INTERVAL_SECONDS = 0.05

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def simulate_accelerometer(elapsed_time: float) -> dict[str, float]:
	# Simulate 3-axis movement with sine waves.
	# Using different frequencies/phases avoids perfectly synchronized motion.
	x = 0.8 * math.sin(2.0 * math.pi * 0.7 * elapsed_time)
	y = 0.6 * math.sin(2.0 * math.pi * 1.1 * elapsed_time + 0.8)
	z = 0.9 * math.sin(2.0 * math.pi * 0.4 * elapsed_time + 1.6)
	return {
		"x": round(x, 5),
		"y": round(y, 5),
		"z": round(z, 5),
	}


def simulate_button_1(
	now: float, button_state: int, next_button_toggle: float
) -> tuple[int, float]:
	# Keep current state until the scheduled toggle time is reached.
	if now < next_button_toggle:
		return button_state, next_button_toggle

	# Flip between released (0) and pressed (1).
	button_state = 1 - button_state
	# Press duration is shorter, release duration is longer to mimic tapping.
	if button_state == 1:
		next_button_toggle = now + random.uniform(0.1, 0.4)
	else:
		next_button_toggle = now + random.uniform(0.5, 2.0)

	return button_state, next_button_toggle


def main() -> None:
	start_time = time.monotonic()
	button_state = 0
	next_button_toggle = start_time + random.uniform(0.5, 2.0)

	# Main simulation loop: update values, build JSON payload, send.
	while True:
		now = time.monotonic()
		elapsed = now - start_time
		button_state, next_button_toggle = simulate_button_1(
			now, button_state, next_button_toggle
		)

		# DIPPID payload maps capability names to their current values.
		message_dict = {
			"accelerometer": simulate_accelerometer(elapsed),
			"button_1": button_state,
		}
		message = json.dumps(message_dict)

		# Send one UDP packet per iteration, then wait until next update.
		print(message)
		sock.sendto(message.encode(), (IP, PORT))
		time.sleep(SEND_INTERVAL_SECONDS)


if __name__ == "__main__":
	# Graceful shutdown: stop on Ctrl+C and always close the socket.
	try:
		main()
	except KeyboardInterrupt:
		print("\nSender stopped.")
	finally:
		sock.close()

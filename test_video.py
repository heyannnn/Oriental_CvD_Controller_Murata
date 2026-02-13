from pythonosc import udp_client

client = udp_client.SimpleUDPClient("127.0.0.1", 9000)

# client.send_message("/playlist/load", ["./Waiting.csv"])
client.send_message("/playlist/load", "NormalOperation.csv")
client.send_message("/quit", [])
class Client:
    def __init__(self, mac, signal):
        self.mac = mac
        self.signal = signal

    def __str__(self):
        return f'Client MAC: {self.mac}, Signal: {self.signal} dBm'

    def summary(self):
        return f'MAC: {self.mac}, Signal: {self.signal} dBm'

import config
import threading
import time
import udt
import util

# Selective Repeat transport protocol.
class SelectiveRepeat:

  NO_PREV_ACK_MSG = "Don't have previous ACK to send, will wait for server to timeout."

  # "msg_handler" is used to deliver messages to application layer
  def __init__(self, local_port, remote_port, msg_handler):
    util.log("Starting up `Selective Repeat` protocol ... ")
    self.network_layer = udt.NetworkLayer(local_port, remote_port, self)
    self.msg_handler = msg_handler
    self.sender_base = 0
    self.receiver_base = 0
    self.next_sequence_number = 0
    self.timer = [self.set_timer(-1)] * config.WINDOW_SIZE
    self.ack = [False] * config.WINDOW_SIZE
    self.rcv = [False] * config.WINDOW_SIZE
    self.rcv_pkg = [b''] * config.WINDOW_SIZE
    self.sent_pkg = [b''] * config.WINDOW_SIZE
    self.expected_sequence_number = 0
    # self.receiver_last_ack = b''
    self.is_receiver = True
    self.sender_lock = threading.Lock()


  def set_timer(self, count):
    return threading.Timer((config.TIMEOUT_MSEC/1000.0), self._timeout, {count: count})
    # self.timer = threading.Timer((config.TIMEOUT_MSEC/1000.0), self._timeout)


  # "send" is called by application. Return true on success, false otherwise.
  def send(self, msg):
    self.is_receiver = False
    if self.next_sequence_number < (self.sender_base + config.WINDOW_SIZE):
      self._send_helper(msg)
      return True
    else:
      util.log("Window is full. App data rejected.")
      time.sleep(1)
      return False


  # Helper fn for thread to send the next packet
  def _send_helper(self, msg):
    self.sender_lock.acquire()
    packet = util.make_packet(msg, config.MSG_TYPE_DATA, self.next_sequence_number)
    packet_data = util.extract_data(packet)
    # self.window[self.next_sequence_number%config.WINDOW_SIZE] = packet
    util.log("Sending data: " + util.pkt_to_string(packet_data))
    self.network_layer.send(packet)   
    if self.next_sequence_number < self.sender_base + config.WINDOW_SIZE:
      count = (self.next_sequence_number - self.sender_base)%config.WINDOW_SIZE
      if self.timer[count].is_alive(): self.timer[count].cancel()
      self.timer[count] = self.set_timer(self.next_sequence_number)
      self.timer[count].start()
      self.ack[count] = False
      self.sent_pkg[count] = packet
      # if self.timer.is_alive(): self.timer.cancel()
      # self.set_timer()
      # self.timer.start()
      self.next_sequence_number += 1
    self.sender_lock.release()
    return


  # "handler" to be called by network layer when packet is ready.
  def handle_arrival_msg(self):
    msg = self.network_layer.recv()
    msg_data = util.extract_data(msg)

    if(msg_data.is_corrupt):
      # if(self.is_receiver):
        # if self.expected_sequence_number == 0:
      util.log("Packet received is corrupted.")
        # return
      # self.network_layer.send(self.receiver_last_ack)
      # util.log("Received corrupted data. Resending ACK: "
                # + util.pkt_to_string(util.extract_data(self.receiver_last_ack)))
      return

    # If ACK message, assume its for sender
    if msg_data.msg_type == config.MSG_TYPE_ACK:
      self.sender_lock.acquire()
      count = (msg_data.seq_num - self.sender_base)%config.WINDOW_SIZE
      # self.sender_base = msg_data.seq_num + 1
      self.ack[count] = True
      
      # if(self.sender_base == self.next_sequence_number):
      util.log("Received ACK with seq #" + util.pkt_to_string(msg_data) + ". Cancelling timer.")
      if self.timer[count].is_alive(): self.timer[count].cancel()
      self.timer[count] = self.set_timer(msg_data.seq_num)
      
        # self.timer.cancel()
      # else:
      # util.log("Received ACK: " + util.pkt_to_string(msg_data) + ". There are messages in-flight. Restarting the timer.")

      # Sending and shifting ack list
      if self.ack[0] == True:
        shift_ind = next((i for i, b in enumerate(self.ack) if not b), None)
        self.sender_base += shift_ind
        print(f"New sender base is set to {self.sender_base}")
        self.ack = self.ack[shift_ind:] + [False] * shift_ind
        self.timer = self.timer[shift_ind:] + [self.set_timer(-1)] * shift_ind
        self.sent_pkg = self.sent_pkg[shift_ind:] + [b''] * shift_ind
      # if self.timer.is_alive(): self.timer.cancel()
      # self.set_timer()
      # self.timer.start()
      self.sender_lock.release()
    # If DATA message, assume its for receiver
    else:
      assert msg_data.msg_type == config.MSG_TYPE_DATA
      util.log("Received DATA: " + util.pkt_to_string(msg_data))
      ack_pkt = util.make_packet(b'', config.MSG_TYPE_ACK, msg_data.seq_num)

      if msg_data.seq_num in range(self.receiver_base, self.receiver_base + config.WINDOW_SIZE):
      # if msg_data.seq_num == self.expected_sequence_number:
        # self.msg_handler(msg_data.payload)
        # ack_pkt = util.make_packet(b'', config.MSG_TYPE_ACK, msg_data.seq_num)
        # self.network_layer.send(ack_pkt)
        self.network_layer.send(ack_pkt)
        util.log("Sent ACK: " + util.pkt_to_string(util.extract_data(ack_pkt)))
        count = (msg_data.seq_num - self.receiver_base) % config.WINDOW_SIZE
        self.rcv[count] = True
        self.rcv_pkg[count] = msg_data.payload
        
        if self.rcv[0] == True:
          shift_ind = next((i for i, b in enumerate(self.rcv) if not b), None)
          for i in range(shift_ind):
            self.msg_handler(self.rcv_pkg[i])
          self.receiver_base += shift_ind
          self.rcv = self.rcv[shift_ind:] + [False] * shift_ind
          self.rcv_pkg = self.rcv_pkg[shift_ind:] + [b''] * shift_ind
          print(f"New receiver base is set to {self.receiver_base}") 
 
        # self.receiver_last_ack = ack_pkt
        # self.expected_sequence_number += 1
        # util.log("Sent ACK: " + util.pkt_to_string(util.extract_data(ack_pkt)))
      # else:
        # if self.expected_sequence_number == 0:
          # util.log("Packet received is out of order. " + self.NO_PREV_ACK_MSG)
          # return
        # util.log("DATA message had unexpected sequence #"
                 # + str(int(msg_data.seq_num)) + ". Resending ACK message with sequence # "
                 # + str(int(self.expected_sequence_number-1)) + ".")
        # self.network_layer.send(self.receiver_last_ack)
      elif msg_data.seq_num < self.receiver_base:
        self.network_layer.send(ack_pkt)
        util.log("Sent ACK: " + util.pkt_to_string(util.extract_data(ack_pkt)))
        util.log("Packet outside receiver window")
    return


  # Cleanup resources.
  def shutdown(self):
    if not self.is_receiver: self._wait_for_last_ACK()
    for t in self.timer:
      if t.is_alive(): t.cancel()
    # if self.timer.is_alive(): self.timer.cancel()
    util.log("Connection shutting down...")
    self.network_layer.shutdown()


  def _wait_for_last_ACK(self):
    while self.sender_base < self.next_sequence_number-1:
      util.log("Waiting for last ACK from receiver with sequence # "
               + str(int(self.next_sequence_number-1)) + ".")
      time.sleep(1)


  def _timeout(self, count):
    pkt_num = (count - self.sender_base)%config.WINDOW_SIZE
    util.log("Timeout! Resending packet with seq #s "
             + str(pkt_num) +".")
    self.sender_lock.acquire()
    if self.timer[pkt_num].is_alive(): self.timer[pkt_num].cancel()
    self.timer[pkt_num] = self.set_timer(count)
    # if self.timer.is_alive(): self.timer.cancel()
    # self.set_timer()
    # for i in range(self.sender_base,self.next_sequence_number):
    pkt = self.sent_pkg[pkt_num]
    self.network_layer.send(pkt)
    util.log("Resending packet: " + util.pkt_to_string(util.extract_data(pkt)))
    self.timer[pkt_num].start()
    self.sender_lock.release()
    return

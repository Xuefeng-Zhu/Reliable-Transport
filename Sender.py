import sys
import getopt
import threading

import Checksum
import BasicSender

'''
This is a skeleton sender class. Create a fantastic transport protocol here.
'''

PACKET_SIZE = 1400
RETRANSMIT_TIME = 0.5


class Sender(BasicSender.BasicSender):
    def __init__(self, dest, port, filename, debug=False, sackMode=False):
        super(Sender, self).__init__(dest, port, filename, debug)
        self.sackMode = sackMode
        self.debug = debug
        self.max_buf_size = 7
        self.current_seqno = 0
        self.latest_ack_seqno = None
        self.latest_ack_count = 0
        self.fin_seqno = None
        self.unack_packets = {}
        self.timers = {}

    # Main sending loop.
    def start(self):
        self._send_syn()
        while True:
            message, _ = self.sock.recvfrom(4096)
            if self.debug:
                print "Sender.py: received %s" % (message)

            if Checksum.validate_checksum(message):
                self._handle_ack(message)
            elif self.debug:
                print "Sender.py: checksum failed: %s" % (message)

            if self.fin_seqno is None:
                self._send_data()

    def _handle_ack(self, message):
        msg_type, ack_seqno, _, _ = self.split_packet(message)
        try:
            if self.sackMode:
                ack_seqno, sack_seqnos = ack_seqno.split(";")
                sack_seqnos = sack_seqnos.split(",")\
                    if len(sack_seqnos) else []

            ack_seqno = int(ack_seqno)
        except:
            raise ValueError

        # fast retransmition
        if ack_seqno == self.latest_ack_seqno:
            self.latest_ack_count += 1
            if self.latest_ack_count == 4:
                timer = self.timers[ack_seqno]
                timer.cancel()
                self._resend_packet(ack_seqno)
            return
        else:
            self.latest_ack_seqno = ack_seqno
            self.latest_ack_count = 1

        if self.sackMode and len(sack_seqnos):
            print sack_seqnos
            for sack_seqno in map(int, sack_seqnos):
                if sack_seqno in self.unack_packets:
                    self._acknowledge_packet(sack_seqno)

        seqno = ack_seqno - 1
        for packet_seqno in self.unack_packets.keys():
            if packet_seqno <= seqno:
                self._acknowledge_packet(packet_seqno)

        if seqno == self.fin_seqno:
            if self.debug:
                print "receive fin ack"
            exit()

    def _acknowledge_packet(self, packet_seqno):
        timer = self.timers[packet_seqno]
        timer.cancel()
        del self.timers[packet_seqno]
        del self.unack_packets[packet_seqno]


    def _send_syn(self):
        if self.debug:
            print "send sync"
        packet = self.make_packet('syn', self.current_seqno, "")
        self._send_helper(packet)

    def _send_data(self):
        while len(self.unack_packets) < self.max_buf_size:
            msg = self.infile.read(PACKET_SIZE)

            if len(msg) == 0:
                self._send_fin()
                return

            if self.debug:
                print "send dat %d" % self.current_seqno
            packet = self.make_packet('dat', self.current_seqno, msg)
            self._send_helper(packet)

    def _send_fin(self):
        if self.debug:
            print "send fin %d" % self.current_seqno
        packet = self.make_packet('fin', self.current_seqno, "")
        self.fin_seqno = self.current_seqno
        self._send_helper(packet)

    def _send_helper(self, packet):
        self.unack_packets[self.current_seqno] = packet
        self.send(packet)
        self._set_timer(self.current_seqno)
        self.current_seqno += 1

    def _set_timer(self, seqno):
        timer = threading.Timer(RETRANSMIT_TIME, self._resend_packet,
                                args=[seqno])
        timer.start()
        self.timers[seqno] = timer

    def _resend_packet(self, seqno):
        packet = self.unack_packets.get(seqno)
        if packet:
            self.send(packet)
            self._set_timer(seqno)
            if self.debug:
                print "resend packet %d" % seqno
        else:
            del self.timers[seqno]


'''
This will be run if you run this script from the command line. You should not
change any of this; the grader may rely on the behavior here to test your
submission.
'''
if __name__ == "__main__":
    def usage():
        print "BEARS-TP Sender"
        print "-f FILE | --file=FILE The file to transfer; if empty reads from STDIN"
        print "-p PORT | --port=PORT The destination port, defaults to 33122"
        print "-a ADDRESS | --address=ADDRESS The receiver address or hostname, defaults to localhost"
        print "-d | --debug Print debug messages"
        print "-h | --help Print this usage message"
        print "-k | --sack Enable selective acknowledgement mode"

    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   "f:p:a:dk", ["file=", "port=", "address=", "debug=", "sack="])
    except:
        usage()
        exit()

    port = 33122
    dest = "localhost"
    filename = None
    debug = False
    sackMode = False

    for o, a in opts:
        if o in ("-f", "--file="):
            filename = a
        elif o in ("-p", "--port="):
            port = int(a)
        elif o in ("-a", "--address="):
            dest = a
        elif o in ("-d", "--debug="):
            debug = True
        elif o in ("-k", "--sack="):
            sackMode = True

    s = Sender(dest, port, filename, debug, sackMode)
    try:
        s.start()
    except (KeyboardInterrupt, SystemExit):
        exit()

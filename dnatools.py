__author__ = 'kablag'
import yaml
from PySide import QtCore
from PySide import QtNetwork

PORT          = 49200
SIZEOF_UINT32 = 4

def reverse_complement(sequence: str):
    return complement(reverse(sequence))

def reverse(sequence: str):
    return sequence[::-1]

def complement(sequence: str):
    table = "".maketrans("ATGCatgcRYMKSWBDHVNrymkswbdhvn", "TACGtacgYRKMSWVHDBNyrkmswvhdbn")
    return sequence.translate(table)

def calcGC(sequence: str):
    sequence = sequence.lower()
    at = sequence.count('a') + sequence.count('t')
    gc = sequence.count('g') + sequence.count('c')
    return (gc / (at + gc)) * 100

class MeltviewerConnector():
    def __init__(self, host='127.0.0.1', port=PORT):
        self.__socket = QtNetwork.QUdpSocket()

    def send(self, mtask):
        # mpoints = melt(text, reverse_complement(text), M_CONDS)
        # t = calc_t_at_conc([C_10, C_90], mpoints)
        # self.setWindowTitle('{}/{}'.format(conc[C_10], conc[C_90]))

        plots = [{'action': 'add_graph',
                            'a': mpot.a,
                            'b': mpot.b,
                            'length': mpot.length_of_a,
                            'gc%': mpot.gc_of_a,
                            't10': mpot.t10,
                            't90': mpot.t90,
                            'mpoints': mpot.mpoints_as_XY,
                            'color': 'rnd',
                            'marker': 'rnd',
                            }
                 for mpot in mtask.melting_pots]
        messages = [yaml.dump({'plots':[plot]}) for plot in plots]
        # message = yaml.dump({'plots':plots})
        # print(message)
        # self.__socket.writeDatagram(message,
        #                             QtNetwork.QHostAddress(QtNetwork.QHostAddress.Broadcast),
        #                             45454)
        for message in messages:
            self.__socket.writeDatagram(message,
                                    QtNetwork.QHostAddress(QtNetwork.QHostAddress.Broadcast),
                                    45454)


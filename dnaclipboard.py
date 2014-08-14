import sys
import os
import subprocess
import re
import time

from traceback import print_exc

import dbus
import dbus.mainloop.glib

from PySide import QtGui

from dnatools import *
from pyfold import MeltingConditions
from pyfold import MTask

UNAFOLD_PATH = ''
RAM_DISK = '/home/kablag/.ramdisk/'

A_CONC = 2e-7
C_10 = A_CONC * 0.1
C_90 = A_CONC * 0.9

M_CONDS = MeltingConditions(UNAFOLD_PATH, RAM_DISK, '30', '90',
                            '1', A_CONC, '5e-2', '3e-3')

def execBash(bashCommand):
    proc = subprocess.Popen(['bash', '-c', bashCommand], stdout=subprocess.PIPE)
    return proc.communicate()[0]




# get WID and name of window that executed this script
WID = execBash('xdotool getactivewindow')
wname = execBash('xdotool getwindowname {wid}'.format(wid=WID.decode())).decode()
mytitle = 'DNAclipboard: send to "{wname}"'.format(wname=wname)

# kill another instances of DNAclipboard
anotherIDs = execBash('xdotool search --name DNAclipboard:') \
    .decode().split('\n')
anotherIDs = filter(lambda el: not el == '', anotherIDs)
[execBash('xdotool windowkill {el}'.format(el=el)) for el in anotherIDs]


class SeqLine(QtGui.QWidget):
    def __init__(self, name, sequence, convertor, hotkey):
        super(SeqLine, self).__init__()
        layout = QtGui.QHBoxLayout()
        name = QtGui.QLabel(name)
        self.seqEdit = SeqLineEdit(convertor)
        self.length = QtGui.QLabel('0')
        send = QtGui.QPushButton(text='Send')
        send.clicked.connect(self.on_button_send)
        QtGui.QShortcut(QtGui.QKeySequence("Alt+"+hotkey), self,
                        self.on_button_send)
        melt = QtGui.QPushButton(text='Melt')
        QtGui.QShortcut(QtGui.QKeySequence("Alt+Shift+"+hotkey), self,
                        self.on_button_melt)
        melt.clicked.connect(self.on_button_melt)

        layout.addWidget(name)
        layout.addWidget(self.seqEdit)
        layout.addWidget(self.length)
        layout.addWidget(send)
        layout.addWidget(melt)

        self.setSequence(sequence)

        self.setLayout(layout)

    def on_button_send(self):
        os.system('bash -c "echo -n {text} | xclip -selection clipboard"'
                  .format(text=self.seqEdit.text()))#.__repr__()))
        execBash('''xdotool windowfocus --sync {wid};
                    xdotool key --clearmodifiers "ctrl+v";'''
                 .format(wid=WID.decode()[:-1]))
        QtCore.QCoreApplication.instance().quit()


    def on_button_melt(self):
        if execBash('xdotool search --name meltviewer').decode() == '':
            proc =  subprocess.Popen(
                ['python3m',
                '/home/kablag/private/workspace/snpick/meltviewer.py'],
                stdout=subprocess.PIPE
            )
            time.sleep(1)
        mtask = MTask(self.seqEdit.text())
        mtask.execute(M_CONDS)
        # self.connection.send(mtask)
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
        self.connect_to_meltviewer()
        self.iface.sendPlot(messages[0])

    def setSequence(self, sequence):
        self.seqEdit.setText(sequence)
        self.length.setText(str(len(self.seqEdit.text())))

    def connect_to_meltviewer(self):
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        bus = dbus.SessionBus()

        try:
            remote_object = bus.get_object("com.meltviewer.Graph",
                                           "/Graph")
            self.iface = dbus.Interface(remote_object, "com.meltviewer.Graph")
        except dbus.DBusException:
            print_exc()
            sys.exit(1)


class SeqLineEdit(QtGui.QLineEdit):
    def __init__(self, convertor=lambda x: x):
        super(SeqLineEdit, self).__init__()
        init_validator = re.compile('[^ATGCatgcRYMKSWBDHVNrymkswbdhvn()/\[\]\->]*')
        # sequence = init_validator.sub('', sequence)
        self.initUI(convertor)

    def initUI(self, convertor):
        self.convertor = convertor
        regexp = QtCore.QRegExp('[ATGCatgcRYMKSWBDHVNrymkswbdhvn()/\[\]\->]*')
        validator = QtGui.QRegExpValidator(regexp)
        font = QtGui.QFont('Ubuntu Mono')
        self.setFont(font)
        self.setValidator(validator)

    def toPlain(self):
        return self.convertor(self.text())



class DNAclipboard(QtGui.QWidget):
    def __init__(self):
        super(DNAclipboard, self).__init__()
        self.initUI()

    def initUI(self):
        self.clipboard = QtGui.QApplication.clipboard().text()
        selection = execBash('xclip -out;'
                             .format(wid=WID)).decode('utf-8')

        if selection == self.clipboard:
            selection = ''

        self.clipPlain = SeqLine('Plain',
                                 self.clipboard,
                                 lambda x: x,
                                 'a')
        self.clipPlain.seqEdit.textChanged.connect(
            self.on_clip_text_changed)
        self.clipRev = SeqLine('Rev.',
                                 reverse(self.clipboard),
                                 reverse,
                                 's')
        self.clipRev.seqEdit.textChanged.connect(
            self.on_clip_text_changed)
        self.clipComp = SeqLine('Comp.',
                                 complement(self.clipboard),
                                 complement,
                                 'd')
        self.clipComp.seqEdit.textChanged.connect(
            self.on_clip_text_changed)
        self.clipRevComp = SeqLine('Rev.Comp.',
                                 reverse_complement(self.clipboard),
                                 reverse_complement,
                                 'f')
        self.clipRevComp.seqEdit.textChanged.connect(
            self.on_clip_text_changed)

        self.selPlain = SeqLine('Plain',
                                 selection,
                                 lambda x: x,
                                 'q')
        self.selPlain.seqEdit.textChanged.connect(
            self.on_sel_text_changed)
        self.selRev = SeqLine('Rev.',
                                 reverse(selection),
                                 reverse,
                                 'w')
        self.selRev.seqEdit.textChanged.connect(
            self.on_sel_text_changed)
        self.selComp = SeqLine('Comp.',
                                 complement(selection),
                                 complement,
                                 'e')
        self.selComp.seqEdit.textChanged.connect(
            self.on_sel_text_changed)
        self.selRevComp = SeqLine('Rev.Comp.',
                                 reverse_complement(selection),
                                 reverse_complement,
                                 'r')
        self.selRevComp.seqEdit.textChanged.connect(
            self.on_sel_text_changed)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.clipPlain)
        layout.addWidget(self.clipRev)
        layout.addWidget(self.clipComp)
        layout.addWidget(self.clipRevComp)

        layout.addWidget(self.selPlain)
        layout.addWidget(self.selRev)
        layout.addWidget(self.selComp)
        layout.addWidget(self.selRevComp)

        self.setLayout(layout)
        self.setGeometry(300, 300, 600, 0)

        self.setWindowTitle(mytitle)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.show()


    def connect_to_meltviewer(self):
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        bus = dbus.SessionBus()

        try:
            remote_object = bus.get_object("com.meltviewer.Graph",
                                           "/Graph")
            self.iface = dbus.Interface(remote_object, "com.meltviewer.Graph")
        except dbus.DBusException:
            print_exc()
            sys.exit(1)

    def on_clip_text_changed(self):
        cursor_pos = self.sender().cursorPosition()
        text = self.sender().toPlain()
        self.clipPlain.setSequence(text)
        self.clipRev.setSequence(reverse(text))
        self.clipComp.setSequence(complement(text))
        self.clipRevComp.setSequence(
            reverse_complement(text))
        self.sender().setCursorPosition(cursor_pos)

    def on_sel_text_changed(self):
        cursor_pos = self.sender().cursorPosition()
        text = self.sender().toPlain()
        self.selPlain.setSequence(text)
        self.selRev.setSequence(reverse(text))
        self.selComp.setSequence(complement(text))
        self.selRevComp.setSequence(
            reverse_complement(text))
        self.sender().setCursorPosition(cursor_pos)

def main():
    app = QtGui.QApplication(sys.argv)
    main_view = DNAclipboard()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
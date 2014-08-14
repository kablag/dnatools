import sys
from random import randrange
from enum import Enum
import yaml

import dbus
import dbus.service
import dbus.mainloop.glib


import matplotlib
# import numpy as np
matplotlib.use('Qt4Agg')
matplotlib.rcParams['backend.qt4'] = 'PySide'
# import pylab

from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PySide import QtCore
from PySide import QtGui


from pyfold import MTask

COLORS        = 'bgrcmyk'
MARKERS       = '.ovDs*x'


class COLUMNS(Enum):
    ID = 0
    Show = 1
    Color = 2
    Marker = 3
    Sequence = 4
    Length = 5
    GC = 6
    t10 = 7
    t90 = 8



class MeltingPlot():
    def __init__(self, plot_yaml):
        self.sequence = plot_yaml['a']
        self.length = str(plot_yaml['length'])
        self.gc = '{:.0f} %'.format(plot_yaml['gc%'])
        self.mpoints = plot_yaml['mpoints']
        self.t10 = '{:.2f}'.format(plot_yaml['t10'])
        self.t90 = '{:.2f}'.format(plot_yaml['t90'])
        self.color = plot_yaml['color'] \
                            if plot_yaml['color'] != 'rnd' \
                            else COLORS[randrange(len(COLORS) - 1)]
        self.marker = plot_yaml['marker'] \
                            if plot_yaml['marker'] != 'rnd' \
                            else MARKERS[randrange(len(MARKERS) - 1)]
        self.show = True

class MatplotlibWidget(FigureCanvas):
    def __init__(self, parent=None,xlabel='x',
                 ylabel='y',
                 title='Title'):
        super(MatplotlibWidget, self).__init__(Figure())

        self.setParent(parent)
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.axes = self.figure.add_subplot(111)

        self.axes.set_xlabel(xlabel)
        self.axes.set_ylabel(ylabel)
        self.axes.set_title(title)

class MyTableWidget(QtGui.QTableWidget):
    def __init__(self, rows, columns, parent=None):
        super(MyTableWidget, self).__init__(rows, columns, parent)
        self.setSortingEnabled(True)

    def keyPressEvent(self, event):
        if event.matches(QtGui.QKeySequence.Copy):
            self.copy()
        else:
            QtGui.QTableWidget.keyPressEvent(self, event)

    def copy(self):
        text = []
        selectionRanges = self.selectedRanges()
        for selRange in selectionRanges:
            rows = []
            for row in range(selRange.topRow(),
                             selRange.topRow() + selRange.rowCount()):
                columns = []
                for col in range(selRange.leftColumn(),
                                 selRange.leftColumn() +
                                         selRange.columnCount()):
                    columns.append(self.item(row,col).text())
                columns = '\t'.join(columns)
                rows.append(columns)
            text.append('\n'.join(rows))
        text = '\n'.join(text)
        QtGui.QApplication.clipboard().setText(text)

class MyTableItem(QtGui.QTableWidgetItem):
    def __init__(self, text=''):
        super(MyTableItem, self).__init__(text)
        self.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
        self.setTextAlignment(QtCore.Qt.AlignCenter)
        self.setFont(QtGui.QFont('Ubuntu Mono'))

class TSig(QtCore.QObject):
    test = QtCore.Signal(str)
    def __init__(self):
        QtCore.QObject.__init__(self)



class DBusWidget(dbus.service.Object):
    # class InnerDbus(dbus.service.Sequence)
    class DBusInterlayer(QtCore.QObject):
        plotReceived = QtCore.Signal(str)

        def __init__(self):
            QtCore.QObject.__init__(self)

    def __init__(self, bus):
        busName = dbus.service.BusName('com.meltviewer.Graph', bus = bus)
        dbus.service.Object.__init__(self, busName, '/Graph')
        self.interlayer = self.DBusInterlayer()

    @dbus.service.method('com.meltviewer.Graph', in_signature='s', out_signature='')
    def sendPlot(self, value):
        self.interlayer.plotReceived.emit(value)

    # plotReceived = QtCore.Signal(str)

# class Meltviewer(QtGui.QWidget):
class Meltviewer(QtGui.QWidget):
    def __init__(self, bus):
        super(Meltviewer, self).__init__()
        # self.plots = ()
        self.melting_plots = []
        self.initDbus(bus)
        self.init_ui()

    def init_ui(self):
        grid = QtGui.QGridLayout()

        self.data_plot = MatplotlibWidget(xlabel='t, ℃', ylabel='C, M')
        grid.addWidget(self.data_plot)

        self.data_table = MyTableWidget(0, len(COLUMNS))
        self.data_table.setSortingEnabled(True)
        self.data_table.setColumnWidth(COLUMNS.Show.value, 50)
        self.data_table.setColumnWidth(COLUMNS.Color.value, 50)
        self.data_table.setColumnWidth(COLUMNS.Marker.value, 80)
        self.data_table.setColumnWidth(COLUMNS.Sequence.value, 300)
        self.data_table.setHorizontalHeaderLabels(
            [name for name, member in COLUMNS.__members__.items()])
        self.data_table.itemClicked.connect(self.item_clicked)
        self.data_table.setColumnHidden(COLUMNS.ID.value, True)
        # self.data_table.setSortingEnabled(True)
        grid.addWidget(self.data_table)

        self.setLayout(grid)
        self.setGeometry(300, 300, 1000, 600)
        self.show()

    def initDbus(self, bus):
        dbusw = DBusWidget(bus)
        dbusw.interlayer.plotReceived.connect(self.on_dbusPlot_received)

    @QtCore.Slot(str)
    def on_dbusPlot_received(self, text):
        text_yaml = yaml.load(text)
        for plot_yaml in text_yaml['plots']:
            if plot_yaml['action'] == 'add_graph':
                # color = plot_yaml['color'] \
                #     if plot_yaml['color'] != 'rnd' \
                #     else COLORS[randrange(len(COLORS) - 1)]
                # marker = plot_yaml['marker'] \
                #     if plot_yaml['marker'] != 'rnd' \
                #     else MARKERS[randrange(len(MARKERS) - 1)]
                self.melting_plots.append(
                    MeltingPlot(plot_yaml)
                )
                # self.add_plot(plot_yaml['mpoints'], color, marker)
                self.add_row(
                    self.melting_plots[len(self.melting_plots) - 1])
        self.redraw_plots()

    def add_plot(self, dots, color, marker):
        dots += (color + marker + '-',)

        self.plots += dots
        self.data_plot.axes.clear()
        self.data_plot.axes.plot(*self.plots)
        self.data_plot.draw()
        self.show()

    def redraw_plots(self):
        self.data_plot.axes.clear()
        for mplot in self.melting_plots:
            if not mplot.show: continue
            self.data_plot.axes.plot(mplot.mpoints[0],mplot.mpoints[1],
                     mplot.color + mplot.marker + '-')
        self.data_plot.draw()
        self.show()

    def add_row(self, mplot):
        self.data_table.setSortingEnabled(False)
        last_row = self.data_table.rowCount()
        self.data_table.insertRow(last_row)
        self.data_table.setItem(last_row, COLUMNS.ID.value,
                                MyTableItem(str(last_row)))
        self.data_table.setItem(last_row, COLUMNS.Sequence.value,
                                MyTableItem(mplot.sequence))
        self.data_table.setItem(last_row, COLUMNS.Length.value,
                                MyTableItem(mplot.length))
        self.data_table.setItem(last_row, COLUMNS.GC.value,
                                MyTableItem(mplot.gc))
        self.data_table.setItem(last_row, COLUMNS.t10.value,
                                MyTableItem(mplot.t10))
        self.data_table.setItem(last_row, COLUMNS.t90.value,
                                MyTableItem(mplot.t90))

        chk_box_item = MyTableItem()
        chk_box_item.setFlags(QtCore.Qt.ItemIsUserCheckable
                              | QtCore.Qt.ItemIsEnabled)
        chk_box_item.setCheckState(QtCore.Qt.Checked)
        self.data_table.setItem(last_row, COLUMNS.Show.value,
                                chk_box_item)

        color_select_item = QtGui.QComboBox()
        color_select_item.addItems(COLORS)
        color_select_item.currentIndexChanged.connect(
            lambda: self.color_changed(last_row,
                                       color_select_item.currentText()))
        color_select_item.setCurrentIndex(COLORS.index(mplot.color))
        self.data_table.setCellWidget(last_row, COLUMNS.Color.value,
                                color_select_item)

        marker_select_item = QtGui.QComboBox()
        marker_select_item.addItems(MARKERS)
        marker_select_item.currentIndexChanged.connect(
            lambda: self.marker_changed(last_row,
                                       marker_select_item.currentText()))
        marker_select_item.setCurrentIndex(MARKERS.index(mplot.marker))
        self.data_table.setCellWidget(last_row, COLUMNS.Marker.value,
                                marker_select_item)
        self.data_table.setSortingEnabled(True)

    def item_clicked(self, cell):
        if cell.column() == COLUMNS.Show.value:
            state = cell.checkState()
            id = int(self.data_table.item(cell.row(),
                                          COLUMNS.ID.value).text())
            self.melting_plots[id].show = state

            self.redraw_plots()

    def color_changed(self, id, color):
        self.melting_plots[id].color = color
        self.redraw_plots()

    def marker_changed(self, id, marker):
        self.melting_plots[id].marker = marker
        self.redraw_plots()


def main():
    dbus_loop = dbus.mainloop.glib.DBusGMainLoop()

    bus = dbus.SessionBus(private = True, mainloop=dbus_loop)
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    app = QtGui.QApplication(sys.argv)
    mv = Meltviewer(bus)
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
import sys
from enum import Enum

from PySide import QtCore
from PySide import QtGui
from PySide import QtNetwork

from pyfold import MTask
from pyfold import MeltingConditions

PORT          = 49200
UNAFOLD_PATH = ''
RAM_DISK = '/home/kablag/.ramdisk/'

SLIDER_RATE = 10

A_CONC = 2e-7
C_10 = A_CONC * 0.1
C_90 = A_CONC * 0.9

M_CONDS = MeltingConditions(UNAFOLD_PATH, RAM_DISK, '30', '90',
                            '1', A_CONC, '5e-2', '3e-3')

class COLUMNS(Enum):
    ID = 0
    Sequence = 1
    T10 = 2
    T90 = 3
    Dt10 = 4
    Dt90 = 5
    Dt90t10 = 6
    Length = 7
    Position = 8


class TempSelectWidget(QtGui.QWidget):
    def __init__(self, text, tickPosition):
        super(TempSelectWidget, self).__init__()

        self.label = QtGui.QLabel(text)

        self.slider = QtGui.QSlider()
        self.slider.setOrientation(QtCore.Qt.Horizontal)
        self.slider.setTickInterval(1)
        self.slider.setMinimum(0)
        self.slider.setMaximum(1000)
        self.slider.setValue(tickPosition * SLIDER_RATE)
        self.slider.valueChanged.connect(self.onValueChanged)

        self.value = QtGui.QLineEdit()
        self.onValueChanged()
        self.value.textChanged.connect(self.onValueEditChange)

        self.__sliderValue

        hBox = QtGui.QHBoxLayout()
        hBox.addWidget(self.label)
        hBox.addWidget(self.slider)
        hBox.addWidget(self.value)

        # sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)
        # self.setSizePolicy(sizePolicy)
        self.setLayout(hBox)

    def onValueChanged(self):
        self.__sliderValue = self.slider.value()/SLIDER_RATE
        self.value.setText(str(self.__sliderValue))

    def onValueEditChange(self):
        self.__sliderValue = float(self.value.text())
        self.slider.setValue(int(self.__sliderValue*SLIDER_RATE))

    def sliderValue(self):
        return self.__sliderValue


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


class FilterTab(QtGui.QWidget):
    class Row():
        def __init__(self,
                     id,
                     sequence,
                     t10, t90,
                     dt10, dt90,
                     dt90t10,
                     length,
                     position):
            self.id = str(id)
            self.sequence = sequence
            self.t10 = str(t10)
            self.t90 = str(t90)
            self.dt10 = str(dt10)
            self.dt90 = str(dt90)
            self.dt90t10 = str(dt90t10)
            self.length = str(length)
            self.position = str(position)

    def __init__(self, name):
        super(FilterTab, self).__init__()
        self.rows = []
        self.name = name
        tab_layout = QtGui.QVBoxLayout()
        # tab_layout.setSpacing(-10)
        self.t10Min = TempSelectWidget('t10 min', 0)
        self.t10Min.slider.valueChanged.connect(self.filterRows)
        self.t10Max = TempSelectWidget('t10 max', 75)
        self.t10Max.slider.valueChanged.connect(self.filterRows)
        self.t90Min = TempSelectWidget('t90 min', 50)
        self.t90Min.slider.valueChanged.connect(self.filterRows)
        self.t90Max = TempSelectWidget('t90 max', 90)
        self.t90Max.slider.valueChanged.connect(self.filterRows)
        self.minDelta_t10 = TempSelectWidget('min dt10',0)
        self.minDelta_t10.slider.valueChanged.connect(self.filterRows)
        self.minDelta_t90 = TempSelectWidget('min dt90',0)
        self.minDelta_t90.slider.valueChanged.connect(self.filterRows)
        self.minDelta_t10t90 = TempSelectWidget('min dt90t10',0)
        self.minDelta_t10t90.slider.setMinimum(-20 * SLIDER_RATE)
        self.minDelta_t10t90.slider.setMaximum(10 * SLIDER_RATE)
        self.minDelta_t10t90.slider.setValue(-10 * SLIDER_RATE)
        self.minDelta_t10t90.slider.valueChanged.connect(self.filterRows)

        self.dataTable = MyTableWidget(0, len(COLUMNS))
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        self.dataTable.setSizePolicy(sizePolicy)
        self.dataTable.setHorizontalHeaderLabels(
            [name for name, member in COLUMNS.__members__.items()])
        self.dataTable.setHidden(COLUMNS.ID.value)
        self.dataTable.resizeColumnsToContents()
        tab_layout.addWidget(self.t10Min)
        tab_layout.addWidget(self.t10Max)
        tab_layout.addWidget(self.t90Min)
        tab_layout.addWidget(self.t90Max)
        tab_layout.addWidget(self.minDelta_t10)
        tab_layout.addWidget(self.minDelta_t90)
        tab_layout.addWidget(self.minDelta_t10t90)
        tab_layout.addWidget(self.dataTable)
        self.setLayout(tab_layout)

    def filterRows(self):
        for i in range(0, self.dataTable.rowCount()):

            if float(self.dataTable.item(i,
                COLUMNS.T10.value).text()) \
                    >= self.t10Min.sliderValue()  and \
                float(self.dataTable.item(i,
                COLUMNS.T10.value).text()) \
                    <= self.t10Max.sliderValue() and \
                float(self.dataTable.item(i,
                COLUMNS.T90.value).text()) \
                    >= self.t90Min.sliderValue() and \
                float(self.dataTable.item(i,
                COLUMNS.T90.value).text()) \
                    <= self.t90Max.sliderValue() and \
                    (float(self.dataTable.item(i,
                COLUMNS.Dt10.value).text()) \
                    >= self.minDelta_t10.sliderValue() or \
                    float(self.dataTable.item(i, COLUMNS.Dt10.value).text()) == 0) and \
                (float(self.dataTable.item(i,
                COLUMNS.Dt90.value).text()) \
                    >= self.minDelta_t90.sliderValue() or \
                    float(self.dataTable.item(i, COLUMNS.Dt90.value).text()) == 0) and \
                (float(self.dataTable.item(i,
                COLUMNS.Dt90t10.value).text()) \
                    >= self.minDelta_t10t90.sliderValue() or \
                    float(self.dataTable.item(i, COLUMNS.Dt90t10.value).text()) == 0):
                self.dataTable.showRow(i)
            else:
                self.dataTable.hideRow(i)
        self.dataTable.resizeColumnsToContents()



    def addData(self, mtask:MTask):
        melts_to_show = mtask.melting_pots
        def add_row(melt_show_mpot, id):
            pos = melt_show_mpot.position
            if self.name == 'A':
                sequence = melt_show_mpot.a
                t10 = melt_show_mpot.t10_AB
                t90 = melt_show_mpot.t90_AB
                try:
                    dt10 = melt_show_mpot.t10_AB - melt_show_mpot.t10_ABm
                except TypeError:
                    dt10 = 0
                try:
                    dt90 = melt_show_mpot.t90_AB - melt_show_mpot.t90_ABm
                except TypeError:
                    dt90 = 0
                try:
                    dt90t10 = melt_show_mpot.t90_AB - melt_show_mpot.t10_ABm
                except TypeError:
                    dt90t10 = 0
            elif self.name == 'B':
                sequence = melt_show_mpot.b
                t10 = melt_show_mpot.t10_AB
                t90 = melt_show_mpot.t90_AB
                try:
                    dt10 = melt_show_mpot.t10_AB - melt_show_mpot.t10_AmB
                except TypeError:
                    dt10 = 0
                try:
                    dt90 = melt_show_mpot.t90_AB - melt_show_mpot.t90_AmB
                except TypeError:
                    dt90 = 0
                try:
                    dt90t10 = melt_show_mpot.t90_AB - melt_show_mpot.t10_AmB
                except TypeError:
                    dt90t10 = 0
            elif self.name == 'Am':
                sequence = melt_show_mpot.am
                t10 = melt_show_mpot.t10_AmBm
                t90 = melt_show_mpot.t90_AmBm
                try:
                    dt10 = melt_show_mpot.t10_AmBm - melt_show_mpot.t10_AmB
                except TypeError:
                    dt10 = 0
                try:
                    dt90 = melt_show_mpot.t90_AmBm - melt_show_mpot.t90_AmB
                except TypeError:
                    dt90 = 0
                try:
                    dt90t10 = melt_show_mpot.t90_AmBm - melt_show_mpot.t10_AmB
                except TypeError:
                    dt90t10 = 0
            else:
                sequence = melt_show_mpot.bm
                t10 = melt_show_mpot.t10_AmBm
                t90 = melt_show_mpot.t90_AmBm
                try:
                    dt10 = melt_show_mpot.t10_AmBm - melt_show_mpot.t10_ABm
                except TypeError:
                    dt10 = 0
                try:
                    dt90 = melt_show_mpot.t90_AmBm - melt_show_mpot.t90_ABm
                except TypeError:
                    dt90 = 0
                try:
                    dt90t10 = melt_show_mpot.t90_AmBm - melt_show_mpot.t10_ABm
                except TypeError:
                    dt90t10 = 0
            try:
                dt10 = round(dt10, 1)
            except TypeError:
                dt10 = 0
            try:
                dt90 = round(dt90, 1)
            except TypeError:
                dt90 = 0
            try:
                dt90t10 = round(dt90t10, 1)
            except TypeError:
                dt90t10 = 0
            return FilterTab.Row(id, sequence,
                                     t10, t90,
                                     dt10, dt90,
                                     dt90t10,
                                     melt_show_mpot.length_of_a,
                                     pos)
        id = 0
        self.rows = []
        for mp in melts_to_show:
            self.rows.append(add_row(mp, id))
            id+=1
        self.showDataInTable()
        self.filterRows()

    def showDataInTable(self):
        self.dataTable.setSortingEnabled(False)
        # self.dataTable.clearContents()
        self.dataTable.clear()
        for d_row in self.rows:
            self.dataTable.insertRow(0)
            self.dataTable.setItem(0, COLUMNS.ID.value,
                                   MyTableItem(d_row.id))
            self.dataTable.setItem(0, COLUMNS.Sequence.value,
                                   MyTableItem(d_row.sequence))
            self.dataTable.setItem(0, COLUMNS.T10.value,
                                   MyTableItem(d_row.t10))
            self.dataTable.setItem(0, COLUMNS.T90.value,
                                   MyTableItem(d_row.t90))
            self.dataTable.setItem(0, COLUMNS.Dt10.value,
                                   MyTableItem(d_row.dt10))
            self.dataTable.setItem(0, COLUMNS.Dt90.value,
                                   MyTableItem(d_row.dt90))
            self.dataTable.setItem(0, COLUMNS.Dt90t10.value,
                                   MyTableItem(d_row.dt90t10))
            self.dataTable.setItem(0, COLUMNS.Length.value,
                                   MyTableItem(d_row.length))
            self.dataTable.setItem(0, COLUMNS.Position.value,
                                   MyTableItem(d_row.position))
        self.dataTable.setHorizontalHeaderLabels(
            [name for name, member in COLUMNS.__members__.items()])
        self.dataTable.setSortingEnabled(True)

class Snpick(QtGui.QWidget):
    def __init__(self):
        super(Snpick, self).__init__()
        self.mtask = None
        self.init_ui()

    def init_ui(self):
        self.seqInput = QtGui.QLineEdit()
        self.seqInput.setText('tcccctccaggccgtgcataaggctgtgctgaccatcgac(A>G)agaaagggactgaagctgctggggccatgtttttagaggc')

        self.probeMin = QtGui.QLineEdit()
        self.probeMin.setText('15')

        self.probeMax = QtGui.QLineEdit()
        self.probeMax.setText('17')

        self.calcProbes = QtGui.QPushButton(text='Calc')
        self.calcProbes.clicked.connect(self.onCalcProbesPressed)

        self.saveBtn = QtGui.QPushButton(text='Save')
        self.loadBtn = QtGui.QPushButton(text='Load')
        self.batchCalcBtn = QtGui.QPushButton(text='Batch Calc')

        self.tabs = QtGui.QTabWidget()
        self.tab_A = FilterTab('A')
        self.tab_B = FilterTab('B')
        self.tab_Am = FilterTab('Am')
        self.tab_Bm = FilterTab('Bm')

        self.tabs.addTab(self.tab_A, 'A')
        self.tabs.addTab(self.tab_B, 'B')
        self.tabs.addTab(self.tab_Am, 'Am')
        self.tabs.addTab(self.tab_Bm, 'Bm')

        vbox = QtGui.QVBoxLayout()
        vbox.addWidget(self.seqInput)
        # vbox.addStretch(1)
        hbox = QtGui.QHBoxLayout()
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Minimum)
        self.probeMin.setSizePolicy(sizePolicy)
        hbox.addWidget(self.probeMin)
        self.probeMax.setSizePolicy(sizePolicy)
        hbox.addWidget(self.probeMax)
        self.calcProbes.setSizePolicy(sizePolicy)
        hbox.addWidget(self.calcProbes)
        hbox.addStretch(1)
        rangeInputs = QtGui.QWidget()
        rangeInputs.setLayout(hbox)
        vbox.addWidget(rangeInputs)
        vbox.addWidget(self.tabs)

        self.setLayout(vbox)
        self.setGeometry(300, 300, 1000, 600)
        self.show()

    def resizeEvent(self, event):
        self.tabs.setBaseSize(self.tabs.width(),
                              event.size().height() * 0.8)

    def onCalcProbesPressed(self):
        mtask = '{sequence}{min_p}->{max_p}'.format(
            sequence=self.seqInput.text(),
            min_p=self.probeMin.text(),
            max_p=self.probeMax.text(),
        )
        self.mtask = MTask(mtask)
        self.seqInput.setText(self.mtask.task)
        self.mtask.meltingPotDone.connect(self.on_mpot_done)
        self.pd = QtGui.QProgressDialog('Melting probes',
                                        'Cancel',
                                        0,
                                        len(self.mtask.melting_pots))
        self.pd.setWindowModality(QtCore.Qt.WindowModal)
        self.calcProbes.setEnabled(False)
        self.pd.canceled.connect(self.cancel_melting)
        self.mtask.execute(M_CONDS)
        self.calcProbes.setEnabled(True)
        if not self.mtask.canceled:
            self.tab_A.addData(self.mtask)
            self.tab_B.addData(self.mtask)
            self.tab_Am.addData(self.mtask)
            self.tab_Bm.addData(self.mtask)

    @QtCore.Slot()
    def cancel_melting(self):
        self.pd.close()
        self.mtask.cancel()


    @QtCore.Slot(int)
    def on_mpot_done(self, value):
        self.pd.setValue(value)

def main():
    app = QtGui.QApplication(sys.argv)
    sp = Snpick()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
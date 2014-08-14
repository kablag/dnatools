__author__ = 'kablag'

import re
from enum import Enum
import uuid
import os
import time
import shutil
import subprocess
import concurrent.futures

from PySide import QtCore

from dnatools import reverse_complement
from dnatools import calcGC
SIMPLE_TASK_PATTERN = r'[atgc]*$'
BEFORE_PATTERN = r'(?P<before>[atgc]*)'
AFTER_PATTERN = r'(?P<after>[atgc]*$)'
SNP_TASK_PATTERN = BEFORE_PATTERN + \
                   r'\((?P<wt>[atgc]*)\>(?P<mut>[atgc]*)\)' + \
                   AFTER_PATTERN
SNP_TASK_WITH_SHIFT_PATTERN = SNP_TASK_PATTERN[:-2] + r')(?P<min>\d+)-\>(?P<max>\d*)$'

MISMATCH_TASK_PATTERN = BEFORE_PATTERN + \
                        r'\((?P<a>[atgc]*)\/(?P<b>[atgc]*)\)' + \
                        AFTER_PATTERN
RANGE_TASK_PATTERN = BEFORE_PATTERN + \
                     r'\[(?P<range>[atgc]*)\]' + \
                     AFTER_PATTERN

class MTaskParsingError(Exception):
    pass

class MeltingPot(QtCore.QObject):
    def __init__(self, a, b, name=''):
        QtCore.QObject.__init__(self)
        self.__name = name
        self.__a, self.__b, = a, b
        self.__length_of_a = len(self.__a)
        self.__gc_of_a = calcGC(self.__a)
        self.__mpoints = []
        self.__conditions = None
        self.__t10 = None
        self.__t90 = None

    meltDone = QtCore.Signal()

    @property
    def name(self):
        return self.__name

    @property
    def a(self):
        return self.__a

    @property
    def b(self):
        return self.__b

    @property
    def length_of_a(self):
        return self.__length_of_a

    @property
    def gc_of_a(self):
        return self.__gc_of_a

    @property
    def conditions(self):
        return self.__conditions

    @property
    def t10(self):
        return self.__t10

    @property
    def t90(self):
        return self.__t90

    @property
    def mpoints(self):
        return self.__mpoints

    @property
    def mpoints_as_XY(self):
        return mpoints_to_x_y_coords(self.__mpoints)

    def melt(self, conditions):
        self.__conditions = conditions
        c10 = self.__conditions.a_conc * 0.1
        c90 = self.__conditions.a_conc * 0.9
        self.__mpoints = melt(self.__a,
                            self.__b,
                            self.__conditions)
        ts = calc_t_at_conc([c10, c90], self.__mpoints)
        self.__t10 = ts[c10]
        self.__t90 = ts[c90]

    def __str__(self):
        return '{a}\n{b}'.format(a=self.a, b=self.b)
    def __repr__(self):
        return '{a}\n{b}'.format(a=self.a, b=self.b)

class MeltingPotSNP(MeltingPot):
    def __init__(self, a, b, am, bm, position):
        # super(MeltingPotSNP, self).__init__(a, b)
        MeltingPot.__init__(self, a, b)
        self.__am = am
        self.__bm = bm
        self.__position = position
        self.__mpointsAB = []
        self.__mpointsABm = []
        self.__mpointsAmBm = []
        self.__mpointsAmB = []
        self.__t10_AB = None
        self.__t10_ABm = None
        self.__t10_AmBm = None
        self.__t10_AmB = None
        self.__t90_AB = None
        self.__t90_ABm = None
        self.__t90_AmBm = None
        self.__t90_AmB = None

    @property
    def am(self):
        return self.__am

    @property
    def bm(self):
        return self.__bm

    @property
    def position(self):
        return self.__position

    @property
    def t10_AB(self):
        return self.__t10_AB

    @property
    def t90_AB(self):
        return self.__t90_AB

    @property
    def t10_ABm(self):
        return self.__t10_ABm

    @property
    def t90_ABm(self):
        return self.__t90_ABm

    @property
    def t10_AmBm(self):
        return self.__t10_AmBm

    @property
    def t90_AmBm(self):
        return self.__t90_AmBm

    @property
    def t10_AmB(self):
        return self.__t10_AmB

    @property
    def t90_AmB(self):
        return self.__t90_AmB

    def calc_t_at_c_points(self):
        c10 = self.__conditions.a_conc * 0.1
        c90 = self.__conditions.a_conc * 0.9
        ts_a_b = calc_t_at_conc([c10, c90], self.__mpointsAB)
        try:
            self.__t10_AB = round(ts_a_b[c10], 1)
        except TypeError:
            pass
        try:
            self.__t90_AB = round(ts_a_b[c90], 1)
        except TypeError:
            pass
        ts_a_bm = calc_t_at_conc([c10, c90], self.__mpointsABm)
        try:
            self.__t10_ABm = round(ts_a_bm[c10], 1)
        except TypeError:
            pass
        try:
            self.__t90_ABm = round(ts_a_bm[c90], 1)
        except TypeError:
            pass
        ts_am_bm = calc_t_at_conc([c10, c90], self.__mpointsAmBm)
        try:
            self.__t10_AmBm = round(ts_am_bm[c10], 1)
        except TypeError:
            pass
        try:
            self.__t90_AmBm = round(ts_am_bm[c90], 1)
        except TypeError:
            pass
        ts_am_b = calc_t_at_conc([c10, c90], self.__mpointsAmB)
        try:
            self.__t10_AmB = round(ts_am_b[c10], 1)
        except TypeError:
            pass
        try:
            self.__t90_AmB = round(ts_am_b[c90], 1)
        except TypeError:
            pass

    def melt(self, conditions):
        self.__conditions = conditions
        self.__mpointsAB, self.__mpointsABm,\
            self.__mpointsAmBm, self.__mpointsAmB =\
            melt_snp(self.a,
                            self.b,
                            self.__am,
                            self.__bm,
                            self.__conditions)
        self.calc_t_at_c_points()
        self.meltDone.emit()

    def __str__(self):
        return '{a}\n{b}\n{am}\n{bm}'.format(a=self.a, b=self.b,
                                 am=self.am, bm=self.bm)
    def __repr__(self):
        return 'A : {a}\nB : {b}\nAm: {am}\nBm: {bm}'.format(
            a=self.a, b=self.b,
                                 am=self.am, bm=self.bm)
class TaskType(Enum):
        simple = 0
        snp = 1
        snp_shift = 2
        mismatch = 3
        cut_range = 4
        error = 5
        
class MTask(QtCore.QObject):
    

    meltingPotDone = QtCore.Signal(int)

    def __init__(self, mtask):
        QtCore.QObject.__init__(self)
        self.__task = None
        self.__melting_pots = []
        self.__task_type = TaskType.error
        self.task = mtask
        self.probeMin = None
        self.probeMax = None
        self.mPotsReady = 0
        self.canceled = False

    @property
    def melting_pots(self):
        return self.__melting_pots

    @property
    def task_type(self):
        return self.__task_type

    @property
    def task(self):
        return self.__task

    @task.setter
    def task(self, task):
        self.__task = task.replace(" ", "")
        self.__task = task.replace("\n", "")
        self.__melting_pots = []
        patterns = {re.compile(SIMPLE_TASK_PATTERN, re.IGNORECASE):
                        TaskType.simple,
                    re.compile(SNP_TASK_PATTERN, re.IGNORECASE):
                        TaskType.snp,
                    re.compile(SNP_TASK_WITH_SHIFT_PATTERN, re.IGNORECASE):
                        TaskType.snp_shift,
                    re.compile(MISMATCH_TASK_PATTERN, re.IGNORECASE):
                        TaskType.mismatch,
                    re.compile(RANGE_TASK_PATTERN, re.IGNORECASE):
                        TaskType.cut_range,
        }
        self.__task_type = TaskType.error
        match_result = None
        for pat in patterns:
            match_result = pat.match(self.__task)
            if match_result:
                self.__task_type = patterns[pat]
                break
        if self.__task_type is TaskType.simple:
            self.__melting_pots = [MeltingPot(self.__task,
                                              reverse_complement(self.__task))]
        elif self.__task_type is TaskType.cut_range:
            before = match_result.group('before')
            variable = match_result.group('range')
            after = match_result.group('after')
            step = 1 if before else -1
            variable_parts = [variable[:i]
                              for i in range(0, len(variable) + 1)] \
                if before else \
                reversed([variable[i:]
                          for i in range(0, len(variable) + 1)])

            self.__melting_pots = [MeltingPot(
                ''.join([before, variable, after]),
                reverse_complement(''.join([before, variable, after]))
            )
                                   for variable in variable_parts]
        elif self.__task_type is TaskType.mismatch:
            before = match_result.group('before')
            a = match_result.group('a')
            b = match_result.group('b')
            after = match_result.group('after')
            self.__melting_pots = [
                MeltingPot(''.join([before, a, after]),
                           reverse_complement(''.join(
                               [before, b, after])))
            ]
        elif self.__task_type is TaskType.snp:
            before = match_result.group('before')
            wt = match_result.group('wt')
            mut = match_result.group('mut')
            after = match_result.group('after')
            self.__melting_pots = [
                MeltingPot(''.join([before, wt, after]),
                           reverse_complement(''.join(
                               [before, wt, after]))),
                MeltingPot(''.join([before, wt, after]),
                           reverse_complement(''.join(
                               [before, mut, after]))),
                MeltingPot(''.join([before, mut, after]),
                           reverse_complement(''.join(
                               [before, mut, after]))),
                MeltingPot(''.join([before, mut, after]),
                           reverse_complement(''.join(
                               [before, wt, after]))),
            ]
        elif self.__task_type is TaskType.snp_shift:
            before = match_result.group('before').lower()
            before_len = len(before)
            wt = match_result.group('wt').upper()
            wt_len = len(wt)
            mut = match_result.group('mut').upper()
            mut_len = len(mut)
            after = match_result.group('after').lower()
            self.probeMin = int(match_result.group('min'))
            self.probeMax = int(match_result.group('max'))
            self.__task = '{bef}({wt}>{mut}){aft}'.format(bef=before,
                                                                        wt=wt,
                                                                        mut=mut,
                                                                        aft=after,)
            self.__melting_pots = []

            for pr_len in range(self.probeMin, self.probeMax + 1):
                for shift in range(0, pr_len):
                    def new_pot(x, x_len, y, y_len):
                        mpotsnp = MeltingPotSNP(
                        a=''.join([before[before_len - shift:],
                                x,
                                after[:pr_len - shift - x_len]]),
                        am=''.join([before[before_len - shift:],
                                y,
                                after[:pr_len - shift - x_len]]),
                        b=reverse_complement(''.join(
                                [before[before_len - shift:],
                                x,
                                after[:pr_len - shift - y_len]])),
                        bm=reverse_complement(''.join(
                                [before[before_len - shift:],
                                y,
                                after[:pr_len - shift - y_len]])),
                        position=str(shift))
                        mpotsnp.meltDone.connect(self.on_melt_ready)
                        return mpotsnp
                    self.melting_pots.append(
                        new_pot(wt, wt_len, mut, mut_len)
                    )
        elif self.__task_type is TaskType.error:
            raise MTaskParsingError
        else:
            raise MTaskParsingError

    def execute(self, conditions):
        self.mPotsReady = 0
        self.canceled = False
        for mpot in self.__melting_pots:
            if self.canceled:
                break
            mpot.melt(conditions)

    def cancel(self):
        self.canceled = True

    @QtCore.Slot()
    def on_melt_ready(self):
        self.mPotsReady += 1
        # time.sleep(0.2)
        QtCore.QCoreApplication.processEvents()
        self.meltingPotDone.emit(self.mPotsReady)

class MPoint():
    def __init__(self, t, conc):
        self.t = t
        self.conc = conc

    def __repr__(self):
        return 't = {t}\tC = {c}'.format(t=self.t, c=self.conc)


def mpoints_to_x_y_coords(mpoints):
    x = []
    y = []
    for mpoint in mpoints:
        x.append(mpoint.t)
        y.append(mpoint.conc)
    return (x, y)


def exec_unafold_commands(commands, working_dir):
    # startupinfo = subprocess.STARTUPINFO()
    # startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    # startupinfo.wShowWindow = subprocess.SW_HIDE

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        executor.map(lambda command:
                     subprocess.call(command,
                                     cwd=working_dir,
                                     stdout=open(os.devnull, "w"),
                                     stderr=subprocess.STDOUT,
                     ),
                     commands)


def melt(seq_a, seq_b, conditions):
    id = uuid.uuid1().hex
    path = conditions.ram_disk + id + '/'
    os.mkdir(path)
    with open('{path}a'.format(path=path), 'w') as f:
        print(seq_a, file=f)
    with open('{path}b'.format(path=path), 'w') as f:
        print(seq_b, file=f)

    commands = [conditions.hybrid_ss_a,
                conditions.hybrid_ss_b,
                conditions.hybrid_a_b,
                conditions.hybrid_a_a,
                conditions.hybrid_b_b,
    ]
    exec_unafold_commands(commands, path)

    commands = [conditions.sbs,
                conditions.concentration_same,
                conditions.concentration]
    exec_unafold_commands(commands, path)

    with open('{path}a-b.conc'.format(path=path), 'r') as f:
        rows = f.readlines()

    def melt_point_from_row(row):
        values = row.split('\t')
        return MPoint(float(values[0]), float(values[len(values) - 1]))

    mpoints = map(melt_point_from_row, rows[1:])
    shutil.rmtree(path)
    return list(mpoints)

def melt_snp(seq_a, seq_b, seq_am, seq_bm, conditions):
    id = uuid.uuid1().hex
    path = conditions.ram_disk + id + '/'
    os.mkdir(path)
    with open('{path}a'.format(path=path), 'w') as f:
        print(seq_a, file=f)
    with open('{path}b'.format(path=path), 'w') as f:
        print(seq_b, file=f)
    with open('{path}am'.format(path=path), 'w') as f:
        print(seq_am, file=f)
    with open('{path}bm'.format(path=path), 'w') as f:
        print(seq_bm, file=f)

    commands = [conditions.hybrid_ss_a,
                conditions.hybrid_ss_b,
                conditions.hybrid_ss_am,
                conditions.hybrid_ss_bm,
                conditions.hybrid_a_b,
                conditions.hybrid_a_a,
                conditions.hybrid_b_b,
                conditions.hybrid_am_am,
                conditions.hybrid_bm_bm,
                conditions.hybrid_am_bm,
                conditions.hybrid_am_b,
                conditions.hybrid_a_bm,
    ]
    exec_unafold_commands(commands, path)

    commands = [conditions.sbs_a,
                conditions.concentration_a_b,
                conditions.concentration_a_bm,
                ]
    exec_unafold_commands(commands, path)
    commands = [conditions.sbs_am,
                conditions.concentration_am_bm,
                conditions.concentration_am_b,
                ]
    exec_unafold_commands(commands, path)


    with open('{path}a-b.conc'.format(path=path), 'r') as f:
        rows_a_b = f.readlines()
    with open('{path}a-bm.conc'.format(path=path), 'r') as f:
        rows_a_bm = f.readlines()
    with open('{path}am-bm.conc'.format(path=path), 'r') as f:
        rows_am_bm = f.readlines()
    with open('{path}am-b.conc'.format(path=path), 'r') as f:
        rows_am_b = f.readlines()

    def melt_point_from_row(row):
        values = row.split('\t')
        return MPoint(float(values[0]), float(values[len(values) - 1]))

    mpoints_a_b = map(melt_point_from_row, rows_a_b[1:])
    mpoints_a_bm = map(melt_point_from_row, rows_a_bm[1:])
    mpoints_am_bm = map(melt_point_from_row, rows_am_bm[1:])
    mpoints_am_b = map(melt_point_from_row, rows_am_b[1:])
    shutil.rmtree(path)
    return (list(mpoints_a_b),
            list(mpoints_a_bm),
            list(mpoints_am_bm),
            list(mpoints_am_b),)



class MeltingConditions():
    def __init__(self, unafold_path, ram_disk, t_min=30, t_max=90,
                 t_increment=1, a_conc=2e-7, Na_conc='5e-2', Mg_conc='3e-3'):
        self.a_conc = a_conc
        self.unafold_path = unafold_path
        self.ram_disk = ram_disk
        self.hybrid_ss_a = [self.unafold_path + 'hybrid-ss',
                            '-n', 'DNA', '-t', t_min,
                            '-i', t_increment, '-T', t_max,
                            '-N', Na_conc, '-M', Mg_conc, 'a']
        self.hybrid_ss_b = [self.unafold_path + 'hybrid-ss',
                            '-n', 'DNA', '-t', t_min,
                            '-i', t_increment, '-T', t_max,
                            '-N', Na_conc, '-M', Mg_conc, 'b']
        self.hybrid_ss_am = [self.unafold_path + 'hybrid-ss',
                            '-n', 'DNA', '-t', t_min,
                            '-i', t_increment, '-T', t_max,
                            '-N', Na_conc, '-M', Mg_conc, 'am']
        self.hybrid_ss_bm = [self.unafold_path + 'hybrid-ss',
                            '-n', 'DNA', '-t', t_min,
                            '-i', t_increment, '-T', t_max,
                            '-N', Na_conc, '-M', Mg_conc, 'bm']
        self.hybrid_a_b = [self.unafold_path + 'hybrid',
                           '-n', 'DNA', '-t', t_min,
                           '-i', t_increment, '-T', t_max,
                           '-N', Na_conc, '-M', Mg_conc, 'a', 'b']
        self.hybrid_a_a = [self.unafold_path + 'hybrid',
                           '-n', 'DNA', '-t', t_min,
                           '-i', t_increment, '-T', t_max,
                           '-N', Na_conc, '-M', Mg_conc, 'a', 'a']
        self.hybrid_b_b = [self.unafold_path + 'hybrid',
                           '-n', 'DNA', '-t', t_min,
                           '-i', t_increment, '-T', t_max,
                           '-N', Na_conc, '-M', Mg_conc, 'b', 'b']

        self.hybrid_am_am = [self.unafold_path + 'hybrid',
                           '-n', 'DNA', '-t', t_min,
                           '-i', t_increment, '-T', t_max,
                           '-N', Na_conc, '-M', Mg_conc, 'am', 'am']
        self.hybrid_bm_bm = [self.unafold_path + 'hybrid',
                           '-n', 'DNA', '-t', t_min,
                           '-i', t_increment, '-T', t_max,
                           '-N', Na_conc, '-M', Mg_conc, 'bm', 'bm']
        self.hybrid_am_bm = [self.unafold_path + 'hybrid',
                           '-n', 'DNA', '-t', t_min,
                           '-i', t_increment, '-T', t_max,
                           '-N', Na_conc, '-M', Mg_conc, 'am', 'bm']
        self.hybrid_am_b = [self.unafold_path + 'hybrid',
                           '-n', 'DNA', '-t', t_min,
                           '-i', t_increment, '-T', t_max,
                           '-N', Na_conc, '-M', Mg_conc, 'am', 'b']
        self.hybrid_a_bm = [self.unafold_path + 'hybrid',
                           '-n', 'DNA', '-t', t_min,
                           '-i', t_increment, '-T', t_max,
                           '-N', Na_conc, '-M', Mg_conc, 'a', 'bm']
        self.sbs = [self.unafold_path + 'sbs',
                    '-n', 'DNA', 'a']
        self.sbs_a = [self.unafold_path + 'sbs',
                    '-n', 'DNA', 'a']
        self.concentration_same = [self.unafold_path + 'concentration-same',
                                   '-A', str(a_conc),
                                   '-H', '-1.1e1', '-S', '-3.4e1', 'a']
        self.concentration = [self.unafold_path + 'concentration',
                              '-A', str(a_conc), '-B', str(a_conc),
                              '-H', '-1.1e1', '-S', '-3.4e1', 'a', 'b']
        self.concentration_a_b = [self.unafold_path + 'concentration',
                              '-A', str(a_conc), '-B', str(a_conc),
                              '-H', '-1.1e1', '-S', '-3.4e1', 'a', 'b']
        self.concentration_a_bm = [self.unafold_path + 'concentration',
                              '-A', str(a_conc), '-B', str(a_conc),
                              '-H', '-1.1e1', '-S', '-3.4e1', 'a', 'bm']

        self.sbs_am = [self.unafold_path + 'sbs',
                    '-n', 'DNA', 'am']
        self.concentration_am_bm = [self.unafold_path + 'concentration',
                              '-A', str(a_conc), '-B', str(a_conc),
                              '-H', '-1.1e1', '-S', '-3.4e1', 'am', 'bm']
        self.concentration_am_b = [self.unafold_path + 'concentration',
                              '-A', str(a_conc), '-B', str(a_conc),
                              '-H', '-1.1e1', '-S', '-3.4e1', 'am', 'b']


def calc_t_at_conc(concs, mpoints):
    sorted_by_conc = sorted(mpoints, key=lambda mpoint: mpoint.conc)

    def check_c_X(c_X, mpoint, next_mpoint):
        if c_X >= mpoint.conc and c_X < next_mpoint.conc:
            return mpoint.t + (next_mpoint.t - mpoint.t) * \
                              ((c_X - mpoint.conc) / (next_mpoint.conc - mpoint.conc))
        else:
            return None

    ts = {conc: None for conc in concs}
    num_t_founded = 0
    for i in range(0, len(sorted_by_conc) - 2):
        for conc in concs:
            t = check_c_X(conc,
                          sorted_by_conc[i],
                          sorted_by_conc[i + 1])
            if t:
                ts[conc] = t
                num_t_founded += 1
                if num_t_founded == len(concs):
                    return ts
    return ts



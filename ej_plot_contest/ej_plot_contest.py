import argparse
import csv
import json
import logging
import sys


"""
Parse dumped runs, get OK statistics: prob_
Run_Id;Time;Nsec;Time2;Date;Year;Mon;Day;Hour;Min;Sec;Dur;Dur_Day;Dur_Hour;Dur_Min;Dur_Sec;Size;IPV6_Flag;IP;SSL_Flag;Sha1;User_Id;User_Login;User_Name;User_Inv;User_Ban;User_Lock;Prob;Variant;Lang;Content_Type;Stat_Short;Status;Score;Score_Adj;Test;Import_Flag;Hidden_Flag;RO_Flag;Locale_Id;Pages;Judge_Id
1593;1576160067;253221000;20191212171427;20191212;2019;12;12;17;14;27;10646;0;02;57;26;1076;0;10.55.131.43;0;49563b565fed363984a340b94ab6fdc354c0c202;10089;ed95080609;Григорьевых Илья Дмитриевич   Б04-905;;;;F-DPQE;0;gcc-vg;;PT;Partial solution;4;0;4;1;0;0;0;1;0;0
"""

class ProblemName:
    """
    Имя задачи в разных случаях:
    _base - основа создания имени Cmem-
    fullname - полное (реальное) имя задачи Cmem-DPQE
    label - как эту задачу называют в заголовках и легенде Cmem
    """
   
    def __init__(self, label, suffix=''):
        self._base = label
        self._label = label.rstrip('-')
        self._fullname = label + suffix
        
    #label = property()
    #fullname = property()
    
    def __repr__(self):
        return self._fullname
        
    @property
    def label(self):
        return self._label

    @property
    def fullname(self):
        return self._fullname

    def update_fullname(self, allow_set):
        """
        Если fullname нет в allow_set, а base или label есть, то заменить на base или label
        :param allow_set: множество строк - реальных названий задач
        """
        if self._fullname in allow_set:
            return

        if self._base in allow_set:
            self._fullname = self._base

        if self._label in allow_set:
            self._fullname = self._label


    @staticmethod
    def read_names(problem_names, department):
        # problem_names = 'C- C-mem- D- F- E- E_mem-'
        return [ProblemName(p, department) for p in problem_names.split()]


class Params:
    """
    Сборник всех параметров, которые задаются по умолчанию, в конфиг файле и в аргументах командной строки
    """
    def __init__(self):
        self.output_dir = '.'       # directory for output csv tables and plots
        self.department = ''
        self.login_prefix = 'ed'
        self.login_group_len = 3
        self._preps = {}            # group from login : prep last name, or build by csv data without prep names
        self._groups = []           # list of groups in preconstructed order
        self.probs = []             # ProblemName list
    
    
    def __repr__(self):
        return str(self.__dict__)
        
    #groups = property()
    #preps = property()

    @property
    def groups(self):
        return self._groups

    @property
    def preps(self):
        return self._preps

    @preps.setter
    def preps(self, new_preps):
        self._preps = new_preps
        self._groups = [str(g) for g in new_preps]

    def read_json(self, filename):
        with open(filename, 'r', encoding='utf8') as read_file:
            cfg = json.load(read_file)
            self.department = cfg.get('department', self.department)
            self.login_prefix = cfg.get('login_prefix', self.login_prefix)
            self.login_group_len = cfg.get('login_group_len', self.login_group_len)
            self.probs = ProblemName.read_names(cfg['problems'], self.department)
            self.preps = cfg.get('preps', [])


class Data:
    def __init__(self, config:Params, csv_file:str, delimiter):
        self.cfg = config

        # читаем cvs файл
        runs = Data.get_data(csv_file, delimiter)
        logging.debug((runs))

        # учитываем только ОК посылки от логинов, которые содержат номера групп по маске, для всех задач
        # так же подсчитывается количество студентов в группе (по количеству логинов, которые посылали успешно задачи)
        data, totals = self.fiter_data(runs)
        self.data = data            # {'702': {'A":22, 'C-DPQE':20, 'Cmem-DPQE':18, 'D-DPQE':10}} - сколько успешных решений задач
        self.totals = totals        # сколько человек в каждой группе {'702': 20, '319':17}
        logging.debug(f'groups in original order: {self.cfg.groups}')
        logging.debug(f'data: {self.data}')

        # оставляем только те названия задач, что реально существуют и интересны нам
        # если фильтр задач в конфигурации указан пустой, то считаем все задачи
        self.headers = self.get_counted_probs(data)     # реальные имена задач, в порядке, заданном в фильтре
        logging.debug(f'real counted prob names {self.headers}')


    def data_group(self, group, get_student_numbers=True, add_percentes=False):
        """
        возвращает список данных: [количество_студентов_в_группе, количество_ок_задачи1, .. количество_ок_задачиN]
        где задачи в том порядке, что в self.headers
        :param group: название (номер) группы
        :param get_student_numbers: добавлять количество студентов в группе или опустить параметр
        :param add_percentes: добавить данные по % соотношению решивших данные задачи к общему количеству студентов в группе
        :return: [количество_студентов_в_группе, количество_ок_задачи1, .. количество_ок_задачиN]
        """
        d = [self.data[group].get(prob.fullname, 0) for prob in self.headers]
        x0 = self.totals[group]

        if add_percentes:
            d += [int(x * 100 / x0) for x in d]
        if get_student_numbers:
            d.insert(0, x0)
        return d

    def data_group_all(self, get_student_numbers=True, add_percentes=False):
        """
        возвращает список данных: [количество_студентов_во_всех группах, количество_ок_задачи1, .. количество_ок_задачиN]
        где задачи в том порядке, что в self.headers и суммы по всем группам
        :param get_student_numbers: добавлять количество студентов в группах или опустить параметр
        :param add_percentes: добавить данные по % соотношению решивших данные задачи к общему количеству студентов в группах
        :return: [количество_студентов_в_группах, количество_ок_задачи1, .. количество_ок_задачиN]
        """
        d = [ sum([gr_data.get(prob.fullname, 0)  for gr_data in self.data.values()]) for prob in self.headers]
        x0 = sum(self.totals.values())

        if add_percentes:
            d += [int(x * 100 / x0) for x in d]
        if get_student_numbers:
            d.insert(0, x0)
        return d



    @staticmethod
    def get_data(file, delimiter=';'):
        """ get scv data from file as list of tuples
        file with data:
        A;B;C
        1;2;3
        parse as
        OrderedDict([('A', '1'), ('B', '2'), ('C', '3')])
        OrderedDict([('A', '10'), ('B', '20'), ('C', '30')])
        """
        with open(file, encoding="utf8") as fh:
            rd = csv.DictReader(fh, delimiter=delimiter)
            runs = [dict(row) for row in rd]
            logging.debug('Read csv data:')
            logging.debug(runs)
        return runs


    def fiter_data(self, runs, counted_status='OK'):
        """
        Create table:
        login_group \ prob | D- | F- | E- | E_mem- |
        -------------------+----+----+----+--------+
        group1             | cd1| cf1| ce1| cemem1 |  данные по группе 1
        group2             | cd2| cf2| ce2| cemem2 |  данные по группе 2
        -------------------+----+----+----+--------+
        total              | cdt| cft| cet| cememt | сумма по всем группам
        as d['group1']['D-']
        and total[group1] - how many different logins in this group1 with any results for any problems - сколько всего человек в группе, нужно будет для подсчета % справившихся с задачей

        """
        d1 = {}         # данные
        total = {}      # для подсчета разных логинов в группе total[group] = [login1, login2, ... loginN]
        for r in runs:
            login = r['User_Login']
            prob = r['Prob']
            result = r['Stat_Short']
            group = self.extract_group(login)
            if group is None:
                continue
            logging.debug(f'filter data (data): {login} {group} {prob} {result}')
            # учитываем очередной логин в группе (будем смотреть сколько в ней разных логинов)
            Data.enroll(total, login, group)
            if result == counted_status:
                Data.count(d1, group, prob)
            # logging.debug(f'filter data (total): {total}')

        logging.debug(f'filter data (total): {total}')
        # проверить, что в конфиге указали все группы и указали правильно
        if set(total.keys()) != set(self.cfg.groups):
            logging.error(f'expected groups:{self.cfg.groups} groups from csv={total.keys()}')
            raise ValueError(f'expected groups:{self.cfg.groups} groups from csv={total.keys()}')

        group_numbers = {group: len(total[group]) for group in sorted(total.keys())}
        logging.debug(f'group_numbers={group_numbers}')
        return d1, group_numbers

    def get_counted_probs(self, data):
        """
        data = {'702': {'A":22, 'C-DPQE':20, 'Cmem-DPQE':18, 'D-DPQE':10}} - сколько успешных решений задач
        self.cfg.probs - или  [ProblemName] - взять только их, или [], тогда взять все задачи
        return counted problem names in filter list order
        """
        # get all problem names from d
        s = set()
        for gv in data.values():
            s = s | set(gv.keys())

        # если не задан фильтр имен задач, то взять все имена
        if not self.cfg.probs:
            return [ProblemName(name) for name in sorted(s)]

        # если задан фильтр по задачам, то fullname должен стать равен реальным именам задач
        #return [prob for prob in self.cfg.probs if prob in s]
        for pn in self.cfg.probs:
            pn.update_fullname(s)

        return self.cfg.probs

    def print_table(self, percent=False):
        """
        print d[task][prob] as table with prob - column header, task - row header
        """
        TABLE_SEPARATOR = '=>'

        d = self.data
        headers = self.headers
        group_numbers = self.totals

        logging.debug('print_table:')
        logging.debug(d)
        # print header
        csv_header = ['group', 'students'] + [h.label for h in headers] + [h.label+'%' for h in headers]
        s = '\t'.join(csv_header)
        print(s)

        # print rows and calc totals
        logging.debug(d)
        logging.debug([h.fullname for h in headers])

        csv_body = []
        for gr in self.cfg.groups:
            csv_body.append( [gr] + self.data_group(gr, get_student_numbers=True, add_percentes=True))
            r = '\t'.join(map(str,csv_body[-1]))
            print(r)

        csv_footer = ['all'] + self.data_group_all(get_student_numbers=True, add_percentes=True)
        r = '\t'.join(map(str, csv_footer))
        print(r)

        # write to  csv file
        filename = f'{self.cfg.department}_table.csv'
        with open(filename, 'w', encoding='utf8',  newline='') as csvfile:
            csvwriter = csv.writer(csvfile, delimiter=';', quotechar='|', quoting=csv.QUOTE_MINIMAL)
            csvwriter.writerow(csv_header)
            csvwriter.writerows(csv_body)
            csvwriter.writerow(csv_footer)


    def extract_group(self, login):
        """
        extract and return group name part from login: remove prefix, get group_name_len symbols
        extract_group('ed95070507', 'ed950', 3) -> '705'
        extract_group('ejudge', 'ed950', 3) -> None
        """
        if not login.startswith(self.cfg.login_prefix):
            return None
        n = len(self.cfg.login_prefix)
        return login[n:n+self.cfg.login_group_len]

    @staticmethod
    def enroll(total, login, group):
        """
        Учитывает сколько разных логинов было в этой группе, нужно будет для подсчета % успешных решений задач по группе
        """
        if total.get(group) is None:
            total[group] = {login}
        else:
            total[group].add(login)


    @staticmethod
    def count(d, group, prob):
        """
        Add +1 to counter for (group, prob) key
        """
        if d.get(group) is None:
            d[group] = {prob: 0}
        d[group][prob] = d[group].get(prob, 0) + 1


if __name__ == '__main__':

    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s:\t%(message)s'
        )

    parser = argparse.ArgumentParser(
        description='Calculate statistics for Ejudge contest stored in csv file', 
        usage= f'\n\t{sys.argv[0]} --prob "C- C-mem- D- F- E- E_mem-" --prob_suffix=DPQE --login_prefix=ed905  2019decDPQE.csv --dir ../2019/DPQE',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("FILE", help="file in csv, dumped standings from ejudge")
    parser.add_argument('-v', "--verbose", help="increase verbosity",
                        action="store_true")
    parser.add_argument("--prob", help="list of problem name prefixes without department name via space")

    parser.add_argument("--prob_suffix", help="department name, add to problem names",
                        default="")
    parser.add_argument("--login_prefix", help="non-group login part",
                        default="")
    parser.add_argument("--group_len", help="length of group part in login",
                        default=3, type=int)
    parser.add_argument("-c", '--config', help="config file name with the options listed above")

    parser.add_argument("--dir", help="output dir for cvs and png files (todo)",
                        default=".")
    parser.add_argument("--delimiter", help="delimiter in csv file, default ;",
                        default=";")
    parser.add_argument("--text_only", help="prevent prot data, use if no matplotlib",
                        default=False, action="store_true")

    args = parser.parse_args()
    
    
    file = args.FILE
    
    if args.verbose:
        print("verbosity turned on")
        logging.getLogger().level = logging.DEBUG
    
    # сначала разбираем конфиг
    cfg = Params()
    if args.config:
        cfg.read_json(args.config)
    logging.info(f'Read config file: {cfg}')    
    
    # параметры командной строки приоритетнее конфиг-файла
    cfg.output_dir = args.dir
    if args.prob_suffix:
        cfg.department = args.prob_suffix
    if args.prob:
        cfg.probs = ProblemName.read_names(args.prob, cfg.department)
    if args.login_prefix:
        cfg.login_prefix = args.login_prefix
    if args.group_len:
        cfg.login_group_len = args.group_len
    
    logging.info(f'Args: file={file} department={cfg.department} prefix={cfg.login_prefix} group_len={cfg.login_group_len} tasks={cfg.probs}')
    logging.info(f'Parameters (finally): {cfg}')    

    # разбираем файл данных
    data = Data(cfg, file, args.delimiter)
    data.print_table()

    if not args.text_only:
        print("Plot data")


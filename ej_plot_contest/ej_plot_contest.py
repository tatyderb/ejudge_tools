import argparse
import datetime
import csv
import json
import logging
import os
import pathlib
import sys


"""
Parse dumped runs, get OK statistics: prob_
Run_Id;Time;Nsec;Time2;Date;Year;Mon;Day;Hour;Min;Sec;Dur;Dur_Day;Dur_Hour;Dur_Min;Dur_Sec;Size;IPV6_Flag;IP;SSL_Flag;Sha1;User_Id;User_Login;User_Name;User_Inv;User_Ban;User_Lock;Prob;Variant;Lang;Content_Type;Stat_Short;Status;Score;Score_Adj;Test;Import_Flag;Hidden_Flag;RO_Flag;Locale_Id;Pages;Judge_Id
1593;1576160067;253221000;20191212171427;20191212;2019;12;12;17;14;27;10646;0;02;57;26;1076;0;10.55.131.43;0;49563b565fed363984a340b94ab6fdc354c0c202;10089;ed95080609;Иванов Иван Иванович   Б04-905;;;;F-DPQE;0;gcc-vg;;PT;Partial solution;4;0;4;1;0;0;0;1;0;0
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
    def __init__(self, base_dir):
        self.base_dir = base_dir    # resolve all paths into config relative this directory
        self.dir = pathlib.Path('.')
        self.output_dir = '.'       # directory for output csv tables and plots
        self.file_data = None       # обязательно должно стать именем файла входных данных
        self.department = ''        # факультет
        self.stage = None           # test, oct, dec - какая именно контрольная проходит
        self.login_prefix = 'ed'    # как добыть номер группы из логина: префикс и далее длина части, которая идентификатор группы
        self.login_group_len = 3
        self.login_list = None      # группа может быть задана списком в csv файле Group;Login
        self._preps = {}            # group from login : prep last name, or build by csv data without prep names
        self._groups = []           # list of groups in preconstructed order
        self.probs = []             # ProblemName list
        self.duration = None        # contest duration, all OK runs after end would be dropped (дорешивание не учитываем)
        self.statement_table = False     # файл данных содержит не run dumps (False), а таблицу результатов (True)

    
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

    @staticmethod
    def read_json(self, base_dir, filename):
        base_dir_path = pathlib.Path(base_dir)
        filename_path = pathlib.Path(filename)
        if not filename_path.is_absolute():
            filename_path = base_dir_path / filename_path

        with open(filename_path, 'r', encoding='utf8') as read_file:
            cfg = json.load(read_file)
            return __class__.from_dict(base_dir, cfg)

    @staticmethod
    def from_dict(base_dir, dictionary):
        """
        create Params instace from dictionary, resolve all paths relative the base_dir
        :param base_dir: resolve all paths relative this directory
        :param dictionary: dictionary with data
        :return: Params instance
        """
        p = Params(base_dir)
        for key in dictionary:
            setattr(p, key, dictionary[key])
        p.probs = ProblemName.read_names(dictionary['problems'], p.department)

        if p.duration is not None:
            t = datetime.datetime.strptime(p.duration, '%H:%M')
            p.duration = datetime.timedelta(hours=t.hour, minutes=t.minute)

        logging.debug(p)

        if 'dir' in dictionary:
            p.dir = pathlib.Path(dictionary['dir'])


        # меняем директорию, относительно которой будет разбирать пути
        p.base_dir = p.resolve_path(p.dir)
        # и определяем где лежат входные файлы
        p.file_data = p.resolve_path(p.file_data)
        p.login_list = p.resolve_path(p.login_list)

        # результаты конкретного факультета и контрольной - отдельно от данных
        p.output_dir = p.resolve_path(p.output_dir)
        logging.info(f'output_dir={p.output_dir} dep={p.department} stage={p.stage}')
        p.output_dir = p.output_dir / p.department / p.stage
        # директория выходных данных, создаем ее
        logging.info(f'Output directory is {p.output_dir.resolve()}')
        if not p.output_dir.exists():
            p.output_dir.mkdir(parents=True)

        return p


    def resolve_path(self, path):
        if path is None:
            return None
        if not isinstance(path, pathlib.Path):
            path = pathlib.Path(path)
        if not path.is_absolute():
            return self.base_dir / path
        return path



class Data:
    def __init__(self, config:Params):
        """
        Читаем данные из csv файла данных config.file_data, фильтруем из них только нужные и их подсчитываем
        :param config: параметры конфигурации
        """
        self.cfg = config

        # раньше были аргументами, теперь лежат в конфиге
        csv_file = config.file_data
        login_csv_file = config.login_list
        statement_table = config.statement_table
        duration = config.duration

        # результирующий файл для таблицы - имя файла данных с расширением csv в директории результататов

        # читаем cvs файл
        runs = Data.get_data(csv_file)
        logging.debug((runs))
        self.logins = Data.get_login_list(login_csv_file) if login_csv_file else None
        self.groups = self.cfg.groups    # {'705': 'Иванов', '702':'Петров'}

        if statement_table:
            # это statement table, где задача считается НЕ решеной, если у нее нет или 0 баллов.
            # Иначе - решена, поэтому ручками вытрите неполные решения, если не хотите их учитыватьd
            data, totals = self.parse_statement_table(runs)
        else:
            # runs dump in csv format with logins list if needed

            # учитываем только ОК посылки от логинов, которые содержат номера групп по маске, для всех задач
            # так же подсчитывается количество студентов в группе (по количеству логинов, которые посылали успешно задачи)
            data, totals = self.fiter_data(runs, duration)

        self.data = data            # {'702': {'A":22, 'C-DPQE':20, 'Cmem-DPQE':18, 'D-DPQE':10}} - сколько успешных решений задач
        logging.debug(f'groups in original order: {self.cfg.groups}')
        logging.debug(f'data: {self.data}')

        # количество студентов в группе считаем или по списку логинов, или по посылкам (total)
        # сколько человек в каждой группе {'702': 20, '319':17}
        if self.logins is not None:
            self.totals = self.count_totals_by_login_list()
        else:
            self.totals = self.count_totals_by_runs(totals)


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
        d = [self.data.get(group, {}).get(prob.fullname, 0) for prob in self.headers]
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

    def data_prob(self, prob:ProblemName):
        """
        Возвращает для задачи prob список [количество_ок_группы1, количество_ок_группы2, .. количество_ок_группыN]
        :param prob: задача
        :return:
        """
        return [self.data.get(g, {}).get(prob.fullname, 0) for g in self.groups]

    @staticmethod
    def read_csv_file(file, delimiter=None):
        """
        Read csv file and return list of OrderedDict
        file with data:
        A;B;C
        1;2;3
        parse as
        OrderedDict([('A', '1'), ('B', '2'), ('C', '3')])
        OrderedDict([('A', '10'), ('B', '20'), ('C', '30')])

        :param file: filename
        :param delimiter: None - try to use delimiter , or ; (good delimiter has 1+ columns)
        :return: list of OrderedDict
        """
        if delimiter is None:       # try delimiters ; and ,
            delimiter = [';', ',']
        else:
            delimiter = [delimiter]

        for delim in delimiter:
            with open(file, encoding="utf8") as fh:
                rd = csv.DictReader(fh, delimiter=delim)
                runs = [dict(row) for row in rd]
                if len(runs[0].keys()) > 1:
                    logging.debug('Read csv data:')
                    logging.debug(runs)
                    return runs


    @staticmethod
    def get_data(file, delimiter=';'):
        return Data.read_csv_file(file, delimiter)

    @staticmethod
    def get_login_list(file):
        data = Data.read_csv_file(file)
        return {r['Login']:r['Group'] for r in data}

    def parse_statement_table(self, runs):
        """
        Даны runs -  прочитанная statement table в формате csv, из которых нужно сделать
        total[group1] - how many different logins in this group
        считаем у сколькоих пользователей из group1 за задачу D- очки >0 в d['group1']['D-']

        :param runs:
        :return: data, totals
        """
        print(runs)
        d = {}
        total = {gr:0 for gr in self.groups}
        for r in runs:
            group = self.get_group(r)
            if group not in total:
                logging.warning(f'group {group} has not been counted')
                continue
            total[group] += 1
            for prob in self.cfg.probs:
                score = self.get_score(r, prob)
                # logging.debug(f"score={score} prob={prob} r={r}")
                if  score > 0:
                    self.count(d, group, prob.fullname)

        print(d)
        return d, total

    def get_score(self, r, prob):
        """
        При разборе standing table возвращаем очки в виде int (если было пусто, возвращаем 0, если проблемы нет, возвращаем 0)
        :param r:
        :param prob:
        :return:
        """
        titles = [prob.label, prob.fullname]
        for p in titles:
            score = r.get(p)
            if score is None:
                continue
            try:
                score = int(score)
            except ValueError:
                score = 0
            if score > 0:
                return score

        return 0


    def fiter_data(self, runs, contest_duration=None, counted_status='OK'):
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
        contest_start_timestamp = None   # contest start, datetime
        contest_end_timestamp = None     # contest end, datetime
        for r in runs:
            login = r['User_Login']
            prob = r['Prob']
            result = r['Stat_Short']
            timestamp = r['Time']
            user_invis = r['User_Inv']
            logging.debug(f'raw data (data): {login} ??? {prob} {result} {timestamp}')
            logging.debug('User_Inv=[{user_invis}]')
            if user_invis:
                logging.warning(f'Invisible user {login} ... skipped')
                continue

            # номер группы достаем или из списка посылок или из списка логин-группа или из логина по маске
            group = self.get_group(r, login)

            if group is None or group == '0':
                continue
            logging.debug(f'filter data (data): {login} {group} {prob} {result}')

            # учитываем очередной логин в группе (будем смотреть сколько в ней разных логинов), посылки могут быть не ОК
            Data.enroll(total, login, group)

            if result != counted_status:
                continue

            #if user_invis:
            #    logging.warning(f'Invisible user {login} from {group} with task {prob}')
            #    continue


            # учитываем, чтобы посылка не прошла после окончания турнира, во время дорешивания, если указана длительность турнира
            # если длительность не указана, считаем посылки (с правильным логином и группой)
            if contest_duration is None:
                Data.count(d1, group, prob)
                continue

            # первая ОК посылка от правильного логина становится началом отсчета длительности
            if contest_end_timestamp is None:
                contest_start_timestamp = int(timestamp)
                contest_end_timestamp = datetime.datetime.fromtimestamp(contest_start_timestamp) + contest_duration
                contest_end_timestamp = contest_end_timestamp.timestamp()
            # учитываются посылки во время турнира (а не до него или при дорешивании)
            if contest_start_timestamp <= int(timestamp) <= contest_end_timestamp:
                Data.count(d1, group, prob)
            else:
                logging.warning(f"Out of date: {group} {prob} {timestamp}")
            # logging.debug(f'filter data (total): {total}')
        return d1, total        # это total по посылкам, его могут потом игнорировать, если считать будем по списку логинов

    def get_group(self, r, login=None):
        """
        Достает номер группы или из поля Group записи r, или по логину из списка логинов или по маске из логина
        :param r: - прочитанная запись из cvs файла
        :param login: - если уже найден логин для этой записи, передать его (run dump, поле Login, в standing table этого поля нет
        :return: group
        """
        if 'Group' in r.keys():
            group = r['Group']
        elif self.logins:
            group = self.logins[login]
        else:
            group = r.get('Group', self.extract_group(login))
        return group

    def count_totals_by_login_list(self):
        """
        В self.totals делает словарь {номер группы : количество студентов в ней} по списку студентов или учтенным посылкам
        """
        a = list(self.logins.values())
        logging.debug(f'ALL LOGINS: -------------------------------\n{a}\n-------------------------------\n')
        logging.debug(f'groups: {self.cfg.groups}')
        return {group: a.count(group) for group in self.cfg.groups}

    def count_totals_by_runs(self, total):
        # количество студентов в группе считаем по количеству разных логинов в группе

        # может случиться (при обработке standing table), что total уже в нужном формате: {группа: количество_студентов}
        # тогда нужно просто вернуть переданный total
        if all(map(lambda v : isinstance(v, int), total.values())):
            return total

        # считаем разные логины
        logging.debug(f'filter data (total): {total}')
        # проверить, что в конфиге указали все группы и указали правильно
        if set(total.keys()) != set(self.cfg.groups):
            logging.warning(f'expected groups:{self.cfg.groups} groups from csv={total.keys()}')
            #raise ValueError(f'expected groups:{self.cfg.groups} groups from csv={total.keys()}')
        #print(total)
        group_numbers = {group: len(total[group]) for group in sorted(total.keys())}
        logging.debug(f'group_numbers={group_numbers}')
        return group_numbers

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

    def print_table(self, percent=False, to_html=True):
        header, body, footer = self.get_table(percent)
        Data.table_print(header, body, footer)
        self.table_csv(header, body, footer)
        if to_html:
            self.table_html(header, body, footer)

    def table_html(self,header, body, footer):

        from jinja2 import Environment, FileSystemLoader

        html_template_dir = pathlib.Path(__file__).parent / 'jinja_templates'
        html_template_file = 'result_table_template.html'

        env = Environment(loader=FileSystemLoader([html_template_dir]))
        template = env.get_template(html_template_file)

        # разбиваем данные на абсолютные и проценты
        n = len(self.headers)
        # делаем кусок html кода с только таблицей абсолютных данных
        self.table_html_1(template, header[2:n+2], [r[:n+2] for r in body], footer[:n+2])
        # делаем кусок html кода с только таблицей процентов
        self.table_html_1(template, header[n+2:], [r[:2]+r[n+2:] for r in body], footer[:2]+footer[n+2:], percent=True)

    def table_html_1(self, template, header, body, footer, percent=False):
        print(f'header={header}')
        print(f'body={body}')
        print(f'footer={footer}')


        percent_sign = '%' if percent else ''
        output_from_parsed_template = template.render(header=header, body=body, footer=footer, percent=percent_sign)
        print(output_from_parsed_template)

        if percent:
            filename = f'{self.cfg.department}_{self.cfg.stage}_percent_table.html'
        else:
            filename = f'{self.cfg.department}_{self.cfg.stage}_table.html'
        html_file = self.cfg.output_dir.joinpath(filename).resolve()

        # to save the results
        with open(html_file, "w", encoding='utf8') as fh:
            fh.write(output_from_parsed_template)

    def get_table(self, percent=False):
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

        # print rows and calc totals
        logging.debug(d)
        logging.debug([h.fullname for h in headers])

        csv_body = []
        for gr, prep in self.cfg.preps.items():
            csv_body.append( [f'{gr} - {prep}'] + self.data_group(gr, get_student_numbers=True, add_percentes=True))

        csv_footer = ['all'] + self.data_group_all(get_student_numbers=True, add_percentes=True)

        print(csv_header, csv_body, csv_footer)
        return (csv_header, csv_body, csv_footer)


    def table_csv(self, csv_header, csv_body, csv_footer):
        # write to  csv file
        filename = f'{self.cfg.department}_table.csv'
        csv_file = self.cfg.output_dir.joinpath(filename).resolve()
        with open(csv_file, 'w', encoding='utf8',  newline='') as csvfile:
            csvwriter = csv.writer(csvfile, delimiter=';', quotechar='|', quoting=csv.QUOTE_MINIMAL)
            csvwriter.writerow(csv_header)
            csvwriter.writerows(csv_body)
            csvwriter.writerow(csv_footer)

    @staticmethod
    def table_print(csv_header, csv_body, csv_footer):
        """
        Print table in stdout
        :param csv_header:
        :param csv_body:
        :param csv_footer:
        """
        s = '\t'.join(csv_header)
        print(s)

        for r in csv_body:
            s = '\t'.join(map(str, r))
            print(s)

        s = '\t'.join(map(str, csv_footer))
        print(s)

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



def get_flat_dict(d, department=None, stage=None):
    """
    d = {a1: A1, a2:A2, a3: {b1:B1, b2:B2, b3:{c1:C1, c2:C2}} }
    :param d:
    :param kwargs:
    :return:
    """
    dres = {}
    d1 = {}
    for k in d.keys():
        if k != 'department':
            dres[k] = d[k]
        else:
            dres['department'] = department
            d1 = d['department'][department]

    print(dres)
    print(d1)
    # сначала обрабатываем все ключи высших уровней, потом перезаписываем их уровнем stage
    for st in d1:
        if st != 'stage':
            dres[st] = d1[st]

    dres['stage'] = stage
    dres.update(d1['stage'][stage])
    return dres

def process_data(cfg:Params, show_plots=False, to_html=True):
    """
    Обработка данных и вывод результатов
    :param cfg: конфиг, где указано что брать, как обрабатывать и куда класть результаты
    :return:
    """
    # разбираем файл данных
    if args.text_only:
        data = Data(cfg)
        data.print_table(to_html)
    else:
        from ej_plotter import DataPlotter
        data = DataPlotter(cfg)
        data.print_table(to_html)
        data.plot_all(show_plots)

def process_one_contest(config, config_dir, config_only, show_plots):
    cfg = Params.from_dict(config_dir, config)
    if not config_only:
        process_data(cfg, show_plots)
    logging.info(cfg.output_dir)

    # а теперь данные, не отфильтрованные по задачам. Чтобы два раза не запускать с фильтрованным и нефильтрованным конфигом.
    if config['problems']:
        config['problems'] = ''
        config['output_dir'] = 'res_unfiltered'
        cfg = Params.from_dict(config_dir, config)
        if not config_only:
            process_data(cfg, show_plots)
        logging.info(cfg.output_dir)


if __name__ == '__main__':

    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s:%(lineno)d  \t%(message)s'
        )

    parser = argparse.ArgumentParser(
        description='Calculate statistics for all Ejudge contests described into config json',
        usage=f'\n\t{sys.argv[0]} cfg_2019.json FRTK dec --text_only',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("config", help="config in json format")
    parser.add_argument("department", help="Department name in config dictionary", default=None, nargs='?')
    parser.add_argument("stage", help="stage name in config dictionary", default=None, nargs='?')
    parser.add_argument("--config_only", help="prevent any data processing, only print resulted config, for debug only!",
                        default=False, action="store_true")
    parser.add_argument("--text_only", help="prevent prot data, use if no matplotlib",
                        default=False, action="store_true")
    parser.add_argument("--show_plots", help="show all plots interactively in addition to saving all images",
                        default=False, action="store_true")
    parser.add_argument('-v', "--verbose", help="increase verbosity",
                        action="store_true")

    args = parser.parse_args()

    if args.verbose:
        print("verbosity turned on")
        logging.getLogger().level = logging.DEBUG

    base_dir = pathlib.Path.cwd()
    config_path = base_dir / args.config
    config_dir = config_path.parent

    with open(config_path, 'r', encoding='utf8') as read_file:
        config = json.load(read_file)
    json.dump(config, indent=4, fp=sys.stdout)

    # обрабатываем конфиг для одного единственного констеста (конфиг плоский)
    if isinstance(config.get('department'), str) and isinstance(config.get('stage'), str):
        logging.info('Не знаю как Земля, но конфиг плоский')
        process_one_contest(config, config_dir, args.config_only, args.show_plots)
        sys.exit(0)

    # в конфиге есть уровни вложенности
    logging.info(f'file={args.config} dep={args.department} stage={args.stage}')

    departments = config['department'].keys() if args.department is None else [args.department]

    for dep in departments:
        stages = config['department'][dep]['stage'].keys() if args.stage is None else [args.stage]
        for st in stages:
            print(dep, st)
            d = get_flat_dict(config, dep, st)
            json.dump(d,indent=4, fp=sys.stdout)
            if d is None:
                logging.warning(f'Config file has not department {dep} and stage {st}')
                continue
            process_one_contest(d, config_dir, args.config_only, args.show_plots)


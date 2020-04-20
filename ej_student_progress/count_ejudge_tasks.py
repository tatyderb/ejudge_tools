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

def read_runs(file, delimeter=';'):
    """ get scv data from file as list of tuples
    file with data:
    A;B;C
    1;2;3
    parse as
    OrderedDict([('A', '1'), ('B', '2'), ('C', '3')])
    OrderedDict([('A', '10'), ('B', '20'), ('C', '30')])    
    """
    with open(file, encoding="utf8") as fh:
        rd = csv.DictReader(fh, delimiter=';')
        runs = [dict(row) for row in rd]
    return runs

def fiter_data(runs, task_fiter, login_list, counted_status='OK'):
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
    d1 = {}
    total = {}
    for r in runs:
        login = r['User_Login']
        prob = r['Prob']
        result = r['Stat_Short']
        group = extract_group(login, prefix, group_name_len)
        if group is None:
            continue
        logging.debug(f'filter data (data): {login} {group} {prob} {result}')
        enroll(total, login, group)
        if result == counted_status:
            count(d1, group, prob)
        #logging.debug(f'filter data (total): {total}')

    logging.debug(f'filter data (total): {total}')
    group_numbers = {group:len(total[group]) for group in sorted(total.keys())}
    logging.debug(f'group_numbers={group_numbers}')
    return d1, group_numbers

def parse_config(cfg_file):
    """ parse config file in json format:
    {
        "logins": [
        {
            "login_format":"m2020%02d",
            "login_first":1,
            "login_last":89
        }, 
        {
            "login": "ejudge"
        }
        ],
        "tasks" : [
            "hello",	"float_2",	"float_3",	"float_4"
        ]
    }
    """
    with open(cfg_file, 'r', encoding='utf8') as read_file:
        cfg = json.load(read_file)

    login_list = []
    for log in cfg['login']:
        if 'login' in log:
            login_list += [log['login']]
        else:
            login_format = log['login_format']
            login_first = log['login_first']
            login_last = log['login_last']
            login_list += [login_format.format(x) for x in range(login_first, login_last+1)]
            
    task_list = {}
    DEFAULT_SCORE = 10
    for t in cfg['tasks']:
        if isinstance(t, str):
            task_list[t] = DEFAULT_SCORE
        else:
            task_list[t['name']] = t['score']
    logging.debug(task_list)
    return login_list, task_list
    
def get_data_from_runs(timestamp, runs, login_list, task_list, olddata_file=None):
    """ Update data in olddata_file with runs according to login_list and task_list filters
    """
    '''
    if olddata_file is None:
        data = [['login', timestamp]] 
        data += [[login, 0] for login in login_list]
    else:
        with open(olddata_file, newline='') as csvfile:
            data = csv.reader(csvfile, delimiter=' ', quotechar='|')
        data[0] = data[0].expand(['d', timestamp])
    '''
    data = [['login', timestamp]] 
    data += [[login, 0] for login in login_list]

    
    d = {}
    for r in runs:
        login = r['User_Login']
        prob = r['Prob']
        result = r['Stat_Short']
        if result != 'OK':
            logging.debug(f'skip result {result}')
            continue
        if not prob in task_list:
            logging.debug(f'skip task {prob}')
            continue
        logging.debug(f'count login={login} task={prob}')

        
        # d[login] = d.get(login, 0) + 1
        if login in d:
            d[login].add(prob)
        else:
            d[login] = {prob}
        
    
    for row in data[1:]:
        row[-1] = len(d.get(row[0], {}))
        
    logging.info(data)
    return data
    
def get_data_from_standing(timestamp, runs, login_list, task_list, olddata_file=None):
    """ output:
    [[login, ok_task_count], ['ejudge', 12]]
    """   
    """  Data example:
    OrderedDict([('login', 'ejudge'), ('hello', '13'), ('float_1', '27')])
    """
    data = [['login', timestamp]] 
    d = { login:0 for login in login_list}
    for r in runs:
        logging.debug(r)
        login = r['User']
        logging.debug(login)
        logging.debug(task_list)
        if not login in login_list:
            logging.debug(f'skip login {login}')
            continue
            
        for task, score in r.items():
            if not task in task_list:
                logging.debug(f'skip {login} {task}')
            elif score == '\xa0' or int(score) < task_list[task]:
                logging.debug(f'skip {login} {task} {score}')
            else:
                logging.debug(f'COUNT {login} {task} {d[login]}')
                d[login] += 1    # count this task as ok
    data += [[login, d[login]] for login in login_list]
    logging.info(data)
    return data
    
def save_result_csv(data, res_file):
    """ write data in res_file in csv format
    """
    with open(res_file, 'w', encoding='utf8',  newline='') as csvfile:
        csvwriter = csv.writer(csvfile, delimiter=';', quotechar='|', quoting=csv.QUOTE_MINIMAL)
        csvwriter.writerows(data)

    
if __name__ == '__main__':
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s:%(lineno)d  \t%(message)s'
        )

    parser = argparse.ArgumentParser(
        description='Calculate statistics per login for one Ejudge contests described into config json',
        usage=f'\n\t{sys.argv[0]} --standings 20200405 20200405_t1.csv 01_int.json now.csv',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("timestamp", help="Data date as string")
    parser.add_argument("raw_csv", help="input data in csv format")
    parser.add_argument("config", help="config in json format")
    parser.add_argument("res_csv", help="output data in csv format", default='now.csv')
    parser.add_argument("--standings", help="csv data from stangings table",
                        default=False, action="store_true")
    parser.add_argument('-v', "--verbose", help="increase verbosity",
                        default=False, action="store_true")

    args = parser.parse_args()

    if args.verbose:
        logging.info("verbosity turned on")
        logging.getLogger().level = logging.DEBUG    
    timestamp = args.timestamp
    cvs_file = args.raw_csv
    cfg_file = args.config
    res_file = args.res_csv
    
    '''
    olddata_file = sys.argv[4]
    if len(sys.argv) > 4:
        olddata_file = sys.argv[4]
    else:
        olddata_file = None
    '''
    login_list, task_list = parse_config(cfg_file)
    
    if args.standings:
        update_data = get_data_from_standing
    else:
        update_data = get_data_from_runs
    runs = read_runs(cvs_file)
    res = update_data(timestamp, runs, login_list, task_list)
    save_result_csv(res, res_file)

    